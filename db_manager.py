# -*- coding: utf-8 -*-
import os
import datetime
import logging
from typing import Optional
from collections import defaultdict

from peewee import *

log = logging.getLogger(__name__)

cards_db = SqliteDatabase('cards.db')
users_db = SqliteDatabase('users.db')


# ──────────────────────────────────────────────────────────────────────────────
# Runtime-класс карточки, используемый ботом
# ──────────────────────────────────────────────────────────────────────────────
class MindCard:
    """
    Карточка, хранящаяся в оперативной памяти во время работы бота
    """
    def __init__(
        self,
        word_one: str,
        word_two: str,
        user_id: int,
        repeat_lvl: int = -1,
        card_id: Optional[int] = None,
        hint: Optional[str] = None,
    ):
        self.word_one = word_one
        self.word_two = word_two
        self.repeat_lvl = repeat_lvl
        self.today_repeat = 0
        self.today_reverse_repeat = 0
        self.repeat_mistake = 0
        self.user_id = user_id
        self.card_id = card_id

        # ----  NEW  -----------------------------------------------------------
        self.hint: Optional[str] = hint          # сохранённая мнемоника
        self.hint_shown: bool = False           # отображается ли сейчас?
        self.temp_hint: Optional[str] = None    # временно сгенерированная
        self.hint_pending: bool = False  # идёт генерация?
        # ---------------------------------------------------------------------


# ──────────────────────────────────────────────────────────────────────────────
#  ORM-модель карточки
# ──────────────────────────────────────────────────────────────────────────────
class Card(Model):
    user_id = IntegerField()
    card_id = AutoField()
    word_one = CharField()
    word_two = CharField()
    create_date = DateField()
    repeat_date = DateField()
    repeat_lvl = IntegerField()
    # ----  NEW  ---------------------------------------------------------------
    hint = TextField(null=True)                 # хранит мнемонику/подсказку
    # -------------------------------------------------------------------------

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


# Users DB manager
class UserUpdater:
    def __init__(self):
        self.user = None
        if not os.path.exists('users.db'):
            User_db.create_table(User_db)

    def save(self, user):
        # Save user from bot to DB
        if User_db.select().where(User_db.user_id == user.user_id):
            db_user = User_db.select().where(User_db.user_id == user.user_id).get()
            db_user.user_id = user.user_id
            db_user.stack_size = user.stack_size
            db_user.interface_lang = user.interface_lang
            db_user.first_lang = user.first_lang
            db_user.second_lang = user.second_lang
            db_user.state = user.state
            db_user.score = user.score
            db_user.nickname = user.nickname
            db_user.nickname_change = user.nickname_change
            db_user.add_cards_to_stack = user.add_cards_to_stack
            db_user.save()
        else:
            self.create_user(user)

    def load(self, user):
        # Update user data from DB
        if User_db.select().where(User_db.user_id == user.user_id):
            db_user = User_db.select().where(User_db.user_id == user.user_id).get()
            user.stack_size = db_user.stack_size
            user.interface_lang = db_user.interface_lang
            user.first_lang = db_user.first_lang
            user.second_lang = db_user.second_lang
            user.state = db_user.state
            user.score = db_user.score
            user.nickname = db_user.nickname
            user.nickname_change = db_user.nickname_change
            user.add_cards_to_stack = db_user.add_cards_to_stack
        else:
            self.create_user(user)

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
        # Load weekly statistic from DB
        # stats = []
        if User_db.select().where(User_db.score > 0):
            score_user_list = sorted(User_db.select().where(User_db.score > 0), key=lambda u: u.score, reverse=True)
            if len(score_user_list) > 0:
                if users:
                    if score_user_list[0].user_id in users:
                        users[score_user_list[0].user_id].nickname_change += 1
                        users[score_user_list[0].user_id].save()
                    else:
                        score_user_list[0].nickname_change += 1
                        score_user_list[0].save()
                    for num, db_user in enumerate(score_user_list):
                        if db_user.user_id in users:
                            users[db_user.user_id].score = int(db_user.score / 10)
                            users[db_user.user_id].save()
                        else:
                            db_user.score = int(db_user.score / 10)
                            db_user.save()
                else:
                    return score_user_list
            else:
                return None


# ──────────────────────────────────────────────────────────────────────────────
#  Менеджер карточек
# ──────────────────────────────────────────────────────────────────────────────
class DataBaseUpdater:
    def __init__(self):
        self.loaded_data = []
        if not os.path.exists('cards.db'):
            Card.create_table(Card)

    # ░░░  SAVE / UPDATE  ░░░
    def update_base(self, mindcards):
        """
        Получает список MindCard и синхронизирует их с БД.
        """
        today_date = datetime.date.today()
        for card in mindcards:
            card.repeat_date = today_date + datetime.timedelta(days=2 ** card.repeat_lvl)

            # --- insert -------------------------------------------------------
            if not card.card_id:
                db_obj = Card.create(
                    user_id=card.user_id,
                    word_one=card.word_one,
                    word_two=card.word_two,
                    create_date=today_date,
                    repeat_date=card.repeat_date,
                    repeat_lvl=card.repeat_lvl,
                    hint=card.hint,
                )
                card.card_id = db_obj.card_id
                continue
            # --- update -------------------------------------------------------
            try:
                db_obj = Card.get(Card.card_id == card.card_id)
            except DoesNotExist:
                log.warning('Card #%s not found, inserting new.', card.card_id)
                self.update_base([MindCard(**card.__dict__)])
                continue

            db_obj.repeat_lvl = card.repeat_lvl
            db_obj.repeat_date = card.repeat_date
            db_obj.hint = card.hint
            db_obj.save()

    # ░░░  LOAD  ░░░
    def _mk_mindcard(self, db_card, user_id):
        return MindCard(
            word_one=db_card.word_one,
            word_two=db_card.word_two,
            user_id=user_id,
            repeat_lvl=db_card.repeat_lvl,
            card_id=db_card.card_id,
            hint=db_card.hint,
        )

    def load_base(self, user, days=None):
        """
        Загружает карточки для пользователя с учётом фильтра дней.
        """
        self.loaded_data = []
        today = datetime.date.today()

        if days == 'all':
            db_cards = Card.select().where(Card.user_id == user.user_id)
        elif days is not None:
            db_cards = Card.select().where(
                (Card.user_id == user.user_id) &
                (Card.repeat_date <= today + datetime.timedelta(days=int(days)))
            )
        else:
            db_cards = Card.select().where(
                (Card.user_id == user.user_id) & (Card.repeat_date <= today)
            )

        for db_card in db_cards:
            self.loaded_data.append(self._mk_mindcard(db_card, user.user_id))
        return self.loaded_data

    def load_today_cards(self):
        """
        Загружает карточки, которые нужно повторить сегодня, сгруппированные по user_id.
        """
        today = datetime.date.today()
        res = defaultdict(list)
        for db_card in Card.select().where(Card.repeat_date <= today):
            res[db_card.user_id].append(self._mk_mindcard(db_card, db_card.user_id))
        return res

    def word_check(self, user, word):
        card_response = []
        db_user_cards = Card.select().where(Card.user_id == user.user_id)
        for card in db_user_cards:
            if card.word_one.lower().find(word.lower()) > -1:
                card_response.append(card)
            if card.word_two.lower().find(word.lower()) > -1:
                card_response.append(card)
        if card_response:
            return card_response
    def card_delete(self, user, card_id):
        # Delete card by ID from DB for /delete_ID bot command
        if Card.select().where((Card.card_id == card_id) & (Card.user_id == user.user_id)):
            deleted_card = Card.select().where((Card.card_id == card_id) & (Card.user_id == user.user_id)).get()
            deleted_card.delete_instance()


if __name__ == '__main__':
    base = UserUpdater()
    User_db.create_table(User_db)
