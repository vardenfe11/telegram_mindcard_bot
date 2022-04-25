import datetime
import logging
import random

import telebot
from markups import markups
from googletrans import Translator
from db_manager import DataBaseUpdater
from db_manager import MindCard
from settings import MESSAGE
from telegram_token import TOKEN
from collections import defaultdict

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
stream_handler.setLevel(logging.DEBUG)


def def_value():
    return User(0)


class User:
    def __init__(self, user_id, context=''):
        self.user_id = user_id
        self.mindcards = []
        self.state = ''
        self.context = context

    def get_card(self, db):
        # if len(self.mindcards) > 0:
        #     self.mindcards = sorted(self.mindcards, key=lambda card: card.repeat_mistake)
        #     self.mindcards = sorted(self.mindcards, key=lambda card: card.today_reverse_repeat)
        #     self.mindcards = sorted(self.mindcards, key=lambda card: card.today_repeat)
        while len(self.mindcards) > 0:
            card = random.choice(self.mindcards)
            if (card.today_repeat + card.today_reverse_repeat) < (6 + card.repeat_mistake):
                self.context = card.card_id
                return card
            else:
                if card.repeat_mistake < 2 and card.card_id:
                    card.repeat_lvl += 1
                db.update_base([card])
                self.mindcards.remove(card)


class Bot:
    def __init__(self, token):
        self.users = defaultdict(def_value)
        self.user_card = {}
        self.token = token
        self.bot = None
        self.markup = None
        self.db = DataBaseUpdater()
        self.repeat = datetime.date.today()

    def run(self):
        """
        Run the bot
        """
        self.bot = telebot.TeleBot(self.token)
        self.bot.set_update_listener(self.handle_messages)
        self.bot.infinity_polling()

    def handle_messages(self, messages):
        """
        :param messages: income messages from user to bot
        :return: run event handler
        """
        for event in messages:
            try:
                log.debug('обнаружен ивент: %s', event)
                self.on_event(event)
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
        log.debug('New user is created, user_id: %s', user_id)

    def on_event(self, event):
        if self.repeat < datetime.date.today():
            if datetime.datetime.today().hour > 8:
                self.repeat = datetime.date.today()
                self.load_today_cards()
                self.send_today_cards()
        user_id = event.from_user.id
        if event:
            if user_id not in self.users:
                self.new_user(event.from_user.id)
            user = self.users[user_id]
            button_click = False
            if self.markup:
                for keyboard in self.markup.keyboard:
                    for button in keyboard:
                        if event.json['text'] == button['text']:
                            button_click = True
                            self.buttons_handler(event, user)
            if event.json['text'] == '/start':
                user.state = 'start'
                self.start(event)
            elif event.json['text'] == '/load_user_cards':
                self.load_user_cards(event, user)
            elif event.json['text'] == '/load_today_cards':
                self.load_today_cards()
            elif event.json['text'] == '/help':
                self.markup = markups['start']
                self.bot.send_message(event.chat.id, MESSAGE['help'], reply_markup=self.markup)
            elif event.json['text'][:5] == '/load':
                num = event.json['text'][6:]
                self.load(event, user, num)
            elif event.json['text'][:7] == '/delete':
                num = event.json['text'][8:]
                self.db.card_delete(user, num)
            elif not button_click:
                self.handle_text(event, user)

    def start(self, event):
        log.debug('/start')
        self.markup = markups['start']
        self.bot.send_message(event.chat.id, MESSAGE['start'], reply_markup=self.markup)

    def handle_text(self, event, user):
        if user.state == 'translate':
            translated_message = translator.translate(event.text, dest='ru')
            user.context = f'{event.text}\n{translated_message.text}'
            self.bot.send_message(event.chat.id, user.context, reply_markup=self.markup)
        elif user.state == 'create':
            self.new_card(event, user)
        else:
            self.start(event)

    def new_card(self, event, user, message=None):
        if not message:
            message = event.text
        break_num = message.find('\n')
        if break_num > 0:
            card = MindCard(word_one=message[:break_num],
                            word_two=message[break_num + 1:],
                            user_id=user.user_id)
            user.mindcards.append(card)
            self.db.update_base([card])
            send_message = f'Card |{message[:break_num]}/{message[break_num + 1:]}| is created\n'
            self.bot.send_message(event.chat.id, send_message, reply_markup=self.markup)
        else:
            self.bot.send_message(event.chat.id, 'error', reply_markup=self.markup)

    def send_card(self, event, card):
        """
        :param event: income message
        :param card: mind card for sending
        :return: send card for repeat to user with Remember, Forgot and Create buttons
        """
        log.debug(f'sending card {card.word_one}/{card.word_two}')
        # create buttons
        self.markup = markups['send_card']
        # 3 time repeats for one card side and 3 for another
        if card.today_repeat < 3:
            word_one, word_two = card.word_one, card.word_two
        else:
            word_two, word_one = card.word_one, card.word_two
        # message text
        send_message = f'{word_one}\n{word_two}'
        # create entities for another card side spoiler
        entities = telebot.types.MessageEntity(offset=len(word_one) + 1, length=len(word_two),
                                               type='spoiler')
        self.bot.send_message(event.chat.id, send_message, entities=[entities], reply_markup=self.markup)

        if self.users[event.from_user.id].state == 'repeat':
            self.bot.delete_message(event.chat.id, event.message_id - 1)
            self.bot.delete_message(event.chat.id, event.message_id - 2)
        log.debug(f'Send the card {word_one} - {word_two}, TR:{card.today_repeat}, TRR:{card.today_reverse_repeat}')

    def buttons_handler(self, event, user):
        """
        :param event: income message
        :param user: current user
        :return: handling user message text if it is in buttons list
        """
        if event.text == 'Repeat':
            if len(user.mindcards) > 0:
                card = user.get_card(self.db)
                self.user_card[event.from_user.id] = card
                self.send_card(event, card)
                user.state = 'repeat'
            else:
                user.state = 'start'
                self.markup = markups['start']
                self.bot.send_message(event.chat.id, MESSAGE['no cards'], reply_markup=self.markup)
        elif event.text == 'Create from translated':
            self.new_card(event, user, message=user.context)
            self.bot.send_message(event.chat.id, MESSAGE['translate'], reply_markup=self.markup)
        elif event.text == 'Create':
            user.state = 'create'
            # create buttons
            self.markup = markups['create']
            self.bot.send_message(event.chat.id, MESSAGE['create'], reply_markup=self.markup)
        elif event.text == 'Remember' or event.text == 'Forgot':
            if self.user_card[event.from_user.id].today_repeat < \
                    (3 + self.user_card[event.from_user.id].repeat_mistake / 2):
                self.user_card[event.from_user.id].today_repeat += 1
            elif self.user_card[event.from_user.id].today_reverse_repeat < \
                    (3 + self.user_card[event.from_user.id].repeat_mistake / 2):
                self.user_card[event.from_user.id].today_reverse_repeat += 1
            else:
                print('У карточки больше 3 повторений')
            if event.text == 'Forgot':
                self.user_card[event.from_user.id].repeat_mistake += 1
            card = user.get_card(self.db)
            if card:
                self.user_card[event.from_user.id] = card
                self.send_card(event, card)
            else:
                self.bot.send_message(event.chat.id, MESSAGE['no cards'])
        elif event.text == 'Translate':
            user.state = 'translate'
            # create buttons
            self.markup = markups['translate']
            self.bot.send_message(event.chat.id, MESSAGE['translate'], reply_markup=self.markup)
        elif event.text == 'Delete' and user.state == 'repeat':
            user.state = 'delete'
            self.markup = markups['delete']
            self.bot.send_message(event.chat.id, MESSAGE['delete'], reply_markup=self.markup)
        elif event.text == 'Yes' and user.state == 'delete':
            self.card_delete(user)
            user.state = 'start'
            self.markup = markups['start']
            self.bot.send_message(event.chat.id, MESSAGE['default'], reply_markup=self.markup)
        else:
            user.state = 'start'
            self.markup = markups['start']
            self.bot.send_message(event.chat.id, MESSAGE['default'], reply_markup=self.markup)

    def load(self, event, user, num):
        self.markup = markups['start']
        if num == 'all' or num.isnumeric():
            users_db_cards = self.db.load_base(user, days=num)
            message = f'{len(users_db_cards)} cards:'
            for card in users_db_cards:
                message += f'\nid{card.card_id}:{card.word_one}-{card.word_two} lvl:{card.repeat_lvl}'
            self.bot.send_message(event.chat.id, message, reply_markup=self.markup)
        else:
            self.bot.send_message(event.chat.id, f'Количество дней в команде должно быть числом или all',
                                  reply_markup=self.markup)

    def card_delete(self, user):
        for card in user.mindcards:
            if card.card_id == user.context:
                user.mindcards.remove(card)
        self.db.card_delete(user)

    def load_today_cards(self):
        today_cards = self.db.load_today_cards()
        for user_id in today_cards:
            for db_card in today_cards[user_id]:
                log.debug(f'Today card {db_card.word_one} - {db_card.word_two}, UID:{db_card.user_id}')
                if self.users[db_card.user_id]:
                    for card in self.users[db_card.user_id].mindcards:
                        if card.card_id == db_card.card_id:
                            self.users[db_card.user_id].mindcards.remove(card)
                    self.users[db_card.user_id].mindcards.append(db_card)
                else:
                    self.new_user(db_card.user_id)
                    self.users[db_card.user_id].mindcards.append(db_card)

    def send_today_cards(self):
        pass

    def load_user_cards(self, event, user):
        user_cards = ''
        cards_amount = 0
        for mindcard in user.mindcards:
            cards_amount += 1
            user_cards += f'{mindcard.card_id}: {mindcard.word_one} - {mindcard.word_two}\n' \
                          f'{mindcard.card_id}: FR: {mindcard.today_repeat}' \
                          f' RR: {mindcard.today_reverse_repeat} RM:{mindcard.repeat_mistake}\n'
        user_cards += f'Total cards: {cards_amount}'
        user.state = 'start'
        self.markup = markups['start']
        self.bot.send_message(event.chat.id, user_cards, reply_markup=self.markup)




if __name__ == '__main__':
    mindcard_bot = Bot(TOKEN)
    mindcard_bot.run()
