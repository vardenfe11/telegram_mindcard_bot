import urllib.request
import json
import os
import logging
import ai_settings

log = logging.getLogger(__name__)

# Попытка импортировать ключ из telegram_token
try:
    from telegram_token import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = None

# Если ключ не задан в telegram_token, пробуем взять из переменной окружения
API_KEY = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")


def get_mem_hint(word, translation):
    """
    Генерирует мнемонику-подсказку при помощи Google Gemini API (REST).
    """
    if not API_KEY:
        raise ValueError(
            "Google Gemini API key is not configured. "
            "Please set GEMINI_API_KEY in telegram_token.py or as an environment variable."
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{ai_settings.MODEL}:generateContent?key={API_KEY}"

    data = {'word': word, 'translation': translation}
    prompt = ai_settings.PROMPT.format(**data)

    payload = {
        "systemInstruction": {
            "parts": [{"text": ai_settings.CONTENT}]
        },
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }

    json_data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=json_data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        log.exception("Error while generating hint via Gemini API REST")
        raise e



# ───────── NEW ───────────────────────────────────────────────────────────────
def ensure_hint(card, db):
    """
    Возвращает сохранённую подсказку либо генерирует новую и записывает её в БД.
    """
    if card.hint:
        return card.hint

    card.hint = get_mem_hint(card.word_one, card.word_two)
    db.update_base([card])
    return card.hint
# ─────────────────────────────────────────────────────────────────────────────
#
# for m in client.models.list():
#     print(m.id)          # доступные модели
# get_mem_hint('word', 'слово')