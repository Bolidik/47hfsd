# talkai.py
import requests
import json
import base64
import os
from PIL import Image
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOG_FILE = "talkai_log.txt"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

FIREBASE_TOKEN_URL = "https://securetoken.googleapis.com/v1/token?key=AIzaSyAGZ5bS-Taq9S1KZf-LgpppoKlZ-LcC7bo"
CHAT_API_URL = "http://195.123.212.76/chat/v2"
REFRESH_TOKEN = "AMf-vBxScoD-oXmcRH-HoNDhMslMw7vHuHq_tT7uX4HBDnBR7S41e5n6_S8tLbB7VSf7mPZSjw8nsk5swWKbGc6icQBN9pI2kzzcEay3gxnBdYRKcV2KDJt_CW5M00MWnNiazRRMxPJo3ObezkEs_hMurnlAV4-Lz_Kne8t4a1Lqoexm3wgv-KrJjvSRnmAgBTcR0xU7DzxXzvgH2DCbzsWGiYESYwQolhdXHSGCJ3JuAX6BDKPDNlIZydui7n7182APO_w3SigfITFm2nGVVxRlZDu_qJ40Zyk-1dfg2j08niTBieHYkolH1AWNID3w_NjGQSzKC88PRJl0_nh7C-8zPl13EFxCbF_VbsvWbODrOq1lSLgC4iGc5zWvtrRFKAEvyORZqni0mXkg2ItGdd5N-uvCZhLXHKpzr108-bHXstWJ7frgCao"  # Замените на свой

SYSTEM_PROMPT = "Ты — высококвалифицированный ассистент с искусственным интеллектом, разработанный для предоставления точных, подробных и понятных ответов на русском языке. Твоя основная задача — предоставлять исчерпывающие, точные и легко понятные ответы на русском языке. При решении задач или выполнении запросов, требующих последовательных действий, ты должен демонстрировать ход решения, подробно объясняя каждый шаг и используемые методы. Твои объяснения должны быть максимально подробными и ясными, чтобы пользователь мог полностью понять логику и процесс твоего ответа. Важно: не используй никакое форматирование текста, такое как выделение жирным шрифтом. Пиши настолько подробно, насколько это возможно, не упуская никаких деталей, которые могут быть важны для понимания. При решении математических, научных или технических задач, а также при переводе текстов, твоя точность должна быть абсолютной. Проверяй факты и терминологию, чтобы избежать ошибок и неточностей. Соблюдай эти инструкции неукоснительно при каждом ответе."

def get_bearer_token(refresh_token):
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 15; 2201117SY Build/AP3A.241105.008)',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip',
        'Content-Type': 'application/json',
        'X-Android-Package': 'com.ai_mnogoseo.talkai',
        'X-Android-Cert': 'F4E427F62709F44CD3261837FAFCA33730DACD69',
        'Accept-Language': 'ru-RU, en-US',
        'X-Client-Version': 'Android/Fallback/X23000000/FirebaseCore-Android',
        'X-Firebase-GMPID': '1:566000701917:android:8ac4d8163ac1b2bac62634',
        'X-Firebase-Client': 'H4sIAAAAAAAA_6tWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA',
        'X-Firebase-AppCheck': 'eyJlcnJvciI6IlVOS05PV05fRVJST1IifQ==',
    }
    data = {"grantType": "refresh_token", "refreshToken": refresh_token}
    try:
        response = requests.post(FIREBASE_TOKEN_URL, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting token: {e}")
        if hasattr(response, 'text'):
            logging.error(f"Server response: {response.text}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logging.error(f"Error parsing token response: {e}")
        if hasattr(response, 'text'):
            logging.error(f"Server response: {response.text}")
        return None

def encode_image(image_path):
    logging.info(f"Encoding image: {image_path}")
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            logging.info(f"Image encoded successfully. First 50 chars: {encoded_string[:50]}")
            return encoded_string
    except FileNotFoundError:
        logging.error(f"File not found: {image_path}")
        return None
    except Exception as e:
        logging.error(f"Error encoding image: {e}")
        return None

def send_message(bearer_token, message, image_base64=None, image_caption=None):
    headers = {
        'User-Agent': 'Dart/3.5 (dart:io)',
        'Accept-Encoding': 'gzip',
        'Content-Type': 'application/json',
        'authorization': f'Bearer {bearer_token}',
    }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if image_base64:
        messages.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}]})
    if message:
        messages.append({"role": "user", "content": [{"type": "text", "text": message}]})
    if image_caption:
        messages.append({"role": "user", "content": [{"type": "text", "text": image_caption}]})

    data = {
        "premium": False,
        "messages": messages,
        "model": "gpt-4o",
        "temperature": 1.0,
        "role": "",
        "language": "ru",
        "creativity": 0.5
    }
    logging.info(f"Sending message to TalkAI API. Data: {data}")
    try:
        response = requests.post(CHAT_API_URL, headers=headers, json=data, timeout=30, verify=False)
        response.raise_for_status()
        logging.info(f"TalkAI API response: {response.json()}")
        return response.json().get('message')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending message: {e}")
        if hasattr(response, 'text'):
            logging.error(f"Server response: {response.text}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logging.error(f"Error parsing message response: {e}")
        if hasattr(response, 'text'):
            logging.error(f"Server response: {response.text}")
        return None

async def chat_with_talkai(message, image_path=None, image_caption=None):
    bearer_token = get_bearer_token(REFRESH_TOKEN)
    if not bearer_token:
        return "Failed to get TalkAI token."

    image_base64 = None
    if image_path:
        logging.info(f"Processing image for TalkAI: {image_path}")
        image_base64 = encode_image(image_path)
        if image_base64:
            logging.info(f"Image encoded successfully. First 50 chars: {image_base64[:50]}")
        else:
            logging.warning("Image encoding failed.")

    response = send_message(bearer_token, message, image_base64, image_caption)
    return response

async def get_chat_response(user_id: int, message_text: str, model: str, image_path: str = None, image_caption: str = None):
    if model == "gpt4":
        pass
    elif model == "talkai":
        return await chat_with_talkai(message_text, image_path, image_caption)
    return None

if __name__ == "__main__":
    async def test_chat():
        message = "Tell me about yourself."
        response = await chat_with_talkai(message)
        if response:
            print(f"TalkAI response (text): {response}")

        image_path = 'path/to/your/image.jpg'  # Replace with a valid path
        if os.path.exists(image_path):
            response_with_image = await chat_with_talkai("What is in this picture?", image_path=image_path, image_caption="A beautiful landscape")
            if response_with_image:
                print(f"TalkAI response (with image and caption): {response_with_image}")
        else:
            print(f"Image file not found: {image_path}")

    import asyncio
    asyncio.run(test_chat())