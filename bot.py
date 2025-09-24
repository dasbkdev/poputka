import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, GROUP_ID
from database import init_db, save_ad

logging.basicConfig(level=logging.DEBUG)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher(storage=MemoryStorage())

init_db()

class Form(StatesGroup):
    name = State()
    phone = State()
    description = State()
    proof = State()


@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Саламатсызбы! Жарыя чыгаруу үчүн аты-жөнүңүздү жазыңыз:")
    await state.set_state(Form.name)


@dp.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📞 Телефон номериңизди жазыңыз:")
    await state.set_state(Form.phone)


@dp.message(Form.phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("✍️ Жарыяңызды жазыңыз (мисалы: Нарындан Бишкекке 3 киши алам):")
    await state.set_state(Form.description)

@dp.message(Form.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)

    photo = FSInputFile("images/qr_code.jpg")
    caption = (
        "💳 Реквизит Mbank: 996553155787\n\n"
        "Төлөгөнүңүздү тастыктаган чек/скриншот жибериңиз (20 сом):"
    )

    await message.answer_photo(photo=photo, caption=caption)
    await state.set_state(Form.proof)

@dp.message(Form.proof, F.photo | F.document)
async def process_proof(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    data = await state.get_data()

    save_ad(data["name"], data["phone"], data["description"], file_id)

    ad_text = (
        f"👤 {data['name']}\n"
        f"📞 {data['phone']}\n\n"
        f"{data['description']}\n\n"
        f"🔥 Өзүңүздүн жарыяңызды чыгаруу үчүн басыңыз 👉 @poputkakgz_bot"
    )

    await bot.send_message(GROUP_ID, ad_text)
    await message.answer("✅ Рахмат! Сиздин жарыяныз чыгарылды. Текшерүү үчүн басыңыз 👉 t.me/NarynBihek")
    await state.clear()


if __name__ == "__main__":
    async def main():
        print("🚀 Бот запущен жана Telegram'дан жаңылыктарды угууда...")
        await dp.start_polling(bot)

    asyncio.run(main())
