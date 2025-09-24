import logging
import asyncio
import os
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, FSInputFile, InputMediaPhoto

from config import (
    BOT_TOKEN, GROUP_IDS, ADMINS, RECIPIENTS, ROTATION,
    MIN_AMOUNT, TIME_WINDOW_MINUTES, CHECK_TZ, QR_DIR, QR_EXTS, EXAMPLE_RECEIPT_PATH 
)
from database import (
    init_db, save_ad, save_payment, get_and_inc_rotation_index
)
from ocr_utils import (
    ocr_text_from_any, extract_amount, extract_datetime, extract_phone
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
init_db()

class Form(StatesGroup):
    name = State()
    phone = State()
    description = State()
    proof = State()

# ---- validators ----
def valid_name(s: str) -> bool:
    return bool(s and len(s.strip()) >= 2)

def normalize_phone(s: str) -> str | None:
    if not s:
        return None
    txt = s.strip().replace(' ', '').replace('-', '')
    if txt.startswith('+996') and len(txt) == 13 and txt[1:].isdigit():
        return txt[1:]
    if txt.startswith('0') and len(txt) == 10 and txt.isdigit():
        return '996' + txt[1:]
    if txt.startswith('996') and len(txt) == 12 and txt.isdigit():
        return txt
    return None

def valid_description(s: str) -> bool:
    return bool(s and len(s.strip()) >= 10)

def choose_recipient_index() -> int:
    mod = len(ROTATION)
    idx_in_rotation = get_and_inc_rotation_index(mod)
    return ROTATION[idx_in_rotation]

# ---- helpers ----
async def download_file_from_message(msg: Message) -> str | None:
    file_id, filename = None, None
    if msg.photo:
        file_id = msg.photo[-1].file_id
        filename = f"{file_id}.jpg"
    elif msg.document:
        file_id = msg.document.file_id
        filename = msg.document.file_name or f"{file_id}"
    else:
        return None
    file = await bot.get_file(file_id)
    tmp = tempfile.NamedTemporaryFile(prefix="receipt_", delete=False,
                                      suffix=os.path.splitext(filename)[1] if filename else ".jpg")
    await bot.download_file(file.file_path, tmp.name)
    tmp.close()
    return tmp.name

# ---- handlers ----
@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🚕Саламатсызбы! Жарыя чыгаруу үчүн аты-жөнүңүздү жазыңыз:")
    await state.set_state(Form.name)

@dp.message(Form.name, F.text)
async def ask_phone(message: Message, state: FSMContext):
    name = message.text.strip()
    if not valid_name(name):
        await message.answer("Атыңызды туура жазыңыз (кеминде 2 символ).")
        return
    await state.update_data(name=name)
    await message.answer("📞 Телефон номери (+996XXXXXXXXX же 0XXXXXXXXX):")
    await state.set_state(Form.phone)

@dp.message(Form.phone, F.text)
async def ask_description(message: Message, state: FSMContext):
    phone = normalize_phone(message.text.strip())
    if not phone:
        await message.answer("Телефон форматы туура эмес. Мисалы: +996703523713 же 0703523713.")
        return
    await state.update_data(phone=phone)
    await message.answer("✍️ Жарыяңызды жазыңыз (кеминде 10 символ):")
    await state.set_state(Form.description)

@dp.message(Form.description, F.text)
async def ask_payment(message: Message, state: FSMContext):
    desc = message.text.strip()
    if not valid_description(desc):
        await message.answer("Жарыя өтө кыска. Кеминде 10 символ жазыңыз.")
        return

    rec_idx = choose_recipient_index()
    recipient = RECIPIENTS[rec_idx]

    await state.update_data(
        description=desc,
        requested_at=datetime.now(ZoneInfo(CHECK_TZ)).isoformat(),
        recipient=recipient
    )

    # Основной текст
    caption_qr = (
        f"💳 Реквизит: {recipient}\n"
        f"🧾 Акысы: {int(MIN_AMOUNT)} сом\n\n"
        f"Төлөгөнүңүздү тастыктаган чек/скриншот (же PDF) жибериңиз."
    )

    # Подсказка к образцу правильного чека (кыргызча, максимально просто)
    caption_example = (
        "✅ Туура чек үлгүсү:\n"
        " • Дал ушул алуучу\n"
        f" • Сумма ≥ {int(MIN_AMOUNT)} сом\n"
        f" • Убакыт ±{TIME_WINDOW_MINUTES} мүн. ичинде\n"
        "Сүрөт так жана толук болсун."
    )

    qr_path = find_qr_image_for_recipient(recipient)
    example_path = EXAMPLE_RECEIPT_PATH if EXAMPLE_RECEIPT_PATH and Path(EXAMPLE_RECEIPT_PATH).exists() else None

    # Если есть и QR, и пример — шлём альбомом; если нет — fallback
    media = []
    if qr_path:
        media.append(InputMediaPhoto(media=FSInputFile(qr_path), caption=caption_qr))
    if example_path:
        # подпись у второго вложения (Telegram показывает только первую подпись в альбоме),
        # поэтому добавим пояснение в ответ отдельным сообщением, или сделаем наоборот:
        # подпись у QR, а к примеру отправим отдельным сообщением ниже.
        media.append(InputMediaPhoto(media=FSInputFile(example_path)))

    if len(media) >= 2:
        # Отправляем альбом + отдельным сообщением пояснение к примеру
        await message.answer_media_group(media=media)
        await message.answer(caption_example)
    elif qr_path:
        # Только QR
        await message.answer_photo(photo=FSInputFile(qr_path), caption=caption_qr)
        if example_path:
            await message.answer_photo(photo=FSInputFile(example_path), caption=caption_example)
    elif example_path:
        # Нет QR — хотя бы пример
        await message.answer_photo(photo=FSInputFile(example_path), caption=f"{caption_qr}\n\n{caption_example}")
    else:
        # Совсем без изображений
        await message.answer(caption_qr + "\n\n" + caption_example)

    await state.set_state(Form.proof)


def find_qr_image_for_recipient(recipient: str) -> str | None:
    base = Path(QR_DIR)
    if not base.exists():
        return None
    for ext in QR_EXTS:
        p = base / f"{recipient}{ext}"
        if p.exists():
            return str(p)
    return None

@dp.message(Form.proof, F.photo | F.document)
async def process_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("name")
    phone = data.get("phone")
    desc = data.get("description")
    recipient_sent = data.get("recipient")
    requested_at_iso = data.get("requested_at")

    # --- скачиваем файл ---
    local_path = await download_file_from_message(message)
    if not local_path:
        await message.answer("Сүрөт же файл тапшырыңыз, сураныч.")
        return

    # --- OCR ---
    try:
        text = ocr_text_from_any(local_path)
    except Exception:
        await message.answer("Кечиресиз, чек окула алган жок. Так/таза сүрөт же PDF жибериңиз.")
        return

    # --- Парсинг ---
    amount = extract_amount(text)
    dt_check = extract_datetime(text)
    phone_on_check = extract_phone(text)

    logging.info("OCR TEXT (first 600 chars): %s", text[:600])
    logging.info("PARSED amount=%s", amount)
    logging.info("PARSED dt_check=%s", dt_check)
    logging.info("PARSED phone_on_check=%s", phone_on_check)

    # --- сумма ---
    if amount is None or amount < MIN_AMOUNT:
        await message.answer(f"Төлөм {int(MIN_AMOUNT)} сомдон кем болбоого тийиш.")
        return

    # --- получатель ---
    matched = False
    for r in RECIPIENTS:
        if r in text:
            matched = True
            break
    if not matched and phone_on_check:
        for r in RECIPIENTS:
            if phone_on_check.endswith(r[-9:]):
                matched = True
                break
    if not matched:
        await message.answer("Чектеги кабыл алуучу биздин реквизиттерге дал келбейт.")
        return

    # --- окно времени ---
    if requested_at_iso and dt_check:
        tz = ZoneInfo(CHECK_TZ)

        requested_at = datetime.fromisoformat(requested_at_iso)
        if requested_at.tzinfo is None:
            requested_at = requested_at.replace(tzinfo=tz)

        msg_time_local = message.date.astimezone(tz)
        dt_check_local = dt_check if dt_check.tzinfo else dt_check.replace(tzinfo=tz)

        def trim_min(dt): return dt.replace(second=0, microsecond=0)
        requested_at = trim_min(requested_at)
        msg_time_local = trim_min(msg_time_local)
        dt_check_local = trim_min(dt_check_local)

        delta1 = abs((requested_at - dt_check_local).total_seconds()) / 60.0
        delta2 = abs((msg_time_local - dt_check_local).total_seconds()) / 60.0

        logging.info(
            "TIME DEBUG: requested_at=%s, msg_time_local=%s, dt_check_local=%s, d1=%.1f, d2=%.1f",
            requested_at, msg_time_local, dt_check_local, delta1, delta2
        )

        if (delta1 > TIME_WINDOW_MINUTES) and (delta2 > TIME_WINDOW_MINUTES):
            await message.answer(f"Чектеги убакыт уруксат берилген терезеге түшпөйт (±{TIME_WINDOW_MINUTES} мүн.).")
            return
    else:
        await message.answer("Чектеги дата/убакыт аныкталган жок. Так сүрөт/PDF жибериңиз.")
        return

    # --- сохраняем и публикуем ---
    save_payment(
        message.from_user.id,
        amount=amount,
        recipient=recipient_sent,
        check_time=dt_check.isoformat(),
        proof_path=local_path
    )
    save_ad(
        message.from_user.id,
        name=name,
        phone=phone,
        description=desc,
        proof_path=local_path
    )

    me = await bot.get_me()
    ad_text = (
        f"👤 {name}\n"
        f"📞 +{phone}\n\n"
        f"{desc}\n\n"
        f"🔥 Өзүңүздүн жарыяңызды чыгаруу үчүн басыңыз 👉 @{me.username}"
    )

    sent_ok = 0
    for gid in GROUP_IDS:
        try:
            await bot.send_message(gid, ad_text)
            sent_ok += 1
        except Exception as e:
            logging.exception("Жарыя жиберүүдө ката (group %s): %s", gid, e)

    await message.answer(
        "✅ Төлөм текшерилди жана жарыя чыгарылды." if sent_ok
        else "✅ Төлөм текшерилди. (Эскертүү: каналга жиберүүдө ката кетти)"
    )
    await state.clear()


if __name__ == "__main__":
    async def main():
        logging.info("🚀 Бот запущен.")
        await dp.start_polling(bot)
    asyncio.run(main())
