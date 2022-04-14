# -*- coding: utf-8 -*-
import os
import datetime
import logging
from peewee import *

log = logging.getLogger()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
log.addHandler(stream_handler)
log.setLevel(logging.INFO)
stream_handler.setLevel(logging.DEBUG)

db = SqliteDatabase('cards.db')

class MindCard:
    def __init__(self, word_one, word_two, user, repeat_lvl=0, card_id=None):
        self.word_one = word_one
        self.word_two = word_two
        self.repeat_lvl = repeat_lvl
        self.today_repeat = 0
        self.today_reverse_repeat = 0
        self.repeat_mistake = 0
        self.user_id = user.user_id
        self.card_id = card_id

class Card(Model):
    user_id = IntegerField()
    card_id = AutoField()
    word_one = CharField()
    word_two = CharField()
    create_date = DateField(unique=True)
    repeat_date = DateField(unique=True)
    repeat_lvl = IntegerField()

    class Meta:
        database = db


class DataBaseUpdater:
    def __init__(self):
        self.loaded_data = []
        if not os.path.exists('cards.db'):
            Card.create_table(Card)

    def update_base(self, mindcards):
        today_date = datetime.date.today()
        for card in mindcards:
            card.repeat_date = today_date + datetime.timedelta(days=2 ** card.repeat_lvl)
            if not card.card_id:
                try:
                    Card.insert(user_id=card.user_id,
                                create_date=today_date,
                                word_one=card.word_one,
                                word_two=card.word_two,
                                repeat_date=card.repeat_date,
                                repeat_lvl=card.repeat_lvl).on_conflict('replace').execute()
                except Exception as error:
                    log.exception(f'Ошибка при записи в БД: {error}')
            else:
                updated_card = Card.select().where(Card.card_id == card.card_id).get()
                if updated_card:
                    updated_card.repeat_lvl = card.repeat_lvl
                    updated_card.repeat_date = card.repeat_date
                    updated_card.save()
                else:
                    log.exception(f'Ошибка при зaгрузке карточки #{card.card_id} из БД')

    def load_base(self, user):
        self.loaded_data = []
        user_id = user.user_id
        today_date = datetime.date.today()
        db_user_cards = Card.select().where(Card.repeat_date <= today_date & Card.user_id == user_id)
        if db_user_cards:
            for db_card in db_user_cards:
                card = MindCard(word_one=db_card.word_one,
                                word_two=db_card.word_two,
                                user=user,
                                repeat_lvl=db_card.repeat_lvl,
                                card_id=db_card.card_id)
                self.loaded_data.append(card)
        return self.loaded_data
