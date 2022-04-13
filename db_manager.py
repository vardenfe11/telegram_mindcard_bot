# -*- coding: utf-8 -*-
import os
from datetime import date
import logging
from peewee import *

log = logging.getLogger()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
log.addHandler(stream_handler)
log.setLevel(logging.INFO)
stream_handler.setLevel(logging.DEBUG)

db = SqliteDatabase('weather.db')


class Card(Model):
    user_id = IntegerField()
    card_id = IntegerField()
    word_one = CharField()
    word_two = CharField()
    create_date = DateField(unique=True)
    repeat_date = DateField(unique=True)
    repeat_lvl = IntegerField()

    class Meta:
        database = db


class DataBaseUpdater:
    def __init__(self, data):
        self.data = data
        self.loaded_data = {}
        if not os.path.exists('weather.db'):
            Card.create_table(Card)

    def update_base(self, from_=None, to=None):
        if from_ and not to:
            to = from_
        for w_day in self.data:
            if not from_ or from_ <= w_day <= to:
                try:
                    # Можно было бы ещё использовать insert_many
                    Day.insert(condition=self.data[w_day]['condition'],
                               temp_night=self.data[w_day]['temp_night'],
                               temp_day=self.data[w_day]['temp_day'],
                               weather_date=w_day).on_conflict('replace').execute()
                except Exception as error:
                    log.exception(f'Ошибка при записи в БД: {error}')

        db_weather = Day.select().where(Day.weather_date.between(from_, to))
        for day in db_weather:
            print('Обновление данных:', day.weather_date, day.condition, day.temp_night, day.temp_day)

    def load_base(self, from_=None, to=None):
        self.loaded_data = {}
        if not from_:
            from_ = date.today()
        if not to:
            to = from_
        db_weather = Day.select().where(Day.weather_date.between(from_, to))
        if db_weather:
            for day in db_weather:
                self.loaded_data[day.weather_date] = {'condition': day.condition, 'temp_night': day.temp_night,
                                                      'temp_day': day.temp_day}
        return self.loaded_data
