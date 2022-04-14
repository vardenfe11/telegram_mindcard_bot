import logging
import telebot
import datetime
from googletrans import Translator
from db_manager import DataBaseUpdater
from db_manager import MindCard

try:
    from settings import *
except ImportError:
    exit('Скопируйте settings.py.deafault как settings.py и укажите в нем токен')

translator = Translator()

log = logging.getLogger()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
log.addHandler(stream_handler)
log.setLevel(logging.DEBUG)
stream_handler.setLevel(logging.DEBUG)


class User:
    def __init__(self, user_id, context=None):
        self.user_id = user_id
        self.mindcards = []
        self.state = None
        self.context = context or {}

    def get_card(self, db):
        if len(self.mindcards) > 0:
            self.mindcards = sorted(self.mindcards, key=lambda card: card.today_reverse_repeat)
            self.mindcards = sorted(self.mindcards, key=lambda card: card.today_repeat)
        for num, card in enumerate(self.mindcards):
            if card.today_repeat < 3 or card.today_reverse_repeat < 3:
                return card
            else:
                if card.repeat_mistake < 2:
                    card.repeat_lvl += 1
                db.update_base([card])
                del self.mindcards[num]


# test_mindcard = [MindCard('dog', 'собака'), MindCard('cat', 'кот'), MindCard('dick', 'хуй')]


class Bot:
    def __init__(self, token):
        self.users = {}
        self.user_card = {}
        self.token = token
        self.bot = None
        self.markup = None
        self.db = DataBaseUpdater()

    def run(self):
        """
        Запуск бота
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

    def new_user(self, event):
        """
        :param event: income message from user to bot
        :return: create new user for keeping repeating cards, load cards from database for the user id
        """
        user_id = event.from_user.id
        user = User(user_id)
        self.users[user_id] = user
        users_db_cards = self.db.load_base(user)
        if users_db_cards:
            self.users[user_id].mindcards = users_db_cards
        log.debug('New user is created, user_id: %s', event.from_user.id)

    def on_event(self, event):
        user_id = event.from_user.id
        if event:
            if user_id not in self.users:
                self.new_user(event)
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
            elif not button_click:
                self.handle_text(event, user)

    def start(self, event):
        log.debug('/start')
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = telebot.types.KeyboardButton('Repeat')
        item2 = telebot.types.KeyboardButton('Create')
        item3 = telebot.types.KeyboardButton('Translate')
        markup.add(item1)
        markup.add(item2)
        markup.add(item3)
        self.markup = markup
        self.bot.send_message(event.chat.id, MESSAGE['start'], reply_markup=self.markup)

    def handle_text(self, event, user):
        if user.state == 'translate':
            translated_message = translator.translate(event.text, dest='ru')
            send_message = f'{event.text}\n{translated_message.text}'
            self.bot.send_message(event.chat.id, send_message, reply_markup=self.markup)
        elif user.state == 'create':
            self.new_card(event, user)
        else:
            self.start(event)

    def new_card(self, event, user):
        break_num = event.text.find('\n')
        if break_num > 0:
            card = MindCard(word_one=event.text[:break_num],
                            word_two=event.text[break_num+1:],
                            user=user)
            self.db.update_base([card])
            user.mindcards.append(card)
            send_message = f'Карточка {event.text[:break_num]}|{event.text[break_num+1:]} создана\n' \
                           f'Можете создать ещё одну'
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
        self.markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        remember = telebot.types.KeyboardButton("Remember")
        forgot = telebot.types.KeyboardButton("Forgot")
        new_word = telebot.types.KeyboardButton("Create")
        translate = telebot.types.KeyboardButton('Translate')
        # create buttons lines
        self.markup.row(remember, forgot)
        self.markup.row(new_word, translate)
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

        log.debug(f'Send the card {word_one} - {word_two}, TR:{card.today_repeat}, TRR:{card.today_reverse_repeat}')

    def buttons_handler(self, event, user):
        """
        :param event: income message
        :param user: current user
        :return: handling user message text if it is in buttons list
        """
        if event.text == 'Repeat':
            user.state = 'repeat'
            if len(user.mindcards) > 0:
                card = user.get_card(self.db)
                self.user_card[event.from_user.id] = card
                self.send_card(event, card)
            else:
                self.bot.send_message(event.chat.id, MESSAGE['no cards'], reply_markup=self.markup)
        elif event.text == 'Create':
            user.state = 'create'
            # create buttons
            self.markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            new_word = telebot.types.KeyboardButton("Repeat")
            translate = telebot.types.KeyboardButton('Translate')
            # create buttons lines
            self.markup.row(new_word, translate)
            # self.markup = telebot.types.ReplyKeyboardRemove(selective=False)
            self.bot.send_message(event.chat.id, MESSAGE['create'], reply_markup=self.markup)
        elif event.text == 'Remember':
            if self.user_card[event.from_user.id].today_repeat < 3:
                self.user_card[event.from_user.id].today_repeat += 1
            elif self.user_card[event.from_user.id].today_reverse_repeat < 3:
                self.user_card[event.from_user.id].today_reverse_repeat += 1
            else:
                print('У карточки больше 3 повторений')
            card = user.get_card(self.db)
            if card:
                self.user_card[event.from_user.id] = card
                self.send_card(event, card)
            else:
                self.bot.send_message(event.chat.id, MESSAGE['no cards'])
        elif event.text == 'Forgot':
            if self.user_card[event.from_user.id].today_repeat < 3:
                self.user_card[event.from_user.id].today_repeat -= 1
            elif self.user_card[event.from_user.id].today_reverse_repeat < 3:
                self.user_card[event.from_user.id].today_reverse_repeat -= 1
            self.user_card[event.from_user.id].repeat_mistake += 1
        elif event.text == 'Translate':
            user.state = 'translate'
            # create buttons
            self.markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            repeat = telebot.types.KeyboardButton('Repeat')
            new_word = telebot.types.KeyboardButton("Create")
            # create buttons lines
            self.markup.row(new_word, repeat)
            self.bot.send_message(event.chat.id, MESSAGE['translate'], reply_markup=self.markup)


if __name__ == '__main__':
    mindcard_bot = Bot(TOKEN)
    mindcard_bot.run()
