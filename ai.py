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

    user_model = ai_settings.MODEL
    # Если в настройках осталась старая модель GPT или модель не указана, используем gemini-3.1-flash-lite
    if not user_model or not user_model.startswith("gemini"):
        user_model = "gemini-3.1-flash-lite"

    # Список кандидатов для перебора (сначала выбранная модель, затем альтернативы)
    candidate_models = [user_model]
    alternatives = ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-2.0-flash"]
    for alt in alternatives:
        if alt not in candidate_models:
            candidate_models.append(alt)

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

    last_error = None
    for model_name in candidate_models:
        log.info("Requesting mnemonic hint using model: %s", model_name)
        url = f"{BASE_URL.rstrip('/')}/v1beta/models/{model_name}:generateContent?key={API_KEY}"

        # 2 попытки на каждую модель
        max_retries = 2
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=json_data,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    return result['candidates'][0]['content']['parts'][0]['text']
            except urllib.error.HTTPError as e:
                last_error = e
                # Повторяем при временных ошибках: 429 (Rate Limit), 500 (Internal Error), 503 (Service Unavailable)
                if e.code in (429, 500, 503):
                    if attempt < max_retries - 1:
                        log.warning(
                            "Gemini API (model: %s) returned status %d on attempt %d/%d. Retrying in %.1fs...",
                            model_name, e.code, attempt + 1, max_retries, retry_delay
                        )
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        log.warning(
                            "Gemini API (model: %s) failed with status %d after %d attempts. Trying fallback model...",
                            model_name, e.code, max_retries
                        )
                        break  # переходим к следующей модели из candidate_models
                else:
                    # Другие HTTP ошибки (например, 404 или 400) - переключаемся на следующую модель без повторов
                    log.warning(
                        "Gemini API (model: %s) returned non-retryable status %d: %s. Trying fallback model...",
                        model_name, e.code, e.reason
                    )
                    break
            except Exception as e:
                last_error = e
                log.warning("Unexpected error with model %s: %s. Trying fallback model...", model_name, str(e))
                break

    # Если перебрали все модели и ни одна не сработала
    log.error("All Gemini models failed to generate mnemonic hint.")
    if last_error:
        raise last_error
    else:
        raise RuntimeError("All Gemini models failed")



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