import asyncio
import logging
import os
import zipfile
import xml.etree.ElementTree as ET
import io
import tempfile
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.telegram import TelegramAPIServer

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from docx import Document
import pillow_heif
import exifread

# Загружаем переменные из .env
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CF_WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL") 

if not TOKEN:
    logging.critical("❌ TELEGRAM_BOT_TOKEN не найден! Проверь переменные окружения.")
    exit(1)

if not CF_WORKER_URL:
    logging.warning("⚠️ CLOUDFLARE_WORKER_URL не найден в .env! Убедись, что переменная задана.")

# Настраиваем логирование
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

# Магия обхода блокировки РКН
custom_server = TelegramAPIServer.from_base(CF_WORKER_URL) if CF_WORKER_URL else None
bot = Bot(token=TOKEN, server=custom_server)
dp = Dispatcher()

# -----------------------------
# Вспомогательные функции EXIF
# -----------------------------
def safe_decode_bytes(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception as e:
            logging.debug(f"Ошибка декодирования байт: {e}")
            return str(value)[:100] + "…"
    return str(value) # Приводим к строке для безопасности HTML

def dms_to_float(value):
    if isinstance(value, tuple):
        if isinstance(value[0], tuple):
            d = value[0][0] / value[0][1]
            m = value[1][0] / value[1][1]
            s = value[2][0] / value[2][1]
        else:
            d, m, s = value
        return d + m/60 + s/3600
    return float(value)

def extract_gps(exif):
    gps_info = exif.get("GPSInfo")
    if not gps_info:
        return None
    gps_data = {}
    for t in gps_info:
        sub_tag = GPSTAGS.get(t, t)
        gps_data[sub_tag] = gps_info[t]
    try:
        lat = dms_to_float(gps_data["GPSLatitude"])
        if gps_data.get("GPSLatitudeRef") == "S":
            lat = -lat
        lon = dms_to_float(gps_data["GPSLongitude"])
        if gps_data.get("GPSLongitudeRef") == "W":
            lon = -lon
        return (lat, lon)
    except Exception as e:
        logging.error(f"Ошибка конвертации GPS: {e}")
        return None

def extract_exif_standard(file_bytes):
    try:
        image = Image.open(io.BytesIO(file_bytes))
        raw_exif = image._getexif()
        if not raw_exif:
            return "❌ EXIF-данные не найдены", None
        exif = {TAGS.get(tag, tag): safe_decode_bytes(val) for tag, val in raw_exif.items()}
        gps_coords = extract_gps(exif)
        lines = [f"<b>{k}</b>: {v}" for k, v in exif.items() if v]
        return "\n".join(lines)[:4000], gps_coords
    except Exception as e:
        logging.error(f"Ошибка при чтении стандартного EXIF: {e}")
        return f"❌ Ошибка при чтении EXIF: {e}", None

def extract_exif_dng(file_bytes):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dng") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        with open(tmp_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

        if not tags:
            return "❌ EXIF-данные не найдены в DNG", None

        lines = []
        for tag in ['Image Make', 'Image Model', 'EXIF ExposureTime', 'EXIF FNumber', 'EXIF ISOSpeedRatings', 'EXIF FocalLength', 'EXIF DateTimeOriginal']:
            if tag in tags:
                lines.append(f"<b>{tag}</b>: {tags[tag]}")

        return "\n".join(lines), None
    except Exception as e:
        logging.error(f"Ошибка парсинга DNG: {e}")
        return f"❌ Ошибка DNG: {e}", None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

def extract_exif_heic(file_bytes):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".heic") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        heif_file = pillow_heif.read_heif(tmp_path)
        image = heif_file.to_pillow()
        lines = [
            f"<b>Width</b>: {image.width}",
            f"<b>Height</b>: {image.height}",
            f"<b>Mode</b>: {image.mode}",
            f"<b>Format</b>: HEIC/HEIF"
        ]
        return "\n".join(lines), None
    except Exception as e:
        logging.error(f"Ошибка парсинга HEIC: {e}")
        return f"❌ Ошибка HEIC: {e}", None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

def extract_exif_auto(file_bytes, filename):
    ext = filename.lower()
    if ext.endswith((".heic", ".heif")):
        return extract_exif_heic(file_bytes)
    elif ext.endswith(".dng"):
        return extract_exif_dng(file_bytes)
    else:
        return extract_exif_standard(file_bytes)

# -----------------------------
# DOCX Метаданные
# -----------------------------
def extract_docx_metadata(file_bytes):
    try:
        doc_file = io.BytesIO(file_bytes)
        doc = Document(doc_file)
        props = doc.core_properties
        
        lines = ["📋 <b>Основные свойства:</b>"]
        core_props = {
            "Автор": props.author,
            "Последний редактор": props.last_modified_by,
            "Создан": props.created,
            "Изменён": props.modified,
            "Название": props.title,
            "Описание": props.subject,
            "Ключевые слова": props.keywords,
        }
        for k, v in core_props.items():
            if v: lines.append(f"<b>{k}</b>: {v}")

        doc_file.seek(0)
        with zipfile.ZipFile(doc_file) as zf:
            if "docProps/app.xml" in zf.namelist():
                lines.append("\n⚙️ <b>Свойства приложения:</b>")
                with zf.open("docProps/app.xml") as f:
                    for child in ET.parse(f).getroot():
                        if child.text and child.text.strip():
                            lines.append(f"<b>{child.tag.split('}')[-1]}</b>: {child.text}")
            
            if "word/comments.xml" in zf.namelist():
                lines.append("\n💬 <b>Комментарии в документе:</b>")
                with zf.open("word/comments.xml") as f:
                    for c in ET.parse(f).getroot().findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}comment"):
                        author = c.attrib.get("author", "Неизвестно")
                        date = c.attrib.get("date", "")
                        text = "".join([t.text or "" for t in c.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")])
                        lines.append(f"👤 {author} ({date}): {text}")

        return "\n".join(lines)[:4000]
    except Exception as e:
        logging.error(f"Ошибка парсинга DOCX: {e}")
        return f"❌ Ошибка парсинга DOCX: {e}"

# -----------------------------
# Обработчики сообщений
# -----------------------------
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "📸 <b>Привет! Пришли фото (как файл) или файл DOCX — я извлеку метаданные.</b>\n\n"
        "‼️ <b>Важно:</b> Telegram сжимает фотографии и полностью удаляет из них EXIF. "
        "Чтобы увидеть метаданные кадра, отправляй фото только как <b>Файл/Документ (без сжатия)</b>.\n\n"
        "Поддерживаемые форматы: <code>jpeg, png, heic, heif, dng, docx</code>",
        parse_mode="HTML"
    )

@dp.message(lambda m: m.photo)
async def handle_photo_compressed(message: types.Message):
    await message.answer(
        "⚠️ Вы отправили сжатое фото! Telegram стёр все метаданные. Перешлите его как <b>Файл/Документ</b>.",
        parse_mode="HTML"
    )

@dp.message(lambda m: m.document)
async def handle_document(message: types.Message):
    status_msg = await message.answer("📥 Скачиваю и анализирую файл, подождите...")
    
    try:
        file_id = message.document.file_id
        filename = message.document.file_name
        
        # Скачиваем файл в память
        file_obj = await bot.get_file(file_id)
        file_bytes_io = io.BytesIO()
        await bot.download_file(file_obj.file_path, file_bytes_io)
        file_bytes = file_bytes_io.getvalue()

        # Обработка DOCX
        if filename.lower().endswith(".docx"):
            result_text = await asyncio.to_thread(extract_docx_metadata, file_bytes)
            await status_msg.edit_text(result_text, parse_mode="HTML")
            
        # Обработка изображений
        elif filename.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".heif", ".dng")):
            exif_text, gps = await asyncio.to_thread(extract_exif_auto, file_bytes, filename)
            await status_msg.edit_text(exif_text, parse_mode="HTML")
            
            if gps:
                await message.answer_location(latitude=gps[0], longitude=gps[1])
        else:
            await status_msg.edit_text("❌ Неподдерживаемый формат файла.")
            
    except Exception as e:
        logging.error(f"Критическая ошибка обработчика документа: {e}")
        await status_msg.edit_text(f"❌ Произошла ошибка при обработке файла.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())