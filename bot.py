import logging
import telebot
import datetime
from googletrans import Translator

try:
    from settings import *
except ImportError:
    exit('Скопируйте settings.py.deafault как settings.py, укажите в нем токен и ID группы')

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
        self.scenario = None
        self.step = None
        self.context = context or {}

    def get_card(self):
        if len(self.mindcards) > 0:
            self.mindcards = sorted(self.mindcards, key=lambda card: card.today_reverse_repeat)
            self.mindcards = sorted(self.mindcards, key=lambda card: card.today_repeat)
        for card in self.mindcards:
            if card.today_repeat < 3 or card.today_reverse_repeat < 3:
                return card
            else:
                log.debug('Сохранение карточки в базу', card)


class MindCard:
    def __init__(self, word_one, word_two, repeat_lvl=0):
        self.word_one = word_one
        self.word_two = word_two
        self.create_date = datetime.date.today()
        self.repeat_date = datetime.date.today() + datetime.timedelta(days=2 ** repeat_lvl - 1)
        self.repeat_lvl = repeat_lvl
        self.today_repeat = 0
        self.today_reverse_repeat = 0


test_mindcard = [MindCard('dog', 'собака'), MindCard('cat', 'кот'), MindCard('dick', 'хуй')]


class Bot:
    def __init__(self, token):
        self.users = {}
        self.user_card = {}
        self.token = token
        self.bot = None
        self.markup = None
        self.current_user = None

    def run(self):
        """
        Запуск бота
        """
        self.bot = telebot.TeleBot(self.token)
        self.bot.set_update_listener(self.handle_messages)
        self.bot.infinity_polling()

    def handle_messages(self, messages):
        for event in messages:
            try:
                log.debug('обнаружен ивент: %s', event)
                self.on_event(event)
            except Exception as error:
                log.exception(f'Ошибка при получении ивента: {error}')

    def new_user(self, event):
        user_id = event.from_user.id
        new_user = User(user_id)
        self.users[user_id] = new_user
        self.current_user = self.users[user_id]
        log.debug('New user is created, current_user: %s', event.from_user.id)

    def on_event(self, event):
        if event:
            if event.from_user.id in self.users:
                self.current_user = self.users[event.from_user.id]
                self.current_user.mindcards = test_mindcard
                log.debug(f'Change current_user: %s', event.from_user.id)
            else:
                self.new_user(event)
            if self.markup:
                for button in self.markup.keyboard:
                    if event.json['text'] == button[0]['text']:
                        self.buttons_handler(event)
            elif event.json['text'] == '/start':
                self.current_user.scenario = '/start'
                self.start(event)
            else:
                self.handle_text(event)

    def start(self, m, res=False):
        log.debug('/start')
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = telebot.types.KeyboardButton('Send the test card')
        item2 = telebot.types.KeyboardButton('Test button')
        markup.add(item1)
        markup.add(item2)
        self.markup = markup
        self.bot.send_message(m.chat.id, 'Test button', reply_markup=markup)

    def handle_text(self, message):
        translated_message = translator.translate(message.text, dest='ru')
        send_message = f'{message.text}\n{translated_message.text}'
        entities = telebot.types.MessageEntity(offset=len(message.text) + 1, length=len(translated_message.text),
                                               type='spoiler')
        self.bot.send_message(message.chat.id, send_message, entities=[entities])

    def send_card(self, event, card):
        log.debug(f'sending card {card.word_one}/{card.word_two}')
        self.markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        remember = telebot.types.KeyboardButton("Remember")
        forgot = telebot.types.KeyboardButton("Forgot")
        new_word = telebot.types.KeyboardButton("New word")
        self.markup.row(remember, forgot)
        self.markup.row(new_word)
        if card.today_repeat < 3:
            word_one, word_two = card.word_one, card.word_two
        else:
            word_two, word_one = card.word_one, card.word_two
        log.debug(f'Send the card {word_one} - {word_two}, TR:{card.today_repeat}, TRR:{card.today_reverse_repeat}', card)
        send_message = f'{word_one}\n{word_two}'
        entities = telebot.types.MessageEntity(offset=len(word_one) + 1, length=len(word_two),
                                               type='spoiler')
        self.bot.send_message(event.chat.id, send_message, entities=[entities], reply_markup=self.markup)

    def buttons_handler(self, event):
        if event.text == 'Send the test card':
            card = self.current_user.get_card()
            self.user_card[event.from_user.id] = card
            self.send_card(event, card)
        elif event.text == 'Test button':
            self.markup = None
            markup = telebot.types.ReplyKeyboardRemove(selective=False)
            self.bot.send_message(event.chat.id, 'Кнопочка нажата', reply_markup=markup)
        elif event.text == 'Remember':
            if self.user_card[event.from_user.id].today_repeat < 3:
                self.user_card[event.from_user.id].today_repeat += 1
            elif self.user_card[event.from_user.id].today_reverse_repeat < 3:
                self.user_card[event.from_user.id].today_reverse_repeat += 1
            else:
                print('У карточки больше 3 повторений')
            card = self.current_user.get_card()
            if card:
                self.user_card[event.from_user.id] = card
                self.send_card(event, card)
            else:
                self.bot.send_message(event.chat.id, 'Вы всё повторили!')
        elif event.text == 'Forgot':
            if self.user_card[event.from_user.id].today_repeat < 3:
                self.user_card[event.from_user.id].today_repeat -= 1
            elif self.user_card[event.from_user.id].today_reverse_repeat < 3:
                self.user_card[event.from_user.id].today_reverse_repeat -= 1
        elif event.text == 'New word':
            pass


if __name__ == '__main__':
    mindcard_bot = Bot(TOKEN)
    mindcard_bot.run()
