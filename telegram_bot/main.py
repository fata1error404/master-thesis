import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Hello! I'm alive 🚀")

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))