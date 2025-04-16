import os
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils import executor
from aiogram.types import Message
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv
import mimetypes

# Загрузка токена
TOKEN = "7744907120:AAFMlbTr48G3HpRWt-fIxh_ku6mxz87HjP8"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

class ConvertStates(StatesGroup):
    waiting_for_format = State()
    waiting_for_bitrate = State()
    waiting_for_resolution = State()
    waiting_for_codec = State()

user_data = {}

AUDIO_FORMATS = ["mp3", "wav", "flac", "aac"]
VIDEO_FORMATS = ["mp4", "avi", "mkv", "mov"]
BITRATES = ["128k", "256k", "512k", "1M", "2M"]
RESOLUTIONS = ["640x360", "1280x720", "1920x1080"]
CODECS = ["libx264", "libx265", "libvpx-vp9"]

@dp.message_handler(Command("start"))
async def start_command(message: Message):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📲 Открыть мини-приложение", web_app=WebAppInfo(url="https://yourdomain.com/app"))
    )
    await message.answer(
        "👋 Привет! Я могу конвертировать медиа 🎵, видео 🎥 и документы 📄.\n\nПросто отправь файл или используй меню ниже:",
        reply_markup=kb
    )

@dp.message_handler(Command("help"))
async def help_command(message: Message):
    await message.answer("\U0001F4D6 Команды:\n/start — начать работу\n/help — помощь\n/info — информация о загруженном файле")

@dp.message_handler(Command("info"))
async def info_command(message: Message):
    user_id = message.from_user.id
    if user_id not in user_data or "file_path" not in user_data[user_id]:
        await message.answer("Сначала отправьте медиафайл.")
        return
    file_path = user_data[user_id]["file_path"]
    if not os.path.exists(file_path):
        await message.answer("Файл не найден. Пожалуйста, отправьте его снова.")
        return
    size = os.path.getsize(file_path)
    await message.answer(f"\U0001F4C4 Информация о файле:\nИмя: {os.path.basename(file_path)}\nРазмер: {round(size / 1024, 2)} КБ")

@dp.message_handler(lambda m: m.web_app_data)
async def handle_webapp_data(message: types.Message):
    uid = message.from_user.id
    choice = message.web_app_data.data

    if uid not in user_data:
        await message.answer("Сначала отправьте файл для конвертации.")
        return

    if choice == "pdf_to_word":
        input_path = user_data[uid]["file_path"]
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}.docx"
        from pdf2docx import Converter
        cv = Converter(input_path)
        cv.convert(output_path, start=0, end=None)
        cv.close()
        with open(output_path, "rb") as f:
            await message.answer_document(types.InputFile(f))
        os.remove(output_path)
        os.remove(input_path)
        return

    elif choice == "word_to_pdf":
        input_path = user_data[uid]["file_path"]
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}.pdf"
        from docx2pdf import convert
        convert(input_path, output_path)
        with open(output_path, "rb") as f:
            await message.answer_document(types.InputFile(f))
        os.remove(output_path)
        os.remove(input_path)
        return

    user_data[uid]["format"] = choice
    await message.answer(f"Выбран формат: {choice.upper()}")
    if choice in AUDIO_FORMATS:
        kb = InlineKeyboardMarkup(row_width=2)
        for br in BITRATES:
            kb.insert(InlineKeyboardButton(br, callback_data=f"bitrate_{br}"))
        await message.answer("Выберите битрейт:", reply_markup=kb)
        await ConvertStates.waiting_for_bitrate.set()
    elif choice in VIDEO_FORMATS:
        kb = InlineKeyboardMarkup(row_width=2)
        for br in BITRATES:
            kb.insert(InlineKeyboardButton(br, callback_data=f"bitrate_{br}"))
        await message.answer("Выберите битрейт:", reply_markup=kb)
        await ConvertStates.waiting_for_bitrate.set()

@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def handle_document(message: Message, state: FSMContext):
    doc = message.document
    file_name = doc.file_name
    file_path = f"downloads/{file_name}"

    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    await message.document.download(destination_file=file_path)

    user_data[message.from_user.id] = {
        "file_path": file_path
    }

    await message.answer("Файл получен. Теперь выберите формат через кнопку /start или /help")

@dp.message_handler(content_types=types.ContentType.AUDIO)
async def handle_audio(message: Message, state: FSMContext):
    audio = message.audio
    file_name = audio.file_name or f"{audio.file_id}.mp3"
    file_path = f"downloads/{file_name}"

    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    await audio.download(destination_file=file_path)

    user_data[message.from_user.id] = {
        "file_path": file_path,
        "is_video": False
    }

    await message.answer("Файл получен. Теперь выберите формат через кнопку /start или /help")

@dp.callback_query_handler(lambda c: c.data.startswith("bitrate_"), state=ConvertStates.waiting_for_bitrate)
async def choose_bitrate(callback_query: types.CallbackQuery, state: FSMContext):
    bitrate = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]["bitrate"] = bitrate

    if user_data[uid].get("is_video"):
        kb = InlineKeyboardMarkup(row_width=2)
        for res in RESOLUTIONS:
            kb.insert(InlineKeyboardButton(res, callback_data=f"res_{res}"))
        await bot.send_message(uid, "Выберите разрешение:", reply_markup=kb)
        await ConvertStates.waiting_for_resolution.set()
    else:
        await start_conversion(callback_query.message, uid, state)

@dp.callback_query_handler(lambda c: c.data.startswith("res_"), state=ConvertStates.waiting_for_resolution)
async def choose_resolution(callback_query: types.CallbackQuery, state: FSMContext):
    resolution = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]["resolution"] = resolution

    kb = InlineKeyboardMarkup(row_width=2)
    for codec in CODECS:
        kb.insert(InlineKeyboardButton(codec, callback_data=f"codec_{codec}"))

    await bot.send_message(uid, "Выберите кодек:", reply_markup=kb)
    await ConvertStates.waiting_for_codec.set()

@dp.callback_query_handler(lambda c: c.data.startswith("codec_"), state=ConvertStates.waiting_for_codec)
async def choose_codec(callback_query: types.CallbackQuery, state: FSMContext):
    codec = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]["codec"] = codec

    await start_conversion(callback_query.message, uid, state)

async def start_conversion(message: Message, uid: int, state: FSMContext):
    await message.answer("⏳ Начинаем конвертацию...")

    data = user_data[uid]
    input_path = data["file_path"]
    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_converted.{data['format']}"

    cmd = ["ffmpeg", "-i", input_path, "-b:a", data["bitrate"]]

    if data.get("is_video"):
        cmd += ["-s", data["resolution"], "-c:v", data["codec"]]

    cmd.append(output_path)

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open(output_path, "rb") as f:
            await message.answer_document(types.InputFile(f))
        os.remove(output_path)
    except subprocess.CalledProcessError as e:
        await message.answer("❌ Ошибка: ffmpeg error")
        print("FFMPEG error:", e)

    os.remove(input_path)
    await state.finish()
    await message.answer("✅ Готово! Отправь новый файл или введи /start для начала заново.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
