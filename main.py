# main.py
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegraph import Telegraph
import html
from gpt4 import chat_with_gpt, user_contexts as gpt4_contexts
from talkai import chat_with_talkai
from config import BOT_TOKEN, TELEGRAPH_TOKEN, LOG_FILE, TELEGRAM_MESSAGE_LIMIT

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)
telegraph = Telegraph(access_token=TELEGRAPH_TOKEN)

MODEL_GPT4 = "gpt4"
MODEL_TALKAI = "talkai"
AVAILABLE_MODELS = [MODEL_GPT4, MODEL_TALKAI]

class ChatState(StatesGroup):
    choosing_model = State()
    waiting_for_message = State()

async def create_telegraph_page(title: str, content: str) -> str:
    try:
        escaped_content = html.escape(content)
        response = telegraph.create_page(title=title, html_content=f"<pre>{escaped_content}</pre>")
        return response['url']
    except Exception as e:
        logging.error(f"Error creating Telegraph page: {e}")
        return None

def get_user_context(user_id: int, model: str):
    return gpt4_contexts if model == MODEL_GPT4 else None

async def get_chat_response(user_id: int, message_text: str, model: str, image_path: str = None, image_caption: str = None):
    if model == MODEL_GPT4:
        return await chat_with_gpt(user_id, message_text)
    elif model == MODEL_TALKAI:
        return await chat_with_talkai(message_text, image_path, image_caption)
    return None

async def download_photo(photo: types.PhotoSize) -> str:
    file_path = f"downloads/{photo.file_id}.jpg"
    await bot.download(photo, destination=file_path)
    return file_path

@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="GPT-4o", callback_data=f"select_model_{MODEL_GPT4}")],
        [InlineKeyboardButton(text="TalkAI (обрабатывает изображения)", callback_data=f"select_model_{MODEL_TALKAI}")]
    ])
    await message.answer("Привет! 👋\nВыберите нейросеть для общения:", reply_markup=markup)
    await state.set_state(ChatState.choosing_model)
    logging.info(f"User {message.from_user.id} started the bot.")

@router.callback_query(ChatState.choosing_model)
async def process_model_choice(callback: CallbackQuery, state: FSMContext):
    model = callback.data.split("_")[-1]
    if model in AVAILABLE_MODELS:
        await state.update_data(selected_model=model)
        await callback.message.edit_text(f"Вы выбрали нейросеть: {model}. Теперь можете задавать вопросы.", reply_markup=None)
        await state.set_state(ChatState.waiting_for_message)
        await callback.answer()
        logging.info(f"User {callback.from_user.id} selected model: {model}")
    else:
        await callback.answer("Ошибка: Неизвестная нейросеть.", show_alert=True)

@router.message(StateFilter(ChatState.waiting_for_message))
async def message_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    selected_model = user_data.get("selected_model")
    if not selected_model:
        await message.answer("Пожалуйста, выберите нейросеть с помощью команды /start.")
        return

    image_path = None
    image_caption = None

    if message.photo and selected_model == MODEL_TALKAI:
        image_path = await download_photo(message.photo[-1])
        logging.info(f"Downloaded image to: {image_path}")
        image_caption = message.caption
        logging.info(f"User {message.from_user.id} | Model: {selected_model} | Received image with caption: {image_caption}")
    elif message.photo and selected_model == MODEL_GPT4:
        await message.answer("GPT-4o не умеет работать с картинками. 🖼️")
        return

    if message.text or image_path:
        try:
            response_text = await get_chat_response(message.from_user.id, message.text, selected_model, image_path, image_caption)
            if response_text:
                clear_button = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🗑️ Очистить чат", callback_data="clear_chat"),
                        InlineKeyboardButton(text="🔄 Сменить нейросеть", callback_data="switch_model")
                    ]
                ])
                if len(response_text) > TELEGRAM_MESSAGE_LIMIT:
                    telegraph_url = await create_telegraph_page(title=f"Ответ от бота ({selected_model})", content=response_text)
                    if telegraph_url:
                        await message.answer(f"Ответ в Telegraph: {telegraph_url}", reply_markup=clear_button)
                        logging.info(f"User {message.from_user.id} | Model: {selected_model} | Long Response in Telegraph: {telegraph_url}")
                    else:
                        await message.answer("Не удалось опубликовать ответ в Telegraph. 😔", reply_markup=clear_button)
                        logging.warning(f"User {message.from_user.id} | Model: {selected_model} | Failed to create Telegraph page for long response.")
                else:
                    await message.answer(response_text, reply_markup=clear_button)
                    logging.info(f"User {message.from_user.id} | Model: {selected_model} | Request: {message.text if message.text else 'Image'} | Response: {response_text}")
            else:
                await message.answer("Не удалось получить ответ. 😔")
                logging.warning(f"User {message.from_user.id} | Model: {selected_model} | Failed to get response for: {message.text if message.text else 'Image'}")
        except Exception as e:
            await message.answer("Произошла ошибка. 😥")
            logging.error(f"User {message.from_user.id} | Model: {selected_model} | Error processing message: {e}")
        # Больше не удаляем файл
        # finally:
        #     if image_path and os.path.exists(image_path):
        #         os.remove(image_path)
        #         logging.info(f"Deleted temporary image file: {image_path}")
    elif not message.text and not message.photo:
        await message.answer("Только текст или изображения (для TalkAI). 📝")
        logging.warning(f"User {message.from_user.id} | Model: {selected_model} | Sent non-text/image message.")

@router.callback_query(StateFilter(ChatState.waiting_for_message), lambda c: c.data == "clear_chat")
async def clear_chat_handler(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    selected_model = user_data.get("selected_model")
    if selected_model:
        context = get_user_context(callback.from_user.id, selected_model)
        if context and callback.from_user.id in context:
            del context[callback.from_user.id]
            await bot.send_message(callback.message.chat.id, "Контекст очищен. 🗑️")
            await callback.answer()
            logging.info(f"User {callback.from_user.id} | Model: {selected_model} cleared the chat context.")
        else:
            await callback.answer("Контекст пуст.", show_alert=True)
    else:
        await callback.answer("Выберите нейросеть.", show_alert=True)

@router.callback_query(StateFilter(ChatState.waiting_for_message), lambda c: c.data == "switch_model")
async def switch_model_handler(callback: CallbackQuery, state: FSMContext):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_switch"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_switch")
        ]
    ])
    await callback.message.answer("Сменить нейросеть? История будет удалена.", reply_markup=markup)
    await state.set_state("confirm_switch_model")
    await callback.answer()
    logging.info(f"User {callback.from_user.id} requested to switch model.")

@router.callback_query(StateFilter("confirm_switch_model"), lambda c: c.data == "confirm_switch")
async def confirm_switch_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_data = await state.get_data()
    selected_model = user_data.get("selected_model")

    if selected_model:
        context = get_user_context(user_id, selected_model)
        if context and user_id in context:
            del context[user_id]
            logging.info(f"User {user_id} cleared context for model {selected_model} before switching.")

    await state.set_state(ChatState.choosing_model)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="GPT-4o", callback_data=f"select_model_{MODEL_GPT4}")],
        [InlineKeyboardButton(text="TalkAI (обрабатывает изображения)", callback_data=f"select_model_{MODEL_TALKAI}")]
    ])
    await callback.message.edit_text("Выберите новую нейросеть:", reply_markup=markup)
    await callback.answer()
    logging.info(f"User {callback.from_user.id} confirmed model switch.")

@router.callback_query(StateFilter("confirm_switch_model"), lambda c: c.data == "cancel_switch")
async def cancel_switch_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChatState.waiting_for_message)
    await callback.message.edit_text("Смена отменена.", reply_markup=None)
    await callback.answer()
    logging.info(f"User {callback.from_user.id} cancelled model switch.")

@router.message()
async def all_messages_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info(f"User {message.from_user.id} | Current state: {current_state}")
    if current_state == ChatState.waiting_for_message.state:
        await message.answer("Только текст или изображения (для TalkAI). 📝")
        logging.warning(f"User {message.from_user.id} | Sent unsupported message type in waiting_for_message state.")
    elif current_state != ChatState.choosing_model:
        await message.answer("Не понимаю. 😕")
        logging.warning(f"User {message.from_user.id} | Sent unsupported message type.")

async def main():
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())