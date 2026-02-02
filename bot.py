import asyncio
import logging
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io
from dotenv import load_dotenv  # <-- для .env

# --- Загружаем .env ---
load_dotenv()  # ищет файл .env в текущей папке
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN не найден в .env")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Вспомогательные функции ---
def safe_decode_bytes(value):
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8")
            return json.dumps(json.loads(text), ensure_ascii=False, indent=0)
        except:
            return str(value)[:100] + "…"
    return value

def get_decimal_from_dms(dms, ref):
    degrees = dms[0][0] / dms[0][1]
    minutes = dms[1][0] / dms[1][1]
    seconds = dms[2][0] / dms[2][1]
    dec = degrees + minutes/60 + seconds/3600
    if ref in ['S', 'W']:
        dec = -dec
    return dec

def extract_gps(exif):
    gps_info = exif.get("GPSInfo")
    if not gps_info:
        return None
    gps_data = {}
    for t in gps_info:
        sub_tag = GPSTAGS.get(t, t)
        gps_data[sub_tag] = gps_info[t]
    try:
        lat = get_decimal_from_dms(gps_data["GPSLatitude"], gps_data["GPSLatitudeRef"])
        lon = get_decimal_from_dms(gps_data["GPSLongitude"], gps_data["GPSLongitudeRef"])
        return (lat, lon)
    except:
        return None

def extract_exif(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        raw_exif = image._getexif()
        if not raw_exif:
            return "❌ EXIF-данные не найдены", None

        exif = {}
        for tag_id, value in raw_exif.items():
            tag = TAGS.get(tag_id, tag_id)
            value = safe_decode_bytes(value)
            exif[tag] = value

        gps_coords = extract_gps(exif)
        result_lines = []
        for k, v in exif.items():
            if isinstance(v, str) and len(v) > 200:
                v = v[:200] + "…"
            result_lines.append(f"{k}: {v}")
        return "\n".join(result_lines), gps_coords

    except Exception as e:
        return f"❌ Ошибка при чтении EXIF: {e}", None

# --- Обработчики ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Пришли фото или файл изображения — извлеку EXIF-метаданные")

@dp.message(lambda m: m.photo)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    exif_text, gps_coords = extract_exif(file_bytes.read())
    reply = f"📋 Метаданные:\n\n{exif_text}"
    if gps_coords:
        lat, lon = gps_coords
        reply += f"\n\n📍 GPS: https://www.google.com/maps?q={lat},{lon}"
    await message.answer(reply)

@dp.message(lambda m: m.document)
async def handle_document(message: types.Message):
    if not (message.document.mime_type.startswith("image/") or
            message.document.file_name.lower().endswith(('.png','.jpg','.jpeg','.heic'))):
        await message.answer("❌ Это не изображение")
        return

    file = await bot.get_file(message.document.file_id)
    file_bytes = await bot.download_file(file.file_path)
    exif_text, gps_coords = extract_exif(file_bytes.read())
    reply = f"📋 Метаданные:\n\n{exif_text}"
    if gps_coords:
        lat, lon = gps_coords
        reply += f"\n\n📍 GPS: https://www.google.com/maps?q={lat},{lon}"
    await message.answer(reply)

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())