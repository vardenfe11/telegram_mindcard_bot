import telebot

repeat = telebot.types.KeyboardButton('Repeat')
new_word = telebot.types.KeyboardButton('Create')
translate = telebot.types.KeyboardButton('Translate')
translate_create = telebot.types.KeyboardButton('Create from translated')
remember = telebot.types.KeyboardButton("Remember")
forgot = telebot.types.KeyboardButton("Forgot")
delete = telebot.types.KeyboardButton("Delete")
yes = telebot.types.KeyboardButton("Yes")
no = telebot.types.KeyboardButton("No")


markup_start = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
markup_start.add(repeat)
markup_start.add(new_word)
markup_start.add(translate)

markup_send_card = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
# create buttons lines
markup_send_card.row(remember, forgot)
markup_send_card.row(new_word, translate, delete)

# create buttons
markup_translate = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
# create buttons lines
markup_translate.row(new_word, repeat)
markup_translate.row(translate_create)

markup_create = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
# create buttons lines
markup_create.row(repeat, translate)

markup_delete = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
markup_delete.row(yes, no)
markup_delete.row(new_word, repeat)

markups = {'start': markup_start,
           'send_card': markup_send_card,
           'translate': markup_translate,
           'create': markup_create,
           'delete': markup_delete,
           }
