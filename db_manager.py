# -*- coding: utf-8 -*-
import os
import datetime
import logging
from peewee import *
from collections import defaultdict

log = logging.getLogger()

cards_db = SqliteDatabase('cards.db')
users_db = SqliteDatabase('users.db')


# ──────────────────────────── КАРТОЧКА ────────────────────────────────────────
class MindCard:
    def __init__(
            self,
            word_one: str,
            word_two: str,
            user_id: int,
            repeat_lvl: int = -1,
            card_id: int = None,
            hint: str = None,
    ):
        self.word_one = word_one
        self.word_two = word_two
        self.repeat_lvl = repeat_lvl
        self.today_repeat = 0
        self.today_reverse_repeat = 0
        self.repeat_mistake = 0
        self.user_id = user_id
        self.card_id = card_id

        # — подсказки —
        self.hint = hint  # сохранённая в БД
        self.hint_visible: bool = False  # показана ли сохранённая
        self.new_hint = None  # «черновик» новой подсказки


# ──────────────────────────── МОДЕЛИ БД ───────────────────────────────────────
class Card(Model):
    user_id = IntegerField()
    card_id = AutoField()
    word_one = CharField()
    word_two = CharField()
    create_date = DateField()
    repeat_date = DateField()
    repeat_lvl = IntegerField()
    hint = TextField(null=True)  # ← новая колонка

    class Meta:
        database = cards_db


# User class for DB
class User_db(Model):
    user_id = IntegerField(unique=True)
    stack_size = IntegerField()
    interface_lang = IntegerField()
    first_lang = IntegerField()
    second_lang = IntegerField()
    score = IntegerField()
    nickname = CharField()
    nickname_change = IntegerField()
    state = CharField()
    add_cards_to_stack = BooleanField()

    class Meta:
        database = users_db


# ──────────────────────── РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ─────────────────────────────
class UserUpdater:
    def __init__(self):
        self.user = None
        if not os.path.exists('users.db'):
            User_db.create_table(User_db)

    # сохранение / загрузка сведений о пользователе (без изменений)
    def save(self, user):
        if User_db.select().where(User_db.user_id == user.user_id):
            db_user = User_db.get(User_db.user_id == user.user_id)
            db_user.stack_size = user.stack_size
            db_user.interface_lang = user.interface_lang
            db_user.first_lang = user.first_lang
            db_user.second_lang = user.second_lang
            db_user.score = user.score
            db_user.nickname = user.nickname
            db_user.nickname_change = user.nickname_change
            db_user.state = user.state
            db_user.add_cards_to_stack = user.add_cards_to_stack
            db_user.save()
        else:
            User_db.create(
                user_id=user.user_id,
                stack_size=user.stack_size,
                interface_lang=user.interface_lang,
                first_lang=user.first_lang,
                second_lang=user.second_lang,
                score=user.score,
                nickname=user.nickname,
                nickname_change=user.nickname_change,
                state=user.state,
                add_cards_to_stack=user.add_cards_to_stack,
            )

    def load(self, user):
        if User_db.select().where(User_db.user_id == user.user_id):
            db_user = User_db.get(User_db.user_id == user.user_id)
            user.stack_size = db_user.stack_size
            user.interface_lang = db_user.interface_lang
            user.first_lang = db_user.first_lang
            user.second_lang = db_user.second_lang
            user.score = db_user.score
            user.nickname = db_user.nickname
            user.nickname_change = db_user.nickname_change
            user.state = db_user.state
            user.add_cards_to_stack = db_user.add_cards_to_stack
        else:
            self.save(user)

    def create_user(self, user):
        # Create user in DB from bot user class
        try:
            User_db.create(
                user_id=user.user_id,
                stack_size=user.stack_size,
                interface_lang=user.interface_lang,
                first_lang=user.first_lang,
                second_lang=user.second_lang,
                state=user.state,
                score=user.score,
                nickname=user.nickname,
                nickname_change=user.nickname_change,
                add_cards_to_stack=user.add_cards_to_stack,
            )
        except Exception as error:
            log.exception(f'Ошибка при записи в БД: {error}')

    def load_stats(self, users=None):
        if User_db.select().where(User_db.score > 0):
            user_list = sorted(
                User_db.select().where(User_db.score > 0),
                key=lambda u: u.score,
                reverse=True
            )
            if user_list:
                if users:
                    top_id = user_list[0].user_id
                    if top_id in users:
                        users[top_id].nickname_change += 1
                        users[top_id].save()
                    else:
                        user_list[0].nickname_change += 1
                        user_list[0].save()
                for db_user in user_list:
                    if users and db_user.user_id in users:
                        users[db_user.user_id].score = int(db_user.score / 10)
                        users[db_user.user_id].save()
                    else:
                        db_user.score = int(db_user.score / 10)
                        db_user.save()


# ──────────────────────── РАБОТА С КАРТОЧКАМИ ────────────────────────────────
class DataBaseUpdater:
    def __init__(self):
        self.loaded_data: list[MindCard] = []

        # создать таблицу или «лёгкая миграция» (добавляем колонку hint)
        if not Card.table_exists():
            Card.create_table()
        else:
            if 'hint' not in Card._meta.fields:
                cards_db.execute_sql('ALTER TABLE card ADD COLUMN hint TEXT;')

    # ---------- сохранение / обновление --------------------------------------
    def update_base(self, mindcards: list[MindCard]):
        today_date = datetime.date.today()
        for card in mindcards:
            card.repeat_date = today_date + datetime.timedelta(days=int(2 ** card.repeat_lvl))

            # новая карточка
            if not card.card_id:
                try:
                    saved = Card.create(
                        user_id=card.user_id,
                        create_date=today_date,
                        word_one=card.word_one,
                        word_two=card.word_two,
                        repeat_date=card.repeat_date,
                        repeat_lvl=card.repeat_lvl,
                        hint=card.hint,
                    )
                    card.card_id = saved.card_id
                except Exception as err:
                    log.exception(f'Ошибка при записи в БД: {err}')

            # обновление существующей
            else:
                try:
                    upd = Card.get(Card.card_id == card.card_id)
                    upd.repeat_lvl = card.repeat_lvl
                    upd.repeat_date = card.repeat_date
                    upd.hint = card.hint
                    upd.save()
                except Exception as err:
                    log.exception(f'Ошибка при обновлении #{card.card_id}: {err}')

    # ---------- выборка -------------------------------------------------------
    def load_base(self, user, days=None):
        """Загрузить карточки пользователя (по умолчанию – только «на сегодня»)."""
        self.loaded_data.clear()
        today = datetime.date.today()

        selector = Card.select().where(Card.user_id == user.user_id)
        if days and days != 'all':
            selector = selector.where(Card.repeat_date <= today + datetime.timedelta(days=int(days)))
        elif not days:
            selector = selector.where(Card.repeat_date <= today)

        for db_card in selector:
            self.loaded_data.append(
                MindCard(
                    word_one=db_card.word_one,
                    word_two=db_card.word_two,
                    user_id=user.user_id,
                    repeat_lvl=db_card.repeat_lvl,
                    card_id=db_card.card_id,
                    hint=db_card.hint,
                )
            )
        return self.loaded_data

    def load_today_cards(self):
        """Собрать словарь {user_id: [MindCard, …]} для автоповторения."""

        def def_value():
            return []

        today_cards = defaultdict(def_value)
        today = datetime.date.today()

        for db_card in Card.select().where(Card.repeat_date <= today):
            today_cards[db_card.user_id].append(
                MindCard(
                    word_one=db_card.word_one,
                    word_two=db_card.word_two,
                    user_id=db_card.user_id,
                    repeat_lvl=db_card.repeat_lvl,
                    card_id=db_card.card_id,
                    hint=db_card.hint,
                )
            )
        return today_cards

    # ---------- поиск и удаление (без изменений) ------------------------------
    def word_check(self, user, word):
        result = []
        query = Card.select().where(Card.user_id == user.user_id)
        for db_card in query:
            if word.lower() in db_card.word_one.lower() or word.lower() in db_card.word_two.lower():
                result.append(db_card)
        return result

    def card_delete(self, user, card_id):
        try:
            Card.get(Card.card_id == card_id, Card.user_id == user.user_id).delete_instance()
            return True
        except Exception as err:
            log.exception(f'Ошибка удаления карточки #{card_id}: {err}')
            return False
