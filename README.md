# Metadata Extractor Bot

A Telegram bot for extracting EXIF and document metadata.
Try it live: [EXIF_export_bot](https://t.me/EXIF_export_bot)

## Features
- **EXIF Extraction:** Supports JPEG, PNG, HEIC/HEIF, and DNG formats.
- **DOCX Analysis:** Opens DOCX files as ZIP archives to parse raw `docProps/app.xml` and comments for hidden metadata.
- **Privacy:** Processes files in memory to avoid storage on the server.

## Proxy Support
If you need to bypass connectivity restrictions, deploy this proxy:
[cf-workers_proxy4bot](https://github.com/KirillxC/cf-workers_proxy4bot/)

## Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/KirillxC/metadata-bot.git
   cd metadata-bot
   nano .env
   # Add your TELEGRAM_BOT_TOKEN and CLOUDFLARE_WORKER_URL
   docker compose up -d --build
