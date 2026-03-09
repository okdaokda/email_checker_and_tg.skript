#!/usr/bin/env python3
"""Проверка email-адресов: MX-записи + SMTP handshake."""

import json
import smtplib
import socket
import ssl
import sys
import re
from urllib.request import Request, urlopen
from urllib.error import URLError

TIMEOUT = 10
HELO_DOMAIN = "example.com"
SENDER = f"check@{HELO_DOMAIN}"


def is_valid_format(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def get_mx_hosts(domain: str) -> list[str]:
    """Получает MX-записи через DNS over HTTPS (Google)."""
    url = f"https://dns.google/resolve?name={domain}&type=MX"
    req = Request(url, headers={"Accept": "application/json"})

    # Пробуем сначала с проверкой сертификатов, затем без
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass

    try:
        with urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError):
        # Если SSL не прошёл — повтор без проверки сертификатов
        try:
            ctx_noverify = ssl.create_default_context()
            ctx_noverify.check_hostname = False
            ctx_noverify.verify_mode = ssl.CERT_NONE
            with urlopen(req, timeout=10, context=ctx_noverify) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            raise ValueError("MX-записи отсутствуют или некорректны")

    # Status 3 = NXDOMAIN
    if data.get("Status") == 3:
        raise ValueError("домен отсутствует")
    if data.get("Status") != 0:
        raise ValueError("MX-записи отсутствуют или некорректны")

    answers = data.get("Answer", [])
    mx_records = []
    for ans in answers:
        if ans.get("type") == 15:  # MX
            # Формат данных: "10 mx.google.com."
            parts = ans.get("data", "").split()
            if len(parts) == 2 and parts[0].isdigit():
                priority = int(parts[0])
                host = parts[1].rstrip(".")
                mx_records.append((priority, host))

    if not mx_records:
        raise ValueError("MX-записи отсутствуют или некорректны")

    mx_records.sort(key=lambda r: r[0])
    return [host for _, host in mx_records]


def smtp_check(email: str, mx_hosts: list[str]) -> str:
    """SMTP handshake: HELO -> MAIL FROM -> RCPT TO. Возвращает статус."""
    last_error = None
    for mx in mx_hosts:
        try:
            with smtplib.SMTP(mx, 25, timeout=TIMEOUT) as smtp:
                smtp.helo(HELO_DOMAIN)
                smtp.mail(SENDER)
                code, _ = smtp.rcpt(email)
                if code == 250:
                    return "пользователь существует (код 250)"
                elif code == 550:
                    return "пользователь не найден (код 550)"
                else:
                    return f"неопределённый ответ (код {code})"
        except (smtplib.SMTPException, socket.error, OSError) as exc:
            last_error = exc
            continue

    return f"не удалось подключиться к SMTP ({last_error})"


def check_email(email: str) -> dict:
    result = {"email": email, "mx": None, "smtp": None}

    if not is_valid_format(email):
        result["mx"] = "некорректный формат email"
        return result

    domain = email.split("@", 1)[1]

    try:
        mx_hosts = get_mx_hosts(domain)
    except ValueError as exc:
        result["mx"] = str(exc)
        return result

    result["mx"] = "домен валиден"
    result["smtp"] = smtp_check(email, mx_hosts)
    return result


def main():
    if len(sys.argv) > 1:
        emails = sys.argv[1:]
    else:
        print("Введите email-адреса (по одному на строку, пустая строка — конец):")
        emails = []
        for line in sys.stdin:
            line = line.strip()
            if not line:
                break
            emails.append(line)

    if not emails:
        print("Список email пуст.")
        return

    for email in emails:
        r = check_email(email)
        print(f"\n{'='*50}")
        print(f"  Email : {r['email']}")
        print(f"  MX    : {r['mx']}")
        if r["smtp"]:
            print(f"  SMTP  : {r['smtp']}")


if __name__ == "__main__":
    main()
