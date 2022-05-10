import datetime
import logging
import random
from functools import reduce

from markups import markups, page_markup, card_markup, translate_markup
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
    def __init__(self, user_id, context=''):
        self.user_id = user_id
        self.mindcards = []
        self.mindcards_delayed = []
        self.state = ''
        self.context = context
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
                self.context = card.card_id
                self.mindcards_delayed.append(card)
                self.mindcards.remove(card)
                self.repeat_time = datetime.datetime.today()
                return card
            else:
                if card.repeat_mistake < 2 and card.card_id:
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
        # for event in messages:
        try:
            log.debug('обнаружен ивент: %s', update.message.text)
            self.on_event(update, context)
        except Exception as error:
            log.exception(f'Ошибка при получении ивента: {error}')

    def new_user(self, user_id):
        """
        :return: create new user for keeping repeating cards, load cards from database for the user id
        """
        # user_id = event.from_user.id
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
                self.db.card_delete(user, num)
            elif not button_click:
                self.handle_text(update, context, user)

    def start(self, update: Update, context: CallbackContext):
        self.user_check(update)
        log.debug('/start')
        self.markup[update.message.from_user.id] = markups['start']
        context.bot.send_message(update.effective_chat.id, MESSAGE['start'],
                                 reply_markup=self.markup[update.message.from_user.id])

    def user_check(self, update):
        if update.message:
            if update.message.from_user.id not in self.users:
                self.new_user(update.message.from_user.id)
        elif update.callback_query:
            if update.callback_query.from_user.id not in self.users:
                self.new_user(update.callback_query.from_user.id)

    def help_command(self, update: Update, context: CallbackContext):
        self.user_check(update)
        self.markup[update.message.from_user.id] = markups['start']
        context.bot.send_message(update.effective_chat.id, MESSAGE['help'],
                                 reply_markup=self.markup[update.message.from_user.id])

    def handle_text(self, update, context, user):
        if user.state == 'translate':
            translated_message = translator.translate(update.message.text, dest='ru')
            user.context = f'{update.message.text}\n{translated_message.text}'
            context.bot.send_message(update.effective_chat.id, user.context,
                                     reply_markup=translate_markup())
            # reply_markup=self.markup[update.message.from_user.id])
        elif user.state == 'create':
            self.new_card(update, context, user)
        else:
            self.start(update, context)

    def new_card(self, update, context, user, message=None, reverse=False):
        send_saved_card = False
        if not message:
            message = update.message.text
            send_saved_card = True
        break_num = message.find('\n')
        if break_num > 0:
            if reverse:
                word_two = message[:break_num]
                word_one = message[break_num + 1:]
            else:
                word_one = message[:break_num]
                word_two = message[break_num + 1:]
            card = MindCard(word_one=word_one,
                            word_two=word_two,
                            user_id=user.user_id)
            user.mindcards.append(card)
            self.db.update_base([card])
            if send_saved_card:
                send_message = f'Card |{message[:break_num]}/{message[break_num + 1:]}| is created\n'
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
            if button_answer == 'remember' or button_answer == 'forgot':
                if user.user_id not in self.user_card:
                    self.user_card[user.user_id] = user.get_card_by_id(int(button[1]))
                elif self.user_card[user.user_id] and self.user_card[user.user_id].card_id != int(button[1]):
                    self.user_card[user.user_id] = user.get_card_by_id(int(button[1]))
                answer_time = datetime.datetime.today()
                time_bonus = 0
                if self.user_card[user.user_id]:
                    if self.user_card[user.user_id].repeat_lvl > 0:
                        if (user.repeat_time + datetime.timedelta(seconds=2)) > answer_time and \
                                self.user_card[user.user_id].repeat_mistake == 0:
                            time_bonus = 2
                        elif (user.repeat_time + datetime.timedelta(seconds=4)) > answer_time and \
                                self.user_card[user.user_id].repeat_mistake == 0:
                            time_bonus = 1
                    if self.user_card[user.user_id].today_repeat < \
                            (3 + self.user_card[user.user_id].repeat_mistake / 2):
                        self.user_card[user.user_id].today_repeat += 1 + time_bonus
                    elif self.user_card[user.user_id].today_reverse_repeat < \
                            (3 + self.user_card[user.user_id].repeat_mistake / 2):
                        self.user_card[user.user_id].today_reverse_repeat += 1 + time_bonus
                    if button_answer == 'forgot':
                        self.user_card[user.user_id].repeat_mistake += 1
                    self.user_card[user.user_id] = user.get_card(self.db)
        else:
            user = self.users[update.message.from_user.id]
            self.user_card[user.user_id] = user.get_card(self.db)
        if self.user_card[user.user_id]:
            card = self.user_card[user.user_id]
            user.state = 'repeat'
            inline_markup = card_markup(card)
            if (card.today_repeat - card.repeat_mistake / 2) < 3:
                word_one, word_two = card.word_one, card.word_two
            else:
                word_two, word_one = card.word_one, card.word_two
            # message text
            send_message = f'{word_one}\n{word_two}'
            # create entities for another card side spoiler
            # encode to utf-16 because telegram use it
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

    # def send_card(self, update, context, card):
    #     log.debug(f'sending card {card.word_one}/{card.word_two}')
    #     # create buttons
    #     self.markup[update.message.from_user.id] = markups['send_card']
    #     # 3 time repeats for one card side and 3 for another
    #     if (card.today_repeat - card.repeat_mistake / 2) < 3:
    #         word_one, word_two = card.word_one, card.word_two
    #     else:
    #         word_two, word_one = card.word_one, card.word_two
    #     # message text
    #     send_message = f'{word_one}\n{word_two}'
    #     # create entities for another card side spoiler
    #     entities = MessageEntity(offset=len(word_one) + 1, length=len(word_two),
    #                              type='spoiler')
    #     context.bot.send_message(update.effective_chat.id, send_message, entities=[entities],
    #                              reply_markup=self.markup[update.message.from_user.id])
    #
    #     if self.users[update.message.from_user.id].state == 'repeat':
    #         context.bot.delete_message(update.effective_chat.id, update.message.message_id - 1)
    #         context.bot.delete_message(update.effective_chat.id, update.message.message_id - 2)
    #     log.debug(f'Send the card {word_one} - {word_two}, TR:{card.today_repeat}, TRR:{card.today_reverse_repeat}')

    def buttons_handler(self, update, context, user):
        user_id = update.message.from_user.id
        if update.message.text == 'Repeat':
            self.repeat_cards(update, context)
        elif update.message.text == 'Create from translated':
            self.new_card(update, context, user, message=user.context)
        elif update.message.text == 'Create':
            user.state = 'create'
            # create buttons
            self.markup[user_id] = markups['create']
            context.bot.send_message(update.effective_chat.id, MESSAGE['create'],
                                     reply_markup=self.markup[user_id])
        # elif update.message.text == 'Remember' or update.message.text == 'Forgot':
        #     answer_time = datetime.datetime.today()
        #     time_bonus = 0
        #     if self.user_card[user_id].repeat_lvl > -2:
        #         if (user.repeat_time + datetime.timedelta(seconds=2)) > answer_time and \
        #                 self.user_card[user_id].repeat_mistake == 0:
        #             time_bonus = 2
        #         elif (user.repeat_time + datetime.timedelta(seconds=4)) > answer_time and \
        #                 self.user_card[user_id].repeat_mistake == 0:
        #             time_bonus = 1
        #     if self.user_card[user_id].today_repeat < \
        #             (3 + self.user_card[user_id].repeat_mistake / 2):
        #         self.user_card[user_id].today_repeat += 1 + time_bonus
        #     elif self.user_card[user_id].today_reverse_repeat < \
        #             (3 + self.user_card[user_id].repeat_mistake / 2):
        #         self.user_card[user_id].today_reverse_repeat += 1 + time_bonus
        #     else:
        #         self.markup[user_id] = markups['start']
        #         context.bot.send_message(update.effective_chat.id, 'У карточки больше 3 повторений',
        #                                  reply_markup=self.markup[user_id])
        #     if update.message.text == 'Forgot':
        #         self.user_card[user_id].repeat_mistake += 1
        #     card = user.get_card(self.db)
        #     if card:
        #         self.user_card[user_id] = card
        #         self.send_card(update, context, card)
        #     else:
        #         context.bot.send_message(update.effective_chat.id, MESSAGE['no cards'])
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
            # print(dir(update.callback_query.from_user.id))
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
                    db_cards.append([f'\nid:{card.card_id}:{card.word_one}-{card.word_two} lvl:{card.repeat_lvl}'])

            if button:
                markup = page_markup(pages_list=db_cards, button=button)
                message = reduce(lambda a, x: a + x, db_cards[int(button[2])])
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
            reverse = True
        else:
            reverse = False
        self.new_card(update, context, user, message=message, reverse=reverse)
        message_edit = message + '\nCard is created ✔️'
        return [message_edit, None, None]


    def card_delete(self, user):
        for card in user.mindcards:
            if card.card_id == user.context:
                user.mindcards.remove(card)
        self.db.card_delete(user)

    def load_today_cards(self, update: Update, context: CallbackContext):
        self.user_check(update)
        today_cards = self.db.load_today_cards()
        for user_id in today_cards:
            for db_card in today_cards[user_id]:
                log.debug(f'Today card {db_card.word_one} - {db_card.word_two}, UID:{db_card.user_id}')
                if self.users[db_card.user_id]:
                    for card in self.users[db_card.user_id].mindcards:
                        if card.card_id == db_card.card_id:
                            log.debug(f'Replace {card.word_one} - {card.word_two}, UID:{card.user_id}')
                            self.users[db_card.user_id].mindcards.remove(card)
                    self.users[db_card.user_id].mindcards.append(db_card)
                else:
                    self.new_user(db_card.user_id)
                    self.users[db_card.user_id].mindcards.append(db_card)

    def send_today_cards(self):
        pass

    def load_user_cards(self, update: Update, context: CallbackContext):
        self.user_check(update)
        user_cards = ''
        cards_amount = 0
        user = self.users[update.message.from_user.id]
        for mindcard in user.mindcards + user.mindcards_delayed:
            cards_amount += 1
            user_cards += f'{mindcard.card_id}: {mindcard.word_one} - {mindcard.word_two} ' \
                          f'{mindcard.today_repeat}|{mindcard.today_reverse_repeat}|{mindcard.repeat_mistake}\n'
        user_cards += f'Total cards: {cards_amount}'
        user.state = 'start'
        self.markup[user.user_id] = markups['start']
        context.bot.send_message(update.effective_chat.id, user_cards,
                                 reply_markup=self.markup[update.message.from_user.id])

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
            if message_edit[2]:
                query.edit_message_text(text=message_edit[0], reply_markup=message_edit[1], entities=[message_edit[2]])
            elif message_edit[1]:
                query.edit_message_text(text=message_edit[0], reply_markup=message_edit[1])
            else:
                query.edit_message_text(text=message_edit[0])


    # TODO кнопка с прослушиванием слова


if __name__ == '__main__':
    mindcard_bot = Bot(TOKEN)
    mindcard_bot.run()
