#!/usr/bin/env python3
"""Отправка текста из .txt файла в Telegram-чат через бота."""

import json
import os
import ssl
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError


def load_env(path: str = ".env") -> None:
    """Загружает переменные из .env файла."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


load_env()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Telegram ограничивает сообщения до 4096 символов
MAX_MESSAGE_LENGTH = 4096


def get_ssl_context() -> ssl.SSLContext:
    """Возвращает SSL-контекст (с fallback без проверки сертификатов)."""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
        return ctx
    except ImportError:
        pass

    # Проверяем, работает ли контекст по умолчанию
    try:
        req = Request(f"{API_URL}/getMe")
        urlopen(req, timeout=5, context=ctx)
        return ctx
    except (URLError, OSError):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def send_message(text: str) -> dict:
    """Отправляет сообщение в Telegram-чат. Возвращает ответ API."""
    url = f"{API_URL}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    ctx = get_ssl_context()

    with urlopen(req, timeout=15, context=ctx) as resp:
        return json.loads(resp.read().decode())


def send_long_message(text: str) -> None:
    """Разбивает длинный текст на части и отправляет по очереди."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        result = send_message(text)
        if result.get("ok"):
            print("Сообщение отправлено.")
        else:
            print(f"Ошибка: {result}")
        return

    # Разбиваем по строкам, чтобы не резать слова
    parts = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > MAX_MESSAGE_LENGTH:
            parts.append(current)
            current = line
        else:
            current += line
    if current:
        parts.append(current)

    print(f"Текст разбит на {len(parts)} частей.")
    for i, part in enumerate(parts, 1):
        result = send_message(part)
        if result.get("ok"):
            print(f"  Часть {i}/{len(parts)} — отправлена.")
        else:
            print(f"  Часть {i}/{len(parts)} — ошибка: {result}")


def read_file(path: str) -> str:
    """Читает текст из файла."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 telegram_sender.py <путь_к_файлу.txt>")
        print("Пример:        python3 telegram_sender.py message.txt")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        text = read_file(file_path)
    except FileNotFoundError:
        print(f"Файл не найден: {file_path}")
        sys.exit(1)

    if not text.strip():
        print("Файл пуст, нечего отправлять.")
        sys.exit(1)

    print(f"Файл: {file_path}")
    print(f"Длина текста: {len(text)} символов")
    print("Отправка в Telegram...")

    try:
        send_long_message(text)
    except (URLError, OSError) as exc:
        print(f"Ошибка отправки: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
