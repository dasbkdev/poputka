import os
from dotenv import load_dotenv

load_dotenv()

QR_DIR = os.getenv("QR_DIR", "images")
QR_EXTS = [".png", ".jpg", ".jpeg", ".webp"]

EXAMPLE_RECEIPT_PATH = os.getenv("EXAMPLE_RECEIPT_PATH", "").strip()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

GROUP_IDS = [int(x) for x in os.getenv("GROUP_IDS", "").split(",") if x.strip()]

ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x.strip()]

RECIPIENTS = [x.strip() for x in os.getenv("RECIPIENTS", "").split(",") if x.strip()]

ROTATION = [int(x) for x in os.getenv("ROTATION", "0,0,0,1").split(",") if x.strip()]

MIN_AMOUNT = float(os.getenv("MIN_AMOUNT", "20"))
TIME_WINDOW_MINUTES = int(os.getenv("TIME_WINDOW_MINUTES", "5"))
CHECK_TZ = os.getenv("CHECK_TZ", "Asia/Bishkek")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")
if not GROUP_IDS:
    raise RuntimeError("GROUP_IDS не заданы в .env (через запятую)")
if not RECIPIENTS:
    raise RuntimeError("RECIPIENTS не заданы в .env (через запятую)")
if any(i >= len(RECIPIENTS) or i < 0 for i in ROTATION):
    raise RuntimeError("ROTATION содержит индексы вне диапазона RECIPIENTS")
