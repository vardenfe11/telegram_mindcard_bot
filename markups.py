from telegram import KeyboardButton, InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup
from telegram_token import *


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


repeat = KeyboardButton('Repeat')
new_word = KeyboardButton('Create')
translate = KeyboardButton('Translate')
# translate_create = KeyboardButton('Create from translated')
remember = KeyboardButton("Remember")
forgot = KeyboardButton("Forgot")
delete = KeyboardButton("Delete")
yes = KeyboardButton("Yes")
no = KeyboardButton("No")

markup_start = ReplyKeyboardMarkup(build_menu([repeat, new_word, translate], n_cols=3), resize_keyboard=True)
markup_send_card = ReplyKeyboardMarkup([[remember, forgot], [new_word, translate, delete]], resize_keyboard=True)
markup_translate = markup_start
markup_delete = ReplyKeyboardMarkup(build_menu([yes, no, new_word, repeat], n_cols=2), resize_keyboard=True)
markup_create = markup_start


def translate_markup():
    save_button = [
        (InlineKeyboardButton(f'💾', callback_data=f'save_translated save')),
        (InlineKeyboardButton(f'↻', callback_data=f'save_translated reverse')),
        (InlineKeyboardButton(f'🏁', callback_data=f'save_translated flag')),
    ]
    message_markup = InlineKeyboardMarkup(build_menu(save_button, n_cols=3))
    return message_markup


def donate_markup():
    save_button = [
        (InlineKeyboardButton('Yoomoney', url=YOOMONEY)),
        (InlineKeyboardButton('PayPal', url=PAYPAL)),
    ]
    message_markup = InlineKeyboardMarkup(build_menu(save_button, n_cols=2))
    return message_markup


def page_markup(pages_list, button):
    func_name = button[0]
    new_buttons = []
    next_page = int(button[2])
    if next_page > 0:
        new_buttons.append(InlineKeyboardButton(f'◁',
                                                callback_data=f'{func_name} {button[1]} {next_page - 1}'))
    new_buttons.append(InlineKeyboardButton(f'{next_page + 1}',
                                            callback_data=f'{func_name} {button[1]} {next_page}'))
    if next_page < len(pages_list) - 1:
        new_buttons.append(InlineKeyboardButton(f'▷',
                                                callback_data=f'{func_name} {button[1]} {next_page + 1}'))
    message_markup = InlineKeyboardMarkup(build_menu(new_buttons, n_cols=3))
    return message_markup


def delete_markup(button):
    func_name = button[0]
    message_markup = InlineKeyboardMarkup(build_menu([
        (InlineKeyboardButton(f'✔️Yes', callback_data=f'{func_name} {button[1]} yes')),
        (InlineKeyboardButton(f'✖️No', callback_data=f'{func_name} {button[1]} no')),
    ], n_cols=2), resize_keyboard=True)
    return message_markup


def card_markup(card):
    func_name = 'repeat_cards'
    buttons = [
        InlineKeyboardButton(f'✔{card.today_repeat + card.today_reverse_repeat - card.repeat_mistake}',
                             callback_data=f'{func_name} {card.card_id} remember'),
        InlineKeyboardButton(f'✖{card.repeat_mistake}', callback_data=f'{func_name} {card.card_id} forgot'),
        InlineKeyboardButton(f'🎵', callback_data=f'{func_name} {card.card_id} listen'),
        InlineKeyboardButton(f'🚮', callback_data=f'{func_name} {card.card_id} delete')
    ]
    message_markup = InlineKeyboardMarkup(build_menu(buttons, n_cols=2))
    return message_markup

#
# reply_markup = InlineKeyboardMarkup(build_menu([
#     InlineKeyboardButton('⬅', callback_data='onboarding_step2_step1'),
#     InlineKeyboardButton('➡', callback_data='onboarding_step2_step3'),
# ],
#     n_cols=2))
markups = {'start': markup_start,
           'send_card': markup_send_card,
           'translate': markup_translate,
           'create': markup_create,
           'delete': markup_delete,
           # 'inline': reply_markup,
           'translate_markup': translate_markup,
           'delete_markup': delete_markup,
           'card_markup': card_markup,
           'page_markup': page_markup,
           'donate_markup': donate_markup,
           }
