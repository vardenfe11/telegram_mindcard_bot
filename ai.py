from openai import OpenAI
from config import OPENAI_API_KEY
import ai_settings

client = OpenAI(api_key=OPENAI_API_KEY)


def get_mem_hint(word, translation):
    # Формируем сообщение
    data = {'word': word, 'translation': translation}
    messages = [
        {"role": "system",
         "content": ai_settings.CONTENT},
        {"role": "user",
         "content": ai_settings.PROMPT.format(**data)}
    ]
    response = client.chat.completions.create(
        model=ai_settings.MODEL,
        messages=messages,
        temperature=0.7
    )
    ai_response = response.choices[0].message.content
    return ai_response


# Пример использования функции

if __name__ == '__main__':
    word = "apple"
    translation = "яблоко"
    technique = get_mem_hint(word, translation)
    print(f"Инструкция по запоминанию для слова '{word}':\n{technique}")
