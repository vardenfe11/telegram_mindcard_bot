from math import floor

from telegram import KeyboardButton, InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup
from telegram_token import *
from settings import *


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    """
    Builds button menu from:
    :param buttons: list of InlineKeyboardButton
    :param n_cols: number of menu columns
    :param header_buttons: menu is above message text
    :param footer_buttons: menu is below message text
    :return: args for InlineKeyboardMarkup
    """
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


repeat = KeyboardButton('Repeat✨')
new_word = KeyboardButton('Create')
translate = KeyboardButton('Translate')
remember = KeyboardButton("Remember")
forgot = KeyboardButton("Forgot")
delete = KeyboardButton("Delete")
yes = KeyboardButton("Yes")
no = KeyboardButton("No")

markup_start = ReplyKeyboardMarkup(build_menu([repeat], n_cols=2), resize_keyboard=True)
markup_send_card = ReplyKeyboardMarkup([[remember, forgot], [new_word, delete]], resize_keyboard=True)
markup_translate = markup_start
markup_delete = ReplyKeyboardMarkup(build_menu([yes, no, new_word, repeat], n_cols=2), resize_keyboard=True)
markup_create = markup_start


def translate_markup():
    # keyboard for translated words
    message_markup = InlineKeyboardMarkup([
        [(InlineKeyboardButton(f'✖', callback_data=f'message_delete None None')),
         (InlineKeyboardButton(f'↻', callback_data=f'save_translated reverse')),
         (InlineKeyboardButton(f'🏴‍☠', callback_data=f'save_translated flag'))],
        [(InlineKeyboardButton(f'💾', callback_data=f'save_translated save'))]
    ])
    # message_markup = InlineKeyboardMarkup(build_menu(save_button, n_cols=3))
    return message_markup


def donate_markup():
    # keyboard for message after user repeated all today cards
    save_button = [
        (InlineKeyboardButton('Yoomoney', url=YOOMONEY)),
        (InlineKeyboardButton('PayPal', url=PAYPAL)),
    ]
    message_markup = InlineKeyboardMarkup(build_menu(save_button, n_cols=2))
    return message_markup


def page_markup(pages_list, button):
    # keyboard for pages in long lists (/load, /load_today_cards, /help bot commands)
    func_name = button[0]
    new_buttons = []
    next_page = int(button[2])
    if next_page == 0 and len(pages_list) > 2:
        new_buttons.append(InlineKeyboardButton(f'▷▷',
                                                callback_data=f'{func_name} {button[1]} {len(pages_list) - 1}'))
    elif next_page != 0 and len(pages_list) > 1:
        new_buttons.append(InlineKeyboardButton(f'◁',
                                                callback_data=f'{func_name} {button[1]} {next_page - 1}'))
    if len(pages_list) > 1:
        new_buttons.append(InlineKeyboardButton(f'{next_page + 1}',
                                                callback_data=f'{func_name} {button[1]} {next_page}'))
    else:
        new_buttons.append(InlineKeyboardButton(f'↻',
                                                callback_data=f'{func_name} {button[1]} {next_page}'))

    if next_page == len(pages_list) - 1 and len(pages_list) > 2:
        new_buttons.append(InlineKeyboardButton(f'◁◁',
                                                callback_data=f'{func_name} {button[1]} 0'))
    elif next_page != len(pages_list) - 1 and len(pages_list) > 1:
        new_buttons.append(InlineKeyboardButton(f'▷',
                                                callback_data=f'{func_name} {button[1]} {next_page + 1}'))
    message_markup = InlineKeyboardMarkup(build_menu(new_buttons, n_cols=3))
    return message_markup


def list_step(proc_list, current_step, step_change):
    """
    Cycle change from list
    :param proc_list: list of changed parameters
    :param current_step: currents value (from user settings)
    :param step_change: change value (+1, -1) for button
    :return: list value number for changed parameter
    """
    step_change = int(step_change)
    if current_step + step_change >= len(proc_list):
        next_step = current_step + step_change - len(proc_list)
    elif current_step + step_change < 0:
        next_step = len(proc_list) + current_step + step_change
    else:
        next_step = current_step + step_change
    return next_step


def settings_markup(user, button):
    # keyboard for /settings bot menu
    func_name = button[0]
    if button:
        if button[1] == 'stack_size':
            stack_change = int(button[2])
            if 0 < (user.stack_size + stack_change) <= 1000:
                user.stack_size += stack_change
                user.save()
        elif button[1] == 'interface_lang':
            new_lang = int(button[2])
            user.interface_lang = new_lang
            user.save()
        elif button[1] == 'first_lang':
            new_lang = int(button[2])
            user.first_lang = new_lang
            user.save()
        elif button[1] == 'second_lang':
            new_lang = int(button[2])
            user.second_lang = new_lang
            user.save()
        elif button[1] == 'add_cards':
            if button[2] == 'true':
                user.add_cards_to_stack = True
            elif button[2] == 'false':
                user.add_cards_to_stack = False
            user.save()

    def add_card_button(check):
        if check == True:
            return InlineKeyboardButton('✓', callback_data=f'{func_name} add_cards false')
        else:
            return InlineKeyboardButton(' ', callback_data=f'{func_name} add_cards true')

    interface_lang_steps = [
        list_step(INTERFACE['interface_langs'], user.interface_lang, -1),
        list_step(INTERFACE['interface_langs'], user.interface_lang, 1)
    ]
    first_lang_steps = [
        list_step(INTERFACE['translate_langs'], user.first_lang, -1),
        list_step(INTERFACE['translate_langs'], user.first_lang, 1)
    ]
    second_lang_steps = [
        list_step(INTERFACE['translate_langs'], user.second_lang, -1),
        list_step(INTERFACE['translate_langs'], user.second_lang, 1)
    ]
    message_markup = InlineKeyboardMarkup(build_menu([
        InlineKeyboardButton(INTERFACE[user.interface_lang]['settings'][0],
                             callback_data=f'{func_name} None None'),
        InlineKeyboardButton('-5', callback_data=f'{func_name} stack_size -5'),
        InlineKeyboardButton(f'≺{user.stack_size}≻', callback_data=f'{func_name} None None'),
        InlineKeyboardButton('+5', callback_data=f'{func_name} stack_size +5'),

        InlineKeyboardButton(INTERFACE[user.interface_lang]['settings'][1], callback_data=f'{func_name} None None'),
        InlineKeyboardButton(FLAGS[INTERFACE['interface_langs'][interface_lang_steps[0]]],
                             callback_data=f'{func_name} interface_lang {interface_lang_steps[0]}'),
        InlineKeyboardButton('≺' + FLAGS[INTERFACE['interface_langs'][user.interface_lang]] +
                             INTERFACE['interface_langs'][user.interface_lang] + '≻',
                             callback_data=f'{func_name} None None'),
        InlineKeyboardButton(FLAGS[INTERFACE['interface_langs'][interface_lang_steps[1]]],
                             callback_data=f'{func_name} interface_lang {interface_lang_steps[1]}'),

        InlineKeyboardButton(INTERFACE[user.interface_lang]['settings'][2], callback_data=f'{func_name} None None'),
        InlineKeyboardButton(FLAGS[INTERFACE['translate_langs'][first_lang_steps[0]]],
                             callback_data=f'{func_name} first_lang {first_lang_steps[0]}'),
        InlineKeyboardButton('≺' + FLAGS[INTERFACE['translate_langs'][user.first_lang]] +
                             INTERFACE['translate_langs'][user.first_lang] + '≻',
                             callback_data=f'{func_name} None None'),
        InlineKeyboardButton(FLAGS[INTERFACE['translate_langs'][first_lang_steps[1]]],
                             callback_data=f'{func_name} first_lang {first_lang_steps[1]}'),

        InlineKeyboardButton(INTERFACE[user.interface_lang]['settings'][3], callback_data=f'{func_name} None None'),
        InlineKeyboardButton(FLAGS[INTERFACE['translate_langs'][second_lang_steps[0]]],
                             callback_data=f'{func_name} second_lang {second_lang_steps[0]}'),
        InlineKeyboardButton('≺' + FLAGS[INTERFACE['translate_langs'][user.second_lang]] +
                             INTERFACE['translate_langs'][user.second_lang] + '≻',
                             callback_data=f'{func_name} None None'),
        InlineKeyboardButton(FLAGS[INTERFACE['translate_langs'][second_lang_steps[1]]],
                             callback_data=f'{func_name} second_lang {second_lang_steps[1]}'),

        InlineKeyboardButton(INTERFACE[user.interface_lang]['settings'][5][0], callback_data=f'{func_name} None None'),
        InlineKeyboardButton(INTERFACE[user.interface_lang]['settings'][5][1], callback_data=f'{func_name} None None'),
        InlineKeyboardButton(INTERFACE[user.interface_lang]['settings'][5][2], callback_data=f'{func_name} None None'),
        add_card_button(user.add_cards_to_stack),
    ], n_cols=4), resize_keyboard=False)

    return message_markup


def fast_lang_markup(user, button):
    # keyboard for /settings bot menu
    func_name = button[0]
    if button:
        if button[1] == 'interface_lang':
            new_lang = int(button[2])
            user.interface_lang = new_lang
            user.save()

    interface_lang_steps = [
        list_step(INTERFACE['interface_langs'], user.interface_lang, -1),
        list_step(INTERFACE['interface_langs'], user.interface_lang, 1)
    ]

    message_markup = InlineKeyboardMarkup(build_menu([
        InlineKeyboardButton(FLAGS[INTERFACE['interface_langs'][interface_lang_steps[0]]] + '◁',
                             callback_data=f'{func_name} interface_lang {interface_lang_steps[0]}'),
    ], n_cols=1), resize_keyboard=False)

    return message_markup


def delete_markup(button):
    func_name = button[0]
    message_markup = InlineKeyboardMarkup(build_menu([
        (InlineKeyboardButton(f'✔️Yes', callback_data=f'{func_name} {button[1]} yes')),
        (InlineKeyboardButton(f'✖️No', callback_data=f'{func_name} {button[1]} no')),
    ], n_cols=2), resize_keyboard=True)
    return message_markup


def change_name_markup(user):
    change_name_text = INTERFACE[user.interface_lang]['settings']['change_name'] + f'({user.nickname_change})'
    cancel_text = INTERFACE[user.interface_lang]['settings']['cancel']
    message_markup = InlineKeyboardMarkup(build_menu([
        (InlineKeyboardButton(f'{change_name_text}', callback_data=f'change_name None yes')),
        (InlineKeyboardButton(f'{cancel_text}', callback_data=f'change_name None no')),
    ], n_cols=2), resize_keyboard=True)
    return message_markup


moon = ['⓿', '➊', '➋', '➌', '➍']


def card_markup(card, back=None):
    """
    Формирует inline-клавиатуру для режима повторения одной карточки
    с учётом логики показа/управления подсказками.
    """
    func_repeat = 'repeat_cards'
    func_hint = 'hint'

    # ───────────  Выбор отображаемого слова  ───────────
    if (card.today_reverse_repeat == 0 and card.today_repeat - card.repeat_mistake < 3) or \
            card.today_repeat < divmod(6 + card.repeat_mistake, 2)[0]:
        w_front, w_back = card.word_one, card.word_two
    else:
        w_back, w_front = card.word_one, card.word_two

    if back:
        word = w_back
        reverse = 'back'
    else:
        word = w_front
        reverse = 'front'

    if card.repeat_lvl < 4:
        word = f'{moon[int(floor(card.repeat_lvl)) + 1]} {word}'

    # ───────────  Верхний ряд — управление подсказками  ───────────
        # ⏳ Кнопка генерации «закрыта» во время ожидания ответа
    if getattr(card, 'hint_pending', False):
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(f'🗿 {card.word_one}', callback_data='wait')]]
        )
    elif card.hint_shown:
        if card.temp_hint:                                       # показана НОВАЯ
            hint_row = [
                InlineKeyboardButton('✅', callback_data=f'{func_hint} {card.card_id} replace'),
                InlineKeyboardButton('↩️', callback_data=f'{func_hint} {card.card_id} cancel'),
            ]
        else:                                                    # показана СОХРАНЁННАЯ
            hint_row = [
                InlineKeyboardButton('♻️', callback_data=f'{func_hint} {card.card_id} new'),
                InlineKeyboardButton('🗑', callback_data=f'{func_hint} {card.card_id} delete'),
            ]
    else:                                                        # подсказка скрыта
        hint_row = [
            InlineKeyboardButton('💡', callback_data=f'{func_hint} {card.card_id} toggle'),
        ]

    # ───────────  Остальные ряды (как раньше, но без старой 💡) ───────────
    buttons = [
        hint_row,
        [InlineKeyboardButton(word, callback_data=f'{func_repeat} {card.card_id} {reverse}')],
        [
            InlineKeyboardButton(f'✔{card.today_repeat + card.today_reverse_repeat - card.repeat_mistake}',
                                 callback_data=f'{func_repeat} {card.card_id} remember'),
            InlineKeyboardButton(f'✖{card.repeat_mistake}', callback_data=f'{func_repeat} {card.card_id} forgot'),
        ],
        [
            InlineKeyboardButton('🎵', callback_data=f'{func_repeat} {card.card_id} listen{reverse}'),
            InlineKeyboardButton('🗑', callback_data=f'{func_repeat} {card.card_id} delete'),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
def message_delete(word):
    save_button = [
        (InlineKeyboardButton(f'{word} ✖', callback_data=f'message_delete None None')),
    ]
    message_markup = InlineKeyboardMarkup(build_menu(save_button, n_cols=2))
    return message_markup


markups = {'start': markup_start,
           'send_card': markup_send_card,
           'translate': markup_translate,
           'create': markup_create,
           'delete': markup_delete,
           'translate_markup': translate_markup,
           'delete_markup': delete_markup,
           'card_markup': card_markup,
           'page_markup': page_markup,
           'donate_markup': donate_markup,
           'settings': settings_markup,
           'message_delete': message_delete,
           'change_name_markup': change_name_markup,
           'fast_lang_markup': fast_lang_markup,
           }
