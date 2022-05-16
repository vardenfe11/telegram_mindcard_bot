# -*- coding: utf-8 -*-
import os
import datetime
import logging
from peewee import *
from collections import defaultdict

log = logging.getLogger()

cards_db = SqliteDatabase('cards.db')


class MindCard:
    def __init__(self, word_one, word_two, user_id, repeat_lvl=-1, card_id=None):
        self.word_one = word_one
        self.word_two = word_two
        self.repeat_lvl = repeat_lvl
        self.today_repeat = 0
        self.today_reverse_repeat = 0
        self.repeat_mistake = 0
        self.user_id = user_id
        self.card_id = card_id


class Card(Model):
    user_id = IntegerField()
    card_id = AutoField()
    word_one = CharField()
    word_two = CharField()
    create_date = DateField()
    repeat_date = DateField()
    repeat_lvl = IntegerField()

    class Meta:
        database = cards_db


class DataBaseUpdater:
    def __init__(self):
        self.loaded_data = []
        if not os.path.exists('cards.db'):
            Card.create_table(Card)

    def update_base(self, mindcards):
        today_date = datetime.date.today()
        for card in mindcards:
            card.repeat_date = today_date + datetime.timedelta(days=int(2 ** card.repeat_lvl))
            if not card.card_id:
                try:
                    saved_card = Card(user_id=card.user_id,
                                      create_date=today_date,
                                      word_one=card.word_one,
                                      word_two=card.word_two,
                                      repeat_date=card.repeat_date,
                                      repeat_lvl=card.repeat_lvl)  # .on_conflict('replace').execute()
                    saved_card.save()
                    card.card_id = saved_card.card_id
                except Exception as error:
                    log.exception(f'Ошибка при записи в БД: {error}')
            else:
                if Card.select().where(Card.card_id == card.card_id):
                    updated_card = Card.select().where(Card.card_id == card.card_id).get()
                    updated_card.user_id = card.user_id
                    updated_card.repeat_lvl = card.repeat_lvl
                    updated_card.repeat_date = card.repeat_date
                    updated_card.save()
                else:
                    log.exception(f'Ошибка при зaгрузке карточки #{card.card_id} из БД')

    def load_base(self, user, days=None):
        self.loaded_data = []
        user_id = user.user_id
        today_date = datetime.date.today()
        if days:
            if days == 'all':
                db_user_cards = Card.select().where(Card.user_id == user_id)
            else:
                days_delta = datetime.timedelta(days=int(days))
                load_before_date = today_date + days_delta
                db_user_cards = Card.select().where((Card.repeat_date <= load_before_date) & (Card.user_id == user_id))
        else:
            db_user_cards = Card.select().where((Card.repeat_date <= today_date) & (Card.user_id == user_id))
        if db_user_cards:
            for db_card in db_user_cards:
                # print(db_card.repeat_date)
                # print(f'{db_card.repeat_date} <= {today_date}', db_card.repeat_date <= today_date)
                card = MindCard(word_one=db_card.word_one,
                                word_two=db_card.word_two,
                                user_id=user.user_id,
                                repeat_lvl=db_card.repeat_lvl,
                                card_id=db_card.card_id)
                self.loaded_data.append(card)
        return self.loaded_data

    def load_today_cards(self):
        def def_value():
            return []

        today_date = datetime.date.today()
        db_user_cards = Card.select().where(Card.repeat_date <= today_date)
        cards_return = defaultdict(def_value)
        for db_card in db_user_cards:
            card = MindCard(word_one=db_card.word_one,
                            word_two=db_card.word_two,
                            user_id=db_card.user_id,
                            repeat_lvl=db_card.repeat_lvl,
                            card_id=db_card.card_id)
            cards_return[card.user_id].append(card)
        return cards_return

    def card_delete(self, user, card_id):
        if Card.select().where((Card.card_id == card_id) & (Card.user_id == user.user_id)):
            deleted_card = Card.select().where((Card.card_id == card_id) & (Card.user_id == user.user_id)).get()
            deleted_card.delete_instance()


if __name__ == '__main__':
    base = DataBaseUpdater
