MESSAGE = {
    1: {'start': 'Это бот, имитирующий технику запоминания слов при помощи карточек\n'
                 'Пришлите слово, чтобы перевести его и создать карточку'
                 '\n/help для инструкции или'
                 '\n/settings для выбора изучаемых языков и языка интерфейса 🇷🇺·🇬🇧',
        'no cards': '✔ Вы повторили все карточки!\n💰 Можете помочь боту развиваться тут:',
        'create': 'Пришлите такое сообщение:\n[Слово]\n[Его перевод]',
        'translate': 'Отправьте слово для перевода\nВыбрать языки /settings',
        'delete': 'Вы точно хотите удалить карточку?',
        'default': 'Выберите необходимое действие:',
        'repeat': 'Повторение карточек, осталось: ',
        'help': ['Создайте карточку, чтобы запомнить слово:\n'
                 '1. Напишите слово в первой строке вашего сообщения\n'
                 '2. На второй строке пишете его перевод, который нужно будет вспомнить при повторении\n'
                 '3. Отправляете сообщение боту. '
                 'Если в вашем сообщении только одна строка - она будет переведена через Google translate\n'
                 '4. Бот присылает в ответ шаблон для создания карточки с кнопками:\n\n'
                 '💾 - сохранение карточки\n↻ - поменять слова местами\n🏴‍☠ - поставить флаг языка\n\n'
                 'Поменять языки перевода можно в настройках: /settings',
                 'Кнопка [Repeat]\n\n⌹ ⥅ ≣ ⥅ 20≟  Бот берёт карточки, '
                 'которые нужно повторить сегодня, из базы данных '
                 'и выдаёт их стопкой в 20 штук (можно изменить в /settings)\n'
                 '20≟ ⟳×6  Каждую карточку нужно повторить три раза с одной стороны и три раза с другой\n'
                 '19≟ ⥅ ⌹  Когда слово повторили, бот сохраняет карточку для следующего повторения '
                 'обратно в базу\n'
                 '≣ ⥅ 20≟  Из сегодняшних карточек в стопку добавляется новая\n'
                 'Если в /settings убрать галку "Подкидывать в стопку", то карточки для повторения не будут добавляться'
                 ', пока все 20 не будут повторены\n\n'
                 'Интервал повторения увеличивается от одного дня в два раза при каждом '
                 'удачном повторении.\n\n Кнопки:\n[✔] - нажимаете, если вы вспомнили значение карточки\n'
                 '[✖] - если не можете вспомнить (в этом случае вы смотрите значение '
                 'под спойлером и придумываете ассоциации, чтобы лучше запомнить, тут инструкция, как это правильно '
                 'делать: https://www.youtube.com/watch?v=N3DLSJ5E0CM )\n'
                 '[🚮] - удаление ненужной карточки\n[🎵] - позволяет прослушать, как звучит слово, голосом Google '
                 'translate. Язык озвучки - тот, который вы учите, из настроек /settings',
                 'КОМАНДЫ\n\n/load_all - загружает все ваши карточки, all можно заменить на число, тогда бот пришлет '
                 'вам карточки, которые нужно повторить за это количество дней\n'
                 '/load_user_cards - показывает карточки, которые пришло время повторить на данный момент\n'
                 '/settings - Настройки бота:\n'
                 '  - количество карточек, повторяемых одновременно\n  - язык интерфейса\n'
                 '  - язык для перевода по умолчанию\n  - язык с которого переводит по умолчанию',
                 'С вопросами и предложениями писать @Vardenfell'],
        'name_change': {
            'yes': 'Теперь вас зовут ',
            'fail': 'Вы должны набрать максимальное количество очков за неделю.\nИспользуйте /stats для проверки',
            'win': '\n﹋\nВы выиграли и можете выбрать имя!\n',
            'stats': 'Используйте команду /name ВАШЕ_ИМЯ\n'
                     'Изменений имени доступно: ',
            'no one': '\nНикто ещё не получил очков',
            'stats_head': 'Лидеры недели:\n﹏',
            'stats_info': '\n﹋\nПобедитель недели получает возможность изменить ник в таблице',
            'stats_nothing': 'Nobody got scores on this week yet',
        }
        },
    0: {
        'start': 'It is the bot for learning word by mind cards\nPress button for start of look /help for more',
        'no cards': '✔ You have repeated all the words!\n💰 You can help the bot grow here:',
        'create': 'Send a message looks like:\n[The Word]\n[Translation]',
        'translate': 'Send a word for translate\nChange langs /settings',
        'delete': 'Do you want to delete the Card?',
        'default': 'Choose what you need:',
        'repeat': 'Repeating of cards, left: ',
        'help': ['Button [Create]\n\nYou create a card to memorize a word\n'
                 'On one side is the word, on the other side is its meaning\n'
                 'Button [Translate]\n\nAn assistant to Create. You write the word, '
                 'the bot sends in response a template for creating a card with translation '
                 'from Google translate\n'
                 'Button [Repeat]\n\nThe bot takes all the cards you need to repeat today, '
                 'and gives them a stack of 20 pieces, '
                 'where each card must be repeated three times on one side and three times on the other\n'
                 'When the word is repeated, the bot removes the card from the stack '
                 'and adds a new one from todays cards\n'
                 'The interval for repeating cards increases from one day to twice '
                 'for each successful repetition\n'
                 '✔ button means you remember the meaning of the card, '
                 '✖ button means you can not remember '
                 '(in this case you look up the meaning under a spoiler and make up '
                 'associations to remember it better)\n'
                 'You can also delete a card if you do not need it anymore, with the 🚮 button, '
                 'and listen to how the word sounds in Google translate voice with 🎵\n'],
        'name_change': {
            'yes': 'Now your name is ',
            'fail': 'You need to get MAX week score for change your name\nUse /stats to check',
            'win': '\n﹋\nYou won and now can choose name!\n',
            'stats': 'Use /name YOUR_NICKNAME command\nNickname change available: ',
            'no one': '\nNo one get scores yet',
            'stats_head': 'Weekly leaderboard:\n﹏',
            'stats_info': '\n﹋\nWinner of week can change his leaderboard nickname',
            'stats_nothing': 'Никто ещё не заработал очков на этой неделе',

        }
    }
}

FLAGS = {
    'ru': '🇷🇺',
    'uk': '🇺🇦',
    'en': '🇬🇧',
    'fr': '🇫🇷',
    'es': '🇪🇸',
    'it': '🇮🇹',
    'de': '🇩🇪',
    'zh-CN': '🇨🇳',
    'ja': '🇯🇵',
    'ko': '🇰🇷',
    'hy': '🇦🇲',
    'ka': '🇬🇪',
    'tr': '🇹🇷',
    'sv': '🇸🇪',
}
INTERFACE = {
    # English interface
    0: {
        'settings': {
            0: 'Stack',
            1: 'Interface',
            2: 'To',
            3: 'From',
            4: '🔧 SETTINGS',
            5: ['Add', 'to', 'stack'],
            'cancel': 'Cancel',
            'change_name': 'Change name',
        },
    },
    # Russian interface
    1: {
        'settings': {
            0: 'Стопка',
            1: 'Интерфейс',
            2: 'На',
            3: 'С',
            4: '🔧 НАСТРОЙКИ',
            5: ['Подкидывать', 'в', 'стопку'],
            'cancel': 'Отмена',
            'change_name': 'Сменить имя',
        },
    },
    'interface_langs': ['en', 'ru'],
    'translate_langs': ['ru', 'en', 'uk', 'fr', 'es', 'it', 'de', 'zh-CN', 'ja', 'ko', 'hy', 'ka', 'tr', 'sv'],
}

TIMEZONE = 'Europe/Moscow'
RESET_HOUR = 8

