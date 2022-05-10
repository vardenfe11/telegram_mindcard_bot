from telegram import KeyboardButton, InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup


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

markup_start = ReplyKeyboardMarkup(build_menu([repeat, new_word, translate], n_cols=2))
markup_send_card = ReplyKeyboardMarkup([[remember, forgot], [new_word, translate, delete]])
markup_translate = ReplyKeyboardMarkup(build_menu([new_word, repeat], n_cols=2))
markup_delete = ReplyKeyboardMarkup(build_menu([yes, no, new_word, repeat], n_cols=2))
markup_create = ReplyKeyboardMarkup([[repeat, translate]])


def translate_markup():
    save_button = [
        (InlineKeyboardButton(f'Save as card 💾', callback_data=f'save_translated save')),
        (InlineKeyboardButton(f'Save reverse ↕💾', callback_data=f'save_translated reverse')),
                   ]
    message_markup = InlineKeyboardMarkup(build_menu(save_button, n_cols=1))
    return message_markup


def page_markup(pages_list, button):
    func_name = button[0]
    new_buttons = []
    next_page = int(button[2])
    if next_page > 0:
        new_buttons.append(InlineKeyboardButton(f'{next_page} ⬅',
                                                callback_data=f'{func_name} {button[1]} {next_page - 1}'))
    if next_page < len(pages_list) - 1:
        new_buttons.append(InlineKeyboardButton(f'➡ {next_page + 2}',
                                                callback_data=f'{func_name} {button[1]} {next_page + 1}'))
    message_markup = InlineKeyboardMarkup(build_menu(new_buttons, n_cols=2))
    return message_markup


def card_markup(card):
    func_name = 'repeat_cards'
    buttons = [
        InlineKeyboardButton(f'✔{card.today_repeat + card.today_reverse_repeat - card.repeat_mistake}',
                             callback_data=f'{func_name} {card.card_id} remember'),
        InlineKeyboardButton(f'️❓{card.repeat_mistake}', callback_data=f'{func_name} {card.card_id} forgot')
    ]
    message_markup = InlineKeyboardMarkup(build_menu(buttons, n_cols=2))
    return message_markup


reply_markup = InlineKeyboardMarkup(build_menu([
    InlineKeyboardButton('⬅', callback_data='onboarding_step2_step1'),
    InlineKeyboardButton('➡', callback_data='onboarding_step2_step3'),
],
    n_cols=2))
markups = {'start': markup_start,
           'send_card': markup_send_card,
           'translate': markup_translate,
           'create': markup_create,
           'delete': markup_delete,
           'inline': reply_markup
           }
