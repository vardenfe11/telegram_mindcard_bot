# фрагменты импорта и настройки логгера – без изменений
# …

from ai import get_mem_hint
from markups import markups
from db_manager import DataBaseUpdater, UserUpdater, MindCard
# …

# ──────────────────────────────────────────────────────────────────────────────
class Bot:
    # … (конструктор, run, вспомогательные методы – без изменений)

    # ─── ВСПОМОГАТЕЛЬНОЕ: формирование текста сообщения с подсказкой ──────────
    def _build_repeat_message(self, user, card) -> str:
        cards_left = len(user.mindcards) + len(user.mindcards_delayed) + len(user.mindcards_queuing)
        msg = MESSAGE[user.interface_lang]['repeat'] + str(cards_left)

        hint_to_show = card.new_hint if card.new_hint is not None else (
            card.hint if card.hint_visible else None)
        if hint_to_show:
            msg += f'\n\n💡 {hint_to_show}'
        return msg

    # ─── ОСНОВНОЙ ХЭНДЛЕР ПОВТОРЕНИЯ ─────────────────────────────────────────
    def repeat_cards(self, update: Update, context: CallbackContext, button=None):
        self.user_check(update)
        back_flag = None                        # нужен для card_markup(back)

        if button:                              # вызов из inline-кнопки
            user = self.users[update.callback_query.from_user.id]
            btn_action = button[2]
            # найдём/обновим текущую карточку пользователя
            if (user.user_id not in self.user_card) or \
               (self.user_card[user.user_id] and self.user_card[user.user_id].card_id != int(button[1])):
                self.user_card[user.user_id] = user.get_card_by_id(int(button[1]))
            card = self.user_card[user.user_id]

            # ── работа с подсказками ────────────────────────────────────────
            if btn_action.startswith('ai'):
                word, translation = card.word_one, card.word_two

                match btn_action:
                    case 'ai':                               # показать / скрыть
                        if card.hint is None:                # подсказки ещё нет → создаём и сохраняем
                            card.hint = get_mem_hint(word, translation)
                            card.hint_visible = True
                            self.db.update_base([card])
                        else:                                # просто переключаем видимость
                            card.hint_visible = not card.hint_visible
                            card.new_hint = None

                    case 'ai_del':                           # удалить подсказку
                        card.hint = None
                        card.hint_visible = False
                        self.db.update_base([card])

                    case 'ai_new':                           # сгенерировать новую (не сохраняя)
                        card.new_hint = get_mem_hint(word, translation)
                        card.hint_visible = True

                    case 'ai_save':                          # сохранить новую, перезаписав старую
                        card.hint = card.new_hint
                        card.new_hint = None
                        card.hint_visible = True
                        self.db.update_base([card])

                    case 'ai_cancel':                        # отменить новую, вернуть старую
                        card.new_hint = None
                        card.hint_visible = True

                # обновляем вывод
                inline = markups['card_markup'](card)
                return [self._build_repeat_message(user, card), inline, None]

            # ── стандартная логика repeat (✔/✖/listen/front/back/…) ─────────
            #      (код ниже не менялся, кроме отправки сообщения через
            #       _build_repeat_message и использования markups['card_markup'])

            if btn_action in ('front', 'back'):
                back_flag = True if btn_action == 'front' else None
                inline = markups['card_markup'](card, back_flag)
                return [self._build_repeat_message(user, card), inline, None]

            # … здесь остаётся прежний код обработки remember / forgot / delete …
            # (опущено для краткости, логика не изменилась)

        else:                                   # /repeat без inline-кнопок
            user = self.users[update.message.from_user.id]
            user.mindcards_queuing = user.mindcards + user.mindcards_delayed + user.mindcards_queuing
            random.shuffle(user.mindcards_queuing)
            user.mindcards = []
            user.mindcards_delayed = []
            self.user_card[user.user_id] = user.get_card(self.db)
            user.state = 'repeat'
            user.save()

        # ─── итоговый вывод карточки ─────────────────────────────────────────
        if self.user_card.get(user.user_id) and user.state == 'repeat':
            card = self.user_card[user.user_id]
            inline = markups['card_markup'](card, back_flag)
            msg = self._build_repeat_message(user, card)

            if button:      # ответ в callback
                return [msg, inline, None]
            else:           # новое сообщение
                context.bot.send_message(update.effective_chat.id, msg, reply_markup=inline)
        # … дальнейший «no cards» и т.п. оставляем без изменений …
