from openai import OpenAI
from config import OPENAI_API_KEY
import ai_settings

client = OpenAI(api_key=OPENAI_API_KEY)


def get_mem_hint(word, translation):
    """
    Генерирует мнемонику-подсказку при помощи GPT-модели.
    """
    data = {'word': word, 'translation': translation}
    messages = [
        {"role": "system", "content": ai_settings.CONTENT},
        {"role": "user", "content": ai_settings.PROMPT.format(**data)},
    ]
    response = client.chat.completions.create(
        model=ai_settings.MODEL,
        messages=messages,
    )
    return response.choices[0].message.content


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