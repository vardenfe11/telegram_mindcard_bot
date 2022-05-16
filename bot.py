import datetime
import logging
import os
import random
from functools import reduce
from gtts import gTTS
from langdetect import detect

from markups import markups, page_markup, card_markup, translate_markup, delete_markup
from googletrans import Translator
from db_manager import DataBaseUpdater
from db_manager import MindCard
from settings import MESSAGE
from telegram_token import TOKEN
from collections import defaultdict

from telegram import Update, MessageEntity
from telegram.ext import Updater
from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram.ext import CallbackContext, CallbackQueryHandler

try:
    from telegram_token import *
except ImportError:
    exit('Скопируйте telegram_token.py.deafault как telegram_token.py и укажите в нем токен')

translator = Translator()

log = logging.getLogger()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
log.addHandler(stream_handler)
log.setLevel(logging.DEBUG)
stream_handler.setLevel(logging.INFO)


def def_value():
    return User(0)


class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.mindcards = []
        self.mindcards_delayed = []
        self.state = ''
        self.repeat_time = datetime.datetime.today()
        self.db_cards = None

    def get_card_by_id(self, card_id):
        for card in self.mindcards:
            if card.card_id == card_id:
                return card
        for card in self.mindcards_delayed:
            if card.card_id == card_id:
                return card

    def get_card(self, db):
        # two cards list for get all cards after repeat its again
        while len(self.mindcards) > 0 or len(self.mindcards_delayed) > 0:
            if len(self.mindcards) == 0 and len(self.mindcards_delayed) > 0:
                self.mindcards = self.mindcards_delayed
                self.mindcards_delayed = []
            card = random.choice(self.mindcards)
            if (card.today_repeat + card.today_reverse_repeat) < (6 + card.repeat_mistake):
                self.mindcards_delayed.append(card)
                self.mindcards.remove(card)
                self.repeat_time = datetime.datetime.today()
                return card
            else:
                if card.repeat_mistake < 2 and card.repeat_lvl < 4:
                    card.repeat_lvl += 1
                db.update_base([card])
                self.mindcards.remove(card)


def default_markup():
    return markups['start']


class Bot:
    def __init__(self, token):
        self.users = defaultdict(def_value)
        self.user_card = {}
        self.bot = Updater(token=token)
        self.markup = defaultdict(default_markup)
        self.db = DataBaseUpdater()
        self.repeat = datetime.date.today()
        self.button_handlers = {
            'load': self.load,
            'repeat_cards': self.repeat_cards,
            'save_translated': self.save_translated,
            'user_cards': self.load_user_cards,
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
        dispatcher.add_handler(CallbackQueryHandler(self.button))
        dispatcher.add_handler(MessageHandler(Filters.text, self.handle_messages))
        updater.start_polling()

    def handle_messages(self, update: Update, context: CallbackContext):
        self.user_check(update)
        try:
            log.debug('обнаружен ивент: %s', update.message.text)
            self.on_event(update, context)
        except Exception as error:
            log.exception(f'Ошибка при получении ивента: {error}')

    def new_user(self, user_id):
        """
        :return: create new user for keeping repeating cards, load cards from database for the user id
        """
        user = User(user_id)
        self.users[user_id] = user
        users_db_cards = self.db.load_base(user)
        if users_db_cards:
            self.users[user_id].mindcards = users_db_cards
        log.info('New user is created, user_id: %s', user_id)

    def on_event(self, update, context):
        if self.repeat < datetime.date.today():
            if datetime.datetime.today().hour > 8:
                self.repeat = datetime.date.today()
                self.load_today_cards(update, context)
                self.send_today_cards()
        user_id = update.message.from_user.id
        if update:
            if user_id not in self.users:
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
                self.db.card_delete(user, num)
            elif not button_click:
                self.handle_text(update, context, user)

    def start(self, update: Update, context: CallbackContext):
        self.user_check(update)
        log.debug('/start')
        self.markup[update.message.from_user.id] = markups['start']
        context.bot.send_message(update.effective_chat.id, MESSAGE['start'],
                                 reply_markup=self.markup[update.message.from_user.id])

    def user_check(self, update, user_id=None):
        if update.message:
            user_id = update.message.from_user.id
            if user_id not in self.users:
                self.new_user(update.message.from_user.id)
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            if user_id not in self.users:
                self.new_user(update.callback_query.from_user.id)
        if user_id in self.users:
            return self.users[user_id]

    def help_command(self, update: Update, context: CallbackContext):
        self.user_check(update)
        self.markup[update.message.from_user.id] = markups['start']
        context.bot.send_message(update.effective_chat.id, MESSAGE['help'],
                                 reply_markup=self.markup[update.message.from_user.id])

    def handle_text(self, update, context, user):
        if user.state == 'translate':
            translated_message = translator.translate(update.message.text, dest='ru')
            message_text = f'{update.message.text}\n{translated_message.text}'
            context.bot.send_message(update.effective_chat.id, message_text,
                                     reply_markup=translate_markup())
        elif user.state == 'create':
            self.new_card(update, context, user)
        else:
            self.start(update, context)

    def new_card(self, update, context, user, message=None, reverse=False):
        send_saved_card = False
        if not message:
            message = update.message.text
            send_saved_card = True
        word_list = message.split(sep='\n')
        print(word_list, message)
        if len(word_list) > 1:
            if reverse:
                word_two = word_list[0]
                word_one = word_list[1]
            else:
                word_one = word_list[0]
                word_two = word_list[1]
            card = MindCard(word_one=word_one,
                            word_two=word_two,
                            user_id=user.user_id)
            user.mindcards.append(card)
            self.db.update_base([card])
            if send_saved_card:
                send_message = f'✔ Saved 1️⃣{word_one}2️⃣{word_two}\n'
                context.bot.send_message(update.effective_chat.id, send_message,
                                         reply_markup=self.markup[update.message.from_user.id])
        else:
            context.bot.send_message(update.effective_chat.id, 'Card format error',
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
                answer_time = datetime.datetime.today()
                time_bonus = 0
                card = self.user_card[user.user_id]
                if card:
                    if card.repeat_lvl > 0:
                        if (user.repeat_time + datetime.timedelta(seconds=2)) > answer_time and \
                                card.repeat_mistake == 0:
                            time_bonus = 2
                        elif (user.repeat_time + datetime.timedelta(seconds=4)) > answer_time and \
                                card.repeat_mistake == 0:
                            time_bonus = 1
                    if card.today_repeat < \
                            (3 + card.repeat_mistake / 2):
                        card.today_repeat += 1 + time_bonus
                    elif card.today_reverse_repeat < \
                            (3 + card.repeat_mistake / 2):
                        card.today_reverse_repeat += 1 + time_bonus
                    if button_answer == 'forgot':
                        card.repeat_mistake += 1
                    self.user_card[user.user_id] = user.get_card(self.db)
            elif button_answer == 'delete' and self.user_card[user.user_id]:
                user.state = 'delete'
                inline_markup = delete_markup(button)
                send_message = f'{self.user_card[user.user_id].word_one}\n{self.user_card[user.user_id].word_two}\n' \
                               f'Delete the card⁉️'
                return [send_message, inline_markup, None]
            elif button_answer == 'yes' or button_answer == 'no':
                if button_answer == 'yes' and self.user_card[user.user_id].card_id == int(button[1]):
                    self.card_delete(user)
                user.state = 'repeat'
                self.user_card[user.user_id] = user.get_card(self.db)
            elif button_answer == 'listen' and self.user_card[user.user_id]:
                if not os.path.exists('audio'):
                    os.makedirs('audio')
                lang = detect(self.user_card[user.user_id].word_one)
                supported_langs = ['ru', 'uk', 'en']
                if lang not in supported_langs:
                    lang = 'en'
                word_one_tts = gTTS(self.user_card[user.user_id].word_one, lang=lang)
                word_one_tts.save(f'audio/{user.user_id}.mp3')
                voice_message = open(f'audio/{user.user_id}.mp3', 'rb')
                context.bot.send_voice(chat_id=update.effective_chat.id, voice=voice_message)
        else:
            user = self.users[update.message.from_user.id]
            self.user_card[user.user_id] = user.get_card(self.db)
            user.state = 'repeat'

        if self.user_card[user.user_id] and user.state == 'repeat':
            card = self.user_card[user.user_id]
            inline_markup = card_markup(card)
            if (card.today_repeat - card.repeat_mistake / 2) < 3:
                word_one, word_two = card.word_one, card.word_two
            else:
                word_two, word_one = card.word_one, card.word_two
            # message text
            send_message = f'{word_one}\n{word_two}'
            # create entities for another card side spoiler
            # encode to utf-16 because telegram use it for text length
            tg_len_word_one = int(len(word_one.encode('utf-16-le')) / 2)
            tg_len_word_two = int(len(word_two.encode('utf-16-le')) / 2)
            entities = MessageEntity(offset=tg_len_word_one + 1,
                                     length=tg_len_word_two, type='spoiler')
            if button:
                return [send_message, inline_markup, entities]
            else:
                context.bot.send_message(update.effective_chat.id, send_message, entities=[entities],
                                         reply_markup=inline_markup)
        elif not button:
            user.state = 'start'
            self.markup[user.user_id] = markups['start']
            context.bot.send_message(update.effective_chat.id,
                                     MESSAGE['no cards'],
                                     reply_markup=self.markup[user.user_id])
        else:
            return [MESSAGE['no cards'], None, None]

    def buttons_handler(self, update, context, user):
        user_id = update.message.from_user.id
        if update.message.text == 'Repeat':
            self.repeat_cards(update, context)
        elif update.message.text == 'Create':
            user.state = 'create'
            # create buttons
            self.markup[user_id] = markups['create']
            context.bot.send_message(update.effective_chat.id, MESSAGE['create'],
                                     reply_markup=self.markup[user_id])
        elif update.message.text == 'Translate':
            user.state = 'translate'
            # create buttons
            self.markup[user_id] = markups['translate']
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=MESSAGE['translate'],
                                     reply_markup=self.markup[user_id])
        elif update.message.text == 'Delete' and user.state == 'repeat':
            user.state = 'delete'
            self.markup[user_id] = markups['delete']
            context.bot.send_message(update.effective_chat.id, MESSAGE['delete'],
                                     reply_markup=self.markup[user_id])
        elif update.message.text == 'Yes' and user.state == 'delete':
            self.card_delete(user)
            user.state = 'start'
            self.markup[user_id] = markups['start']
            context.bot.send_message(update.effective_chat.id, MESSAGE['default'],
                                     reply_markup=self.markup[user_id])
        else:
            user.state = 'start'
            self.markup[user_id] = markups['start']
            context.bot.send_message(update.effective_chat.id, MESSAGE['default'],
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
            db_cards = [[f'{len(users_db_cards)} cards:']]
            page_rows = 20
            for card in users_db_cards:
                if len(db_cards[len(db_cards) - 1]) < page_rows:
                    db_cards[len(db_cards) - 1].append(
                        f'\nid:{card.card_id}:{card.word_one}-{card.word_two} lvl:{card.repeat_lvl}')
                else:
                    db_cards.append([f'id:{card.card_id}:{card.word_one}-{card.word_two} lvl:{card.repeat_lvl}'])

            if button:
                page = int(button[2])
                if page > len(db_cards) - 1:
                    page = 0
                    markup = page_markup(pages_list=db_cards, button=[f'load', num, 0])
                else:
                    markup = page_markup(pages_list=db_cards, button=button)
                message = reduce(lambda a, x: a + x, db_cards[page])
                return [message, markup, None]
            else:
                markup = page_markup(pages_list=db_cards, button=[f'load', num, 0])
                message = reduce(lambda a, x: a + x, db_cards[0])
                context.bot.send_message(update.effective_chat.id, message, reply_markup=markup)

        else:
            context.bot.send_message(update.effective_chat.id, f'Количество дней в команде должно быть числом или all',
                                     reply_markup=self.markup[update.message.from_user.id])

    def save_translated(self, update, context, button):
        self.user_check(update)
        user = self.users[update.callback_query.from_user.id]
        message = update.callback_query.message.text
        if button[1] == 'reverse':
            markup = translate_markup()
            message_split = message.split(sep='\n')
            message_edit = message_split[1] + '\n' + message_split[0]
        else:
            self.new_card(update, context, user, message=message)
            message_edit = message + '\n✔ Saved'
            markup = None
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

    def load_today_cards(self, update: Update, context: CallbackContext):
        self.user_check(update)
        today_cards = self.db.load_today_cards()
        for user_id in today_cards:
            for db_card in today_cards[user_id]:
                log.debug(f'Today card {db_card.word_one} - {db_card.word_two}, UID:{db_card.user_id}')
                if db_card.user_id in self.users:
                    card_exist = False
                    for card in self.users[db_card.user_id].mindcards_delayed:
                        if card.card_id == db_card.card_id:
                            card_exist = True
                            log.debug(f'card is exist {card.word_one} - {card.word_two}, UID:{card.user_id}')
                    for card in self.users[db_card.user_id].mindcards:
                        if card.card_id == db_card.card_id:
                            card_exist = True
                            log.debug(f'card is exist {card.word_one} - {card.word_two}, UID:{card.user_id}')
                            # self.users[db_card.user_id].mindcards.remove(card)
                    if not card_exist:
                        self.users[db_card.user_id].mindcards.append(db_card)
                else:
                    self.new_user(db_card.user_id)
                    self.users[db_card.user_id].mindcards.append(db_card)

    def send_today_cards(self):
        pass

    def load_user_cards(self, update: Update, context: CallbackContext, button=None):
        user = self.user_check(update)
        user_cards = [[f'{len(user.mindcards)} cards:']]
        page_rows = 20
        for mindcard in user.mindcards + user.mindcards_delayed:
            user_cards_line = f'\n{mindcard.card_id}: {mindcard.word_one} - {mindcard.word_two} ' \
                              f'{mindcard.today_repeat}|{mindcard.today_reverse_repeat}|{mindcard.repeat_mistake}'
            if len(user_cards[len(user_cards) - 1]) < page_rows:
                user_cards[len(user_cards) - 1].append(user_cards_line)
            else:
                user_cards.append([user_cards_line][1:])
        if button:
            page = int(button[2])
            if page > len(user_cards) - 1:
                page = 0
                markup = page_markup(pages_list=user_cards, button=[f'user_cards', 'None', 0])
            else:
                markup = page_markup(pages_list=user_cards, button=button)
            message = reduce(lambda a, x: a + x, user_cards[page])
            return [message, markup, None]
        else:
            markup = page_markup(pages_list=user_cards, button=[f'user_cards', 'None', 0])
            message = reduce(lambda a, x: a + x, user_cards[0])
            context.bot.send_message(update.effective_chat.id, message, reply_markup=markup)

    def button_compare(self, message_edit, keyboard2):
        button_coincidence = False
        if message_edit[1]:
            keyboard1 = message_edit[1].inline_keyboard
            if len(keyboard1) == len(keyboard2):
                for line_num, button_line in enumerate(keyboard2):
                    if len(keyboard1[line_num]) == len(button_line):
                        for num, button in enumerate(button_line):
                            if button.text != keyboard1[line_num][num].text or \
                                    button.callback_data != keyboard1[line_num][num].callback_data:
                                button_coincidence = True
        else:
            button_coincidence = True
        return button_coincidence

    def button(self, update: Update, context: CallbackContext):
        # buttons callback handler
        self.user_check(update)
        query = update.callback_query
        button = query.data.split()
        logging.info('Pressed button: %s', button)
        query.answer()
        if button[0] in self.button_handlers:
            message_edit = self.button_handlers[button[0]](update, context, button=button)
            logging.info('Edited message: %s', button)
            button_compare = self.button_compare(message_edit,
                                                 update.callback_query.message.reply_markup.inline_keyboard)
            if message_edit[0] != update.callback_query.message.text or button_compare:
                if message_edit[2] and message_edit[1]:
                    query.edit_message_text(text=message_edit[0], reply_markup=message_edit[1],
                                            entities=[message_edit[2]])
                elif message_edit[1]:
                    query.edit_message_text(text=message_edit[0], reply_markup=message_edit[1])
                elif message_edit[2]:
                    query.edit_message_text(text=message_edit[0], entities=[message_edit[2]])
                else:
                    query.edit_message_text(text=message_edit[0])



if __name__ == '__main__':
    mindcard_bot = Bot(TOKEN)
    mindcard_bot.run()
