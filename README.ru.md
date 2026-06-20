# Metadata Extractor Bot

[English](https://github.com/KirillxC/metadata-bot/blob/main/README.md) | [Русский](https://github.com/KirillxC/metadata-bot/blob/main/README.ru.md)

Telegram-бот для извлечения EXIF-данных и метаданных документов.
Попробуйте в действии: [EXIF_export_bot](https://t.me/EXIF_export_bot)

## Возможности
- **Извлечение EXIF:** Поддерживает форматы JPEG, PNG, HEIC/HEIF и DNG.
- **Анализ DOCX:** Открывает DOCX-файлы как ZIP-архивы для извлечения сырых данных из `docProps/app.xml` и комментариев, содержащих скрытые метаданные.
- **Конфиденциальность:** Обрабатывает файлы в оперативной памяти, исключая сохранение на сервере.

## Поддержка прокси
Если вам необходимо обойти ограничения подключения, разверните этот прокси:
[cf-workers_proxy4bot](https://github.com/KirillxC/cf-workers_proxy4bot/)

## Установка
1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/KirillxC/metadata-bot.git
   cd metadata-bot
   nano .env
   # Добавьте ваш TELEGRAM_BOT_TOKEN и CLOUDFLARE_WORKER_URL
   docker compose up -d --build
