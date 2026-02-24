import datetime
import logging
import os
import random
from functools import reduce
from gtts import gTTS
import threading

from ai import ensure_hint, get_mem_hint  # ensure_hint используется в обработчике
from markups import markups
import asyncio
from deep_translator import GoogleTranslator
from db_manager import DataBaseUpdater, UserUpdater
from db_manager import MindCard
from settings import *
from handlers import *
from telegram_token import TOKEN
from collections import defaultdict

from telegram import Update
from telegram.ext import Updater
from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram.ext import CallbackContext, CallbackQueryHandler

try:
    from telegram_token import *
except ImportError:
    exit('Скопируйте telegram_token.py.deafault как telegram_token.py и укажите в нем токен')

# translator = GoogleTranslator() # Будем создавать экземпляр при вызове для гибкости или один раз
async def translate_text_async(text: str, target_lang: str = 'en') -> str:
    return await asyncio.to_thread(
        GoogleTranslator(source='auto', target=target_lang).translate,
        text
    )

logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.CRITICAL)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3.connection.VerifiedHTTPSConnection").setLevel(logging.CRITICAL)
logging.getLogger("telegram.ext.dispatcher").setLevel(logging.CRITICAL)
log = logging.getLogger()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.addHandler(stream_handler)
log.setLevel(logging.INFO)
stream_handler.setLevel(logging.INFO)


def def_value():
    return User(0, None)


class User:
    def __init__(self, user_id, user_db):
        self.user_id = user_id
        self.mindcards = []
        self.mindcards_delayed = []
        self.mindcards_queuing = []
        self.state = ''
        self.repeat_time = datetime.datetime.today()
        self.db_cards = None
        self.user_db = user_db
        self.score = 0
        self.nickname = ''
        self.nickname_change = 0
        # Settings:
        self.stack_size = 20
        self.interface_lang = 1
        self.first_lang = 0
        self.second_lang = 1
        self.add_cards_to_stack = True

    def finalize_card(self, card, db):
        """Remove card from active stack and update DB when it is repeated"""
        if (card.repeat_mistake < 2 and card.repeat_lvl < 4) or card.repeat_mistake == 0:
            card.repeat_lvl += 1
        db.update_base([card])
        if card in self.mindcards:
            self.mindcards.remove(card)
        if card in self.mindcards_delayed:
            self.mindcards_delayed.remove(card)
        self.score += 1
        self.save()

    def get_card_by_id(self, card_id):
        for card in self.mindcards:
            if card.card_id == card_id:
                return card
        for card in self.mindcards_delayed:
            if card.card_id == card_id:
                return card
        for card in self.mindcards_queuing:
            if card.card_id == card_id:
                self.mindcards.append(card)
                self.mindcards_queuing.remove(card)
                return card

    def get_card(self, db):
        # two cards list for get all cards after repeat its again
        if self.add_cards_to_stack \
                or (len(self.mindcards) + len(self.mindcards_delayed)) == 0 \
                or len(self.mindcards_queuing) < self.stack_size:
            while (len(self.mindcards) + len(self.mindcards_delayed)) < self.stack_size and len(
                    self.mindcards_queuing) > 0:
                card = self.mindcards_queuing[0]
                self.mindcards.append(card)
                self.mindcards_queuing.remove(card)
        while len(self.mindcards) > 0 or len(self.mindcards_delayed) > 0:
            if len(self.mindcards) == 0 and len(self.mindcards_delayed) > 0:
                self.mindcards = self.mindcards_delayed
                self.mindcards_delayed = []
            card = random.choice(self.mindcards)
            if (card.today_repeat + card.today_reverse_repeat) < (6 + card.repeat_mistake):
                self.mindcards_delayed.append(card)
                self.mindcards.remove(card)
                self.repeat_time = datetime.datetime.today()
                card.hint_shown = False
                card.temp_hint = None
                return card
            else:
                self.finalize_card(card, db)
                card = self.get_card(db)
                if card:
                    card.hint_shown = False
                    card.temp_hint = None
                    return card

    def save(self):
        self.user_db.save(self)

    def load(self):
        self.user_db.load(self)


def default_markup():
    return markups['start']


class Bot:
    def __init__(self, token):
        self.users = defaultdict(def_value)
        self.user_card = {}
        self.bot = Updater(token=token)
        self.markup = defaultdict(default_markup)
        self.db = DataBaseUpdater()
        self.user_db = UserUpdater()
        self.repeat = datetime.date.today()
        self.button_handlers = {
            'load': self.load,
            'repeat_cards': self.repeat_cards,
            'save_translated': self.save_translated,
            'user_cards': self.load_user_cards,
            'settings': self.settings,
            'help': self.help_command,
            'message_delete': self.message_delete,
            'change_name': self.change_name,
            'stats': self.stats,
            'hint': self.hint_handler,
            'wait': lambda *args, **kwargs: None,
        }

    def run(self):
        """
        Run the bot
        """
        updater = Updater(token=TOKEN)
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler('start', self.start))
        dispatcher.add_handler(CommandHandler('help', self.help_command))
        dispatcher.add_handler(CommandHandler('load_user_cards', self.load_user_cards))
        dispatcher.add_handler(CommandHandler('load_today_cards', self.load_today_cards))
        dispatcher.add_handler(CommandHandler('repeat', self.repeat_cards))
        dispatcher.add_handler(CommandHandler('settings', self.settings))
        dispatcher.add_handler(CommandHandler('stats', self.stats))
        dispatcher.add_handler(CallbackQueryHandler(self.button))
        dispatcher.add_handler(MessageHandler(Filters.text, self.handle_messages))
        updater.start_polling()

    # ─────────────────────────────────────────────────────────────────────
    #  НОВЫЙ ОБРАБОТЧИК ПОДСКАЗОК
    # ─────────────────────────────────────────────────────────────────────
    def hint_handler(self, update, context, button):
        """
        button = ['hint', card_id, action]
        action: toggle | new | delete | replace | cancel
        """
        user = self.users[update.callback_query.from_user.id]
        card_id = int(button[1])
        action = button[2]
        card = user.get_card_by_id(card_id)
        # Если подсказка уже генерируется — молча игнорируем повторные клики
        if getattr(card, 'hint_pending', False):
            return None
        need_async_gen = (
                (action == 'new') or
                (action == 'toggle' and card.hint is None)
        )

        # Если подсказка уже генерируется — молча игнорируем повторные клики
        if getattr(card, 'hint_pending', False):
            return None
        need_async_gen = (
                (action == 'new') or
                (action == 'toggle' and card.hint is None)
        )

        if need_async_gen:
            # Помечаем карту как «в обработке»
            card.hint_pending = True
            card.hint_shown = False
            card.temp_hint = None  # на всякий случай

            # Сразу показываем «⌛»-клавиатуру
            cards_left = len(user.mindcards) + len(user.mindcards_delayed) + len(user.mindcards_queuing)
            base_text = MESSAGE[user.interface_lang]['repeat'] + str(cards_left)
            base_text += '\n\n⌛ Generating hint…'

            markup = markups['card_markup'](card)

            # Запускаем отдельный поток
            threading.Thread(
                target=self._generate_hint_async,
                args=(
                    card,
                    user,
                    update.callback_query.message.chat_id,
                    update.callback_query.message.message_id,
                    context,
                    action == 'new',  # replace_current=True  ➜ temp_hint
                ),
                daemon=True).start()

            return [base_text, markup, None]
        # --- toggle ---------------------------------------------------------
        if action == 'toggle':
            card.hint_shown = not card.hint_shown
        # --- delete ---------------------------------------------------------
        elif action == 'delete':
            card.hint = None
            card.hint_shown = False
            card.temp_hint = None
            self.db.update_base([card])
        # --- replace / save -------------------------------------------------
        elif action == 'replace':
            if card.temp_hint:  # temp_hint становится основной
                card.hint = card.temp_hint
                card.temp_hint = None
            card.hint_shown = True
            self.db.update_base([card])
        # --- cancel ---------------------------------------------------------
        elif action == 'cancel':
            card.temp_hint = None
            card.hint_shown = bool(card.hint)

        # ───── обновляем сообщение ─────
        cards_left = len(user.mindcards) + len(user.mindcards_delayed) + len(user.mindcards_queuing)
        base_text = MESSAGE[user.interface_lang]['repeat'] + str(cards_left)

        if card.hint_shown:
            hint_text = card.temp_hint if card.temp_hint else card.hint
            base_text += f'\n\n💡 *Hint*\n{hint_text}'

        markup = markups['card_markup'](card)
        return [base_text, markup, None]

    def _generate_hint_async(
            self, card, user, chat_id, message_id, context, replace_current: bool):
        """
        Отдельный поток: спрашивает OpenAI, заполняет card,
        снимает «pending» и редактирует сообщение с готовой подсказкой.
        """
        try:
            # 1) сам запрос
            if replace_current:
                card.temp_hint = get_mem_hint(card.word_one, card.word_two)
            else:
                card.hint = get_mem_hint(card.word_one, card.word_two)
                # если это «постоянная» подсказка — сразу пишем в БД
                self.db.update_base([card])

            # 2) снимаем флаг
            card.hint_pending = False
            card.hint_shown = True

            # 3) собираем финальный текст/клавиатуру
            cards_left = len(user.mindcards) + len(user.mindcards_delayed) + len(user.mindcards_queuing)
            text = MESSAGE[user.interface_lang]['repeat'] + str(cards_left)

            hint_text = card.temp_hint if card.temp_hint else card.hint
            text += f'\n\n💡 *Hint*\n{hint_text}'

            markup = markups['card_markup'](card)

            # 4) показываем пользователю
            context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=markup,
                parse_mode='Markdown')
        except Exception:
            logging.exception('Ошибка при асинхронной генерации подсказки')
            card.hint_pending = False  # сбрасываем, чтобы не зависло

    def handle_messages(self, update: Update, context: CallbackContext):
        self.user_check(update)
        try:
            log.debug('обнаружен ивент: %s', update.message.text)
            self.on_event(update, context)
        except ConnectionError:
            log.exception(f'Ошибка при получении ивента')

    def new_user(self, user_id):
        """
        :return: create new user for keeping repeating cards, load cards from database for the user id
        """
        user = User(user_id, self.user_db)
        user.load()
        self.users[user_id] = user
        users_db_cards = self.db.load_base(user)
        if users_db_cards:
            self.users[user_id].mindcards_queuing = users_db_cards

    def on_event(self, update, context):
        user_id = update.message.from_user.id
        if update:
            if user_id not in self.users:
                log.info(f'New user is created, user_id: {user_id} {update.message.from_user.username}')
                self.new_user(user_id)
            user = self.users[user_id]
            button_click = False
            if self.markup[user_id]:
                for keyboard in self.markup[user_id].keyboard:
                    for button in keyboard:
                        if update.message.text == button.text:
                            button_click = True
                            self.buttons_handler(update, context, user)
            if update.message.text[:5] == '/load':
                num = update.message.text[6:]
                self.load(update, context, num=num)
            elif update.message.text[:7] == '/delete':
                num = update.message.text[8:]
                for card in user.mindcards:
                    if card.card_id == num:
                        user.mindcards.remove(card)
                for card in user.mindcards_delayed:
                    if card.card_id == num:
                        user.mindcards_delayed.remove(card)
                for card in user.mindcards_queuing:
                    if card.card_id == num:
                        user.mindcards_queuing.remove(card)
                self.db.card_delete(user, num)
            elif update.message.text[:5] == '/name':
                self.change_name(update, context)
            elif not button_click:
                self.handle_text(update, context, user)

    def start(self, update: Update, context: CallbackContext):
        user = self.user_check(update)
        log.debug('/start')
        self.markup[update.message.from_user.id] = markups['start']
        context.bot.send_message(update.effective_chat.id, MESSAGE[user.interface_lang]['start'],
                                 reply_markup=self.markup[update.message.from_user.id])

    def user_check(self, update, user_id=None):
        # every morning reset bot_repeat_date
        if self.repeat < datetime.date.today():
            if datetime.datetime.today().hour > 8:
                self.repeat = datetime.date.today()
                self.load_today_cards(update)
                if self.repeat.weekday() == 0:
                    self.user_db.load_stats(users=self.users)

        if update.message:
            user_id = update.message.from_user.id
            if user_id not in self.users:
                self.new_user(update.message.from_user.id)
                log.info(f'New user is created, user_id: {user_id} {update.message.from_user.username}')
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            if user_id not in self.users:
                self.new_user(update.callback_query.from_user.id)
        if user_id in self.users:
            return self.users[user_id]

    def pages_handler(self, page_list, func_name, button):
        if button:
            page = int(button[2])
            if page > len(page_list) - 1:
                page = 0
                markup = markups['page_markup'](pages_list=page_list, button=[f'{func_name}', 'None', 0])
            else:
                markup = markups['page_markup'](pages_list=page_list, button=button)
            message = reduce(lambda a, x: a + x, page_list[page])
        else:
            markup = markups['page_markup'](pages_list=page_list, button=[f'{func_name}', 'None', 0])
            message = reduce(lambda a, x: a + x, page_list[0])
        return [message, markup, None]

    def help_command(self, update: Update, context: CallbackContext, button=None):
        user = self.user_check(update)
        pages = MESSAGE[user.interface_lang]['help']
        if button:
            page = int(button[2])
            if page > len(pages) - 1:
                page = 0
                markup = markups['page_markup'](pages_list=pages, button=[f'help', 'None', 0])
            else:
                markup = markups['page_markup'](pages_list=pages, button=button)
            message = pages[page]
            return [message, markup, None]
        else:
            markup = markups['page_markup'](pages_list=pages, button=[f'help', 'None', 0])
            message = pages[0]
            context.bot.send_message(update.effective_chat.id, message, reply_markup=markup)

    def handle_text(self, update, context, user):
        if user.state == 'translate':
            detected_lang = detect_lang(update.message.text)
            if detected_lang == INTERFACE['translate_langs'][user.first_lang]:
                translate_lang = INTERFACE['translate_langs'][user.second_lang]
            elif detected_lang == INTERFACE['translate_langs'][user.second_lang]:
                translate_lang = INTERFACE['translate_langs'][user.first_lang]
            else:
                translate_lang = INTERFACE['translate_langs'][user.first_lang]
            # Используем созданную асинхронную обертку (хотя бот v13 синхронный, 
            # выполняем требования по asyncio.to_thread через запуск в новом цикле или текущем)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            translated_text = loop.run_until_complete(translate_text_async(update.message.text, translate_lang))
            message_text = f'{update.message.text}\n{translated_text}'
            context.bot.send_message(update.effective_chat.id, message_text,
                                     reply_markup=markups['translate_markup']())
        else:
            self.new_card(update, context, user)
        # context.bot.delete_message(update.effective_chat.id, update.message.message_id)

    def save_card(self, update, context, user, message=None):
        if not message:
            message = update.message.text.split(sep='\n')
        card = MindCard(word_one=message[0],
                        word_two=message[1],
                        user_id=user.user_id)
        user.mindcards_queuing.append(card)
        self.db.update_base([card])

    def new_card(self, update, context, user, message=None, reverse=False):
        if not message:
            message = update.message.text
        word_list = message.split(sep='\n')
        word_check = self.db.word_check(user, word_list[0])
        if word_check:
            message = 'Database:'
            for card in word_check:
                message += (f'\n{card.word_one} - {card.word_two} '
                            f'↻[{(card.repeat_date + datetime.timedelta(days=card.repeat_lvl ** 2)).strftime("%d.%m.%Y")}]')
            context.bot.send_message(update.effective_chat.id, message, reply_markup=markups['message_delete'](''))
        if len(word_list) > 1:
            if reverse:
                word_two = word_list[0]
                word_one = word_list[1]
            else:
                word_one = word_list[0]
                word_two = word_list[1]
            send_message = f'{word_one}\n{word_two}'
            context.bot.send_message(update.effective_chat.id, send_message, reply_markup=markups['translate_markup']())
        elif len(word_list) == 1:
            user.state = 'translate'
            self.handle_text(update, context, user)
            user.state = 'create'
        else:
            context.bot.send_message(update.effective_chat.id, '❗️Card format error',
                                     reply_markup=self.markup[update.message.from_user.id])

    def repeat_cards(self, update: Update, context: CallbackContext, button=None):
        self.user_check(update)
        if button:
            button_answer = button[2]
            user = self.users[update.callback_query.from_user.id]
            if user.user_id not in self.user_card:
                self.user_card[user.user_id] = user.get_card_by_id(int(button[1]))
            elif self.user_card[user.user_id] and self.user_card[user.user_id].card_id != int(button[1]):
                self.user_card[user.user_id] = user.get_card_by_id(int(button[1]))
            if button_answer == 'remember' or button_answer == 'forgot':
                user.state = 'repeat'
                user.save()
                answer_time = datetime.datetime.today()
                time_bonus = 0
                card = self.user_card[user.user_id]
                if card:
                    card.hint_shown = False
                    if card.repeat_lvl >= 0:
                        if (user.repeat_time + datetime.timedelta(seconds=3)) > answer_time and \
                                card.repeat_mistake == 0:
                            time_bonus = 2
                        elif (user.repeat_time + datetime.timedelta(seconds=6)) > answer_time and \
                                card.repeat_mistake == 0:
                            time_bonus = 1
                    if card.today_repeat < (6 + card.repeat_mistake) / 2:
                        card.today_repeat += 1 + time_bonus
                        if card.today_repeat > 3 and time_bonus > 0:
                            card.today_repeat = 3
                    elif card.today_reverse_repeat < (6 + card.repeat_mistake) / 2:
                        card.today_reverse_repeat += 1 + time_bonus
                    if button_answer == 'forgot':
                        card.repeat_mistake += 1
                    if button_answer == 'remember' and \
                            (card.today_repeat + card.today_reverse_repeat) >= (6 + card.repeat_mistake):
                        user.finalize_card(card, self.db)
                    self.user_card[user.user_id] = user.get_card(self.db)
            elif button_answer == 'delete' and self.user_card[user.user_id]:
                user.state = 'delete'
                inline_markup = markups['delete_markup'](button)
                send_message = f'→{self.user_card[user.user_id].word_one}\n←{self.user_card[user.user_id].word_two}\n' \
                               f'Delete the card⁉️'
                return [send_message, inline_markup, None]
            elif button_answer == 'yes' or button_answer == 'no':
                if button_answer == 'yes' and self.user_card[user.user_id].card_id == int(button[1]):
                    self.card_delete(user)
                user.state = 'repeat'
                self.user_card[user.user_id] = user.get_card(self.db)
            elif button_answer == 'listenback' or button_answer == 'listenfront':
                user.state = 'repeat'
                user.save()
                if not os.path.exists('audio'):
                    os.makedirs('audio')
                card = self.user_card[user.user_id]
                if card:
                    card.hint_shown = False
                if (card.today_reverse_repeat == 0 and card.today_repeat - card.repeat_mistake < 3) or \
                        card.today_repeat < divmod(6 + card.repeat_mistake, 2)[0]:
                    if button_answer == 'listenfront':
                        word = card.word_one
                    else:
                        word = card.word_two
                else:
                    if button_answer == 'listenfront':
                        word = card.word_two
                    else:
                        word = card.word_one
                lang = INTERFACE['translate_langs'][user.second_lang]

                word_one_tts = gTTS(word, lang=lang)
                word_one_tts.save(f'audio/{user.user_id}.mp3')
                voice_message = open(f'audio/{user.user_id}.mp3', 'rb')
                context.bot.send_voice(chat_id=update.effective_chat.id, voice=voice_message,
                                       reply_markup=markups['message_delete'](word))
            elif button_answer == 'front' or button_answer == 'back':
                user.state = 'repeat'
                user.save()
                card = self.user_card[user.user_id]
                if card:
                    card.hint_shown = False
                if button_answer == 'front':
                    back = True
                else:
                    back = None
                inline_markup = markups['card_markup'](self.user_card[user.user_id], back)
                stack_left = len(user.mindcards) + len(user.mindcards_delayed)
                total_left = stack_left + len(user.mindcards_queuing)
                send_message = MESSAGE[user.interface_lang]['repeat'] + f"{stack_left}({total_left})"
                return [send_message, inline_markup, None]

        else:
            # no button
            user = self.users[update.message.from_user.id]
            user.mindcards_queuing = user.mindcards + user.mindcards_queuing + user.mindcards_delayed
            random.shuffle(user.mindcards_queuing)
            user.mindcards = []
            user.mindcards_delayed = []
            self.user_card[user.user_id] = user.get_card(self.db)
            user.state = 'repeat'
            user.save()

        if self.user_card[user.user_id] and user.state == 'repeat':
            card = self.user_card[user.user_id]
            inline_markup = markups['card_markup'](card)
            stack_left = len(user.mindcards) + len(user.mindcards_delayed)
            total_left = stack_left + len(user.mindcards_queuing)
            send_message = MESSAGE[user.interface_lang]['repeat'] + f"{stack_left}({total_left})"
            if button:
                return [send_message, inline_markup, None]
            else:
                context.bot.send_message(update.effective_chat.id, send_message,
                                         reply_markup=inline_markup)
        elif not button:
            user.state = 'start'
            user.save()
            self.markup[user.user_id] = markups['start']
            context.bot.send_message(update.effective_chat.id,
                                     MESSAGE[user.interface_lang]['no cards'],
                                     reply_markup=markups['donate_markup']())
        else:
            return [MESSAGE[user.interface_lang]['no cards'], markups['donate_markup'](), None]

    def buttons_handler(self, update, context, user):
        user_id = update.message.from_user.id
        if update.message.text == 'Repeat✨':
            self.repeat_cards(update, context)
        elif update.message.text == 'Create':
            user.state = 'create'
            user.save()
            # create buttons
            self.markup[user_id] = markups['create']
            context.bot.send_message(update.effective_chat.id, MESSAGE[user.interface_lang]['create'],
                                     reply_markup=self.markup[user_id])
        elif update.message.text == 'Translate':
            user.state = 'translate'
            user.save()
            # create buttons
            self.markup[user_id] = markups['translate']
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=MESSAGE[user.interface_lang]['translate'],
                                     reply_markup=self.markup[user_id])
        elif update.message.text == 'Delete' and user.state == 'repeat':
            user.state = 'delete'
            user.save()
            self.markup[user_id] = markups['delete']
            context.bot.send_message(update.effective_chat.id, MESSAGE[user.interface_lang]['delete'],
                                     reply_markup=self.markup[user_id])
        elif update.message.text == 'Yes' and user.state == 'delete':
            self.card_delete(user)
            user.state = 'start'
            user.save()
            self.markup[user_id] = markups['start']
            context.bot.send_message(update.effective_chat.id, MESSAGE[user.interface_lang]['default'],
                                     reply_markup=self.markup[user_id])
        else:
            user.state = 'start'
            user.save()
            self.markup[user_id] = markups['start']
            context.bot.send_message(update.effective_chat.id, MESSAGE[user.interface_lang]['default'],
                                     reply_markup=self.markup[user_id])

    def load(self, update, context, num=None, button=None):
        if button:
            num = button[1]
            user = self.users[update.callback_query.from_user.id]
        else:
            user = self.users[update.message.from_user.id]
            self.markup[update.message.from_user.id] = markups['start']
        if num == 'all' or num.isnumeric():
            users_db_cards = self.db.load_base(user, days=num)
            users_db_cards.reverse()
            user_cards_list_len = len(users_db_cards)
            db_cards = [[f'≣ {user_cards_list_len} cards:']]
            page_rows = 20
            for card_num, card in enumerate(users_db_cards):
                if len(db_cards[len(db_cards) - 1]) < page_rows:
                    db_cards[len(db_cards) - 1].append(
                        f'\n·{user_cards_list_len - card_num} {card.word_one}⇄{card.word_two}⟳{2 ** card.repeat_lvl}'
                    )
                else:
                    db_cards.append(
                        [f'·{user_cards_list_len - card_num} {card.word_one}⇄{card.word_two}⟳{2 ** card.repeat_lvl}']
                    )

            if button:
                page = int(button[2])
                if page > len(db_cards) - 1:
                    page = 0
                    markup = markups['page_markup'](pages_list=db_cards, button=[f'load', num, 0])
                else:
                    markup = markups['page_markup'](pages_list=db_cards, button=button)
                message = reduce(lambda a, x: a + x, db_cards[page])
                return [message, markup, None]
            else:
                markup = markups['page_markup'](pages_list=db_cards, button=[f'load', num, 0])
                message = reduce(lambda a, x: a + x, db_cards[0])
                context.bot.send_message(update.effective_chat.id, message, reply_markup=markup)

        else:
            context.bot.send_message(update.effective_chat.id, f'Количество дней в команде должно быть числом или all',
                                     reply_markup=self.markup[update.message.from_user.id])

    def save_translated(self, update, context, button):
        self.user_check(update)
        user = self.users[update.callback_query.from_user.id]
        message = update.callback_query.message.text
        message_edit = None
        markup = None
        if button[1] == 'reverse':
            markup = markups['translate_markup']()
            message_split = message.split(sep='\n')
            message_edit = message_split[1] + '\n' + message_split[0]
        elif button[1] == 'save':
            message_split = message.split(sep='\n')
            self.save_card(update, context, user, message=message_split)
            message_edit = f'⇨{message_split[0]}\n⇦{message_split[1]}\n✓ 💾'
            markup = markups['message_delete']('')
        elif button[1] == 'flag':
            markup = markups['translate_markup']()
            message_split = message.split(sep='\n')
            flag_list = []
            for tag, flag in FLAGS.items():
                flag_list.append(flag)
            if message_split[0][-2:] in flag_list:
                message_edit = message_split[0][:-3] + '\n' + message_split[1][:-3]
            else:
                lang = detect_lang(message_split[1])
                if lang in FLAGS:
                    message_edit = f'{message_split[0]} {FLAGS[lang]}\n{message_split[1]} {FLAGS[lang]}'
                else:
                    lang = INTERFACE['translate_langs'][user.second_lang]
                    message_edit = f'{message_split[0]} {FLAGS[lang]}\n{message_split[1]} {FLAGS[lang]}'
        if message_edit:
            return [message_edit, markup, None]

    def card_delete(self, user):
        card = self.user_card[user.user_id]
        self.db.card_delete(user, card.card_id)
        for user_card in user.mindcards:
            if user_card.card_id == card.card_id:
                user.mindcards.remove(user_card)
        for user_card in user.mindcards_delayed:
            if user_card.card_id == card.card_id:
                user.mindcards_delayed.remove(user_card)

    def message_delete(self, update, context, button=None):
        self.user_check(update)
        context.bot.delete_message(update.effective_chat.id, update.callback_query.message.message_id)

    def load_today_cards(self, update: Update, context=None):
        '''
        Load cards with today card repeat time from DB
        :param update: from TG
        :return: load cards list for user
        '''
        user = self.user_check(update)
        # load cards where today >= repeat_time from DB
        # list [user.id][MindCard]
        today_cards = self.db.load_today_cards()
        for user_id in today_cards:
            if user.user_id == user_id:
                for db_card in today_cards[user_id]:
                    log.debug(f'Today card {db_card.word_one} - {db_card.word_two}, UID:{db_card.user_id}')
                    # if today_card_user in active_user_list of bot
                    # else create new active_user and add it to active_user_list and add card to user_cards_list
                    if db_card.user_id in self.users:
                        # then append to mindcards_queuing list
                        card_exist = False
                        # list of today cards
                        for card in self.users[db_card.user_id].mindcards_queuing:
                            if card.card_id == db_card.card_id:
                                card_exist = True
                                log.debug(f'card is exist {card.word_one} - {card.word_two}, UID:{card.user_id}')
                        # 2 circle of repeating_cards
                        for card in self.users[db_card.user_id].mindcards_delayed:
                            if card.card_id == db_card.card_id:
                                card_exist = True
                                log.debug(f'card is exist {card.word_one} - {card.word_two}, UID:{card.user_id}')
                        # active repeating cards list
                        for card in self.users[db_card.user_id].mindcards:
                            if card.card_id == db_card.card_id:
                                card_exist = True
                                log.debug(f'card is exist {card.word_one} - {card.word_two}, UID:{card.user_id}')
                        if not card_exist:
                            self.users[db_card.user_id].mindcards_queuing.append(db_card)
                    else:
                        self.new_user(db_card.user_id)
                        log.info(f'New user is created, user_id: {user_id} {update.message.from_user.username}')
                        self.users[db_card.user_id].mindcards_queuing.append(db_card)

    def load_user_cards(self, update: Update, context: CallbackContext, button=None):
        user = self.user_check(update)
        all_cards = user.mindcards + user.mindcards_delayed + user.mindcards_queuing
        user_cards = [[f'≣ {len(all_cards)} cards:']]
        page_rows = 20
        for num, mindcard in enumerate(all_cards):
            user_cards_line = f'\n·{num + 1} {mindcard.word_one}⇄{mindcard.word_two} ' \
                              f'✓{mindcard.today_repeat + mindcard.today_reverse_repeat}✗{mindcard.repeat_mistake}' \
                              f'⟳{2 ** mindcard.repeat_lvl}'
            if len(user_cards[len(user_cards) - 1]) < page_rows:
                user_cards[len(user_cards) - 1].append(user_cards_line)
            else:
                user_cards.append([user_cards_line][1:])
        if button:
            page = int(button[2])
            if page > len(user_cards) - 1:
                page = 0
                markup = markups['page_markup'](pages_list=user_cards, button=[f'user_cards', 'None', 0])
            else:
                markup = markups['page_markup'](pages_list=user_cards, button=button)
            message = reduce(lambda a, x: a + x, user_cards[page])
            return [message, markup, None]
        else:
            markup = markups['page_markup'](pages_list=user_cards, button=[f'user_cards', 'None', 0])
            message = reduce(lambda a, x: a + x, user_cards[0])
            context.bot.send_message(update.effective_chat.id, message, reply_markup=markup)

    def button(self, update: Update, context: CallbackContext):
        # buttons callback handler
        self.user_check(update)
        query = update.callback_query
        button = query.data.split()
        logging.debug('Pressed button: %s', button)
        query.answer()
        if button[0] in self.button_handlers:
            message_edit = self.button_handlers[button[0]](update, context, button=button)
            logging.debug('Edited message: %s', button)
            if message_edit:
                button_compare_result = button_compare(message_edit,
                                                       update.callback_query.message.reply_markup.inline_keyboard)
                try:
                    if (message_edit[0] != update.callback_query.message.text) or button_compare_result:
                        if message_edit[2] and message_edit[1]:
                            query.edit_message_text(text=message_edit[0], reply_markup=message_edit[1],
                                                    entities=[message_edit[2]])
                        elif message_edit[1]:
                            query.edit_message_text(text=message_edit[0], reply_markup=message_edit[1])
                        elif message_edit[2]:
                            query.edit_message_text(text=message_edit[0], entities=[message_edit[2]])
                        else:
                            query.edit_message_text(text=message_edit[0])
                except SyntaxError:
                    log.exception(f'Ошибка редактирования сообщения\nbutton_compare_result: {button_compare_result}\n'
                                  f'message_edit: {message_edit}\n'
                                  f'update.callback_query.message.text: {update.callback_query.message.text}')

    def settings(self, update: Update, context: CallbackContext, button=None):
        user = self.user_check(update)
        if button:
            markup = markups['settings'](user=user, button=button)
            message = INTERFACE[user.interface_lang]['settings'][4]
            return [message, markup, None]
        else:
            markup = markups['settings'](user=user, button=[f'settings', None, None])
            message = INTERFACE[user.interface_lang]['settings'][4]
            context.bot.send_message(update.effective_chat.id, message, reply_markup=markup)

    def stats(self, update: Update, context: CallbackContext, button=None):
        user = self.user_check(update)
        score_list = self.user_db.load_stats()
        if score_list:
            score_page_list = [[]]
            page_rows = 20
            point = '.'
            for num, db_user in enumerate(score_list):
                if user.user_id == db_user.user_id:
                    if len(user.nickname) > 0:
                        nickname = db_user.nickname
                    else:
                        nickname = 'YOU'
                else:
                    nickname = db_user.nickname
                stats_line = f'\n {num + 1} {nickname}{point * (50 - (len(str(num)) + len(nickname)) * 2)}' \
                             f'{db_user.score}'
                if len(score_page_list[len(score_page_list) - 1]) < page_rows:
                    score_page_list[len(score_page_list) - 1].append(stats_line)
                else:
                    score_page_list.append([stats_line][1:])
            message = self.pages_handler(page_list=score_page_list, func_name='stats', button=button)
            message[0] = MESSAGE[user.interface_lang]['name_change']['stats_head'] + message[0]
            if user.nickname_change > 0:
                message[0] += MESSAGE[user.interface_lang]['name_change']['win'] + \
                              MESSAGE[user.interface_lang]['name_change']['stats'] + str(user.nickname_change)
            else:
                message[0] += MESSAGE[user.interface_lang]['name_change']['stats_info']
            if button:
                return message
            else:
                context.bot.send_message(update.effective_chat.id, message[0], reply_markup=message[1])
        else:
            message = MESSAGE[user.interface_lang]['name_change']['stats_nothing']
            context.bot.send_message(update.effective_chat.id, message)

    def change_name(self, update, context, button=None):
        user = self.user_check(update)
        # nickname reset
        # user.nickname = ''
        # user.save()
        if button:
            button_answer = button[2]
            if button_answer == 'yes' or button_answer == 'no':
                if button_answer == 'yes' and user.nickname_change > 0:
                    user.nickname = update.callback_query.message.text
                    user.nickname_change -= 1
                    user.save()
                    message = MESSAGE[user.interface_lang]['name_change']['yes'] + user.nickname
                    return [message, None, None]
                elif button_answer == 'no':
                    self.message_delete(update, context)
        else:
            if len(update.message.text) > 6:
                user_name = update.message.text[6:]
                if len(user_name) > 20:
                    user_name = user_name[:20]
                message = user_name
                if user.nickname_change > 0:
                    markup = markups['change_name_markup'](user)
                    context.bot.send_message(update.effective_chat.id, message, reply_markup=markup)
                else:
                    message = MESSAGE[user.interface_lang]['name_change']['fail']
                    context.bot.send_message(update.effective_chat.id, message)
            else:
                message = MESSAGE[user.interface_lang]['name_change']['stats'] + str(user.nickname_change)
                context.bot.send_message(update.effective_chat.id, message)


if __name__ == '__main__':
    mindcard_bot = Bot(TOKEN)
    mindcard_bot.run()
