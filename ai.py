import urllib.request
import json
import os
import logging
import time
import ai_settings

log = logging.getLogger(__name__)

# Попытка импортировать ключ и базовый URL из telegram_token по отдельности
try:
    from telegram_token import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = None

try:
    from telegram_token import GEMINI_BASE_URL
except ImportError:
    GEMINI_BASE_URL = None

# Если ключ не задан в telegram_token, пробуем взять из переменной окружения
API_KEY = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
if API_KEY:
    API_KEY = API_KEY.strip()

# Базовый URL для запросов (полезно для обхода блокировок по IP)
BASE_URL = GEMINI_BASE_URL or os.environ.get("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com"


def get_mem_hint(word, translation):
    """
    Генерирует мнемонику-подсказку при помощи Google Gemini API (REST).
    """
    if not API_KEY:
        raise ValueError(
            "Google Gemini API key is not configured. "
            "Please set GEMINI_API_KEY in telegram_token.py or as an environment variable."
        )

    model_name = ai_settings.MODEL
    # Если в настройках осталась старая модель GPT или модель не указана, используем gemini-3.5-flash
    if not model_name or not model_name.startswith("gemini"):
        model_name = "gemini-3.5-flash"

    log.info("Requesting mnemonic hint using model: %s", model_name)
    url = f"{BASE_URL.rstrip('/')}/v1beta/models/{model_name}:generateContent?key={API_KEY}"

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

    max_retries = 3
    retry_delay = 1.0  # начальная задержка в секундах

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['candidates'][0]['content']['parts'][0]['text']
        except urllib.error.HTTPError as e:
            # Повторяем при временных ошибках: 429 (Rate Limit), 500 (Internal Server Error), 503 (Service Unavailable)
            if e.code in (429, 500, 503) and attempt < max_retries - 1:
                log.warning(
                    "Gemini API returned status %d on attempt %d/%d. Retrying in %.1fs...",
                    e.code, attempt + 1, max_retries, retry_delay
                )
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            log.exception("HTTP Error while generating hint via Gemini API REST")
            raise e
        except Exception as e:
            log.exception("Unexpected error while generating hint via Gemini API REST")
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