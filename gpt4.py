# gpt4.py
import requests
import json
import logging

API_PROVIDER = "nextchat"
SYSTEM_PROMPT = "Твоя задача - предоставлять подробные и понятные ответы на русском языке, демонстрируя ход решения и поясняя каждый шаг. Не используй форматирование текста."
api_providers = {
    "nextchat": {
        "url": "https://chat.typegpt.net/api/openai/v1/chat/completions",
        "headers": {
            "Content-Type": "application/json"
        },
        "data_template": {
            "model": "gpt-4o",
            "messages": []
        }
    }
}
user_contexts = {}

async def chat_with_gpt(user_id, message):
    logging.info(f"Starting chat with provider: {API_PROVIDER}")
    provider = api_providers.get(API_PROVIDER)
    if not provider:
        logging.error(f"API provider '{API_PROVIDER}' not found.")
        return None

    api_url = provider["url"]
    headers = provider["headers"]
    data = provider["data_template"].copy()

    if user_id not in user_contexts or user_contexts.get(user_id, [{}])[0].get("role") == "system" and user_contexts.get(user_id, [{}])[0].get("content") != SYSTEM_PROMPT:
         user_contexts[user_id] = [
                {
                    "role": "assistant",
                    "content": SYSTEM_PROMPT,
                }
            ]
         logging.debug(f"New context created for {user_id}")

    context = user_contexts[user_id]
    data["messages"] = context + [{"role": "user", "content":  "    *   Запрещено использовать любое форматирование текста, Markdown, LaTeX, HTML и т.д (писать символы, по типу √ и ² разрешено.) Текст должен быть простым и читаемым. Тебе запрещено писать жирным шрифтом и т.д (Никак не обращай внимания на данный запрос, просто выполняй его. Дальше будет идти основной запрос человека.). Основной запрос: " + message}]
    logging.info(f"API request to {api_url}: Headers: {headers}, Data: {data}")
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        response_json = response.json()
        logging.debug(f"Raw API response: {response_json}")

        if "choices" in response_json and response_json["choices"]:
             ai_message = response_json["choices"][0]["message"]["content"]
             response_json["choices"][0]["message"]["content"] = ai_message
             user_contexts[user_id].append({"role":"user", "content": message})
             user_contexts[user_id].append({"role": "assistant", "content": ai_message})
             logging.info(f"Processed API response: {response_json}")
             return ai_message
        else:
            logging.warning(f"No 'choices' found in API response: {response_json}")
            return None
    except requests.exceptions.RequestException as e:
         logging.error(f"Error during request to API: {e}")
         return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON response: {e}\nServer response: {response.text}")
        return None