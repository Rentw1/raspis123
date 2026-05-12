import os
import requests
from bs4 import BeautifulSoup
import telebot
from telebot import types

# Данные из переменных Railway
TOKEN = os.getenv('TG_TOKEN')
USERNAME = os.getenv('VUZ_USER')
PASSWORD = os.getenv('VUZ_PASS')
BASE_URL = 'https://apeksvuz.mosu-mvd.com'

bot = telebot.TeleBot(TOKEN)

def get_schedule_text():
    """Логика парсинга расписания (та же, что была раньше)"""
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        login_page = session.get(BASE_URL + '/login')
        soup = BeautifulSoup(login_page.content, 'html.parser')
        csrf_token = soup.find('input', {'name': '_csrf'}).get('value', '')
        
        login_data = {
            '_csrf': csrf_token,
            'LoginForm[username]': USERNAME,
            'LoginForm[password]': PASSWORD,
            'LoginForm[rememberMe]': '1'
        }
        session.post(BASE_URL + '/login', data=login_data)
        
        main_page = session.get(BASE_URL)
        soup_main = BeautifulSoup(main_page.content, 'html.parser')
        
        lines = soup_main.get_text().split('\n')
        schedule_data = []
        in_schedule = False
        for line in lines:
            line = line.strip()
            if 'Мое расписание' in line: in_schedule = True
            if in_schedule and 'Настройка виджетов' in line: break
            if in_schedule and line:
                if any(y in line for y in ['.2025,', '.2026,']):
                    schedule_data.append(f"\n<b>📆 {line}</b>")
                elif '913,' in line:
                    subj = ' '.join(line.replace('913, ', '').split())
                    schedule_data.append(f"  • {subj}")
        
        if not schedule_data:
            return "📅 Расписание не найдено."
        
        header = "📅 <b>Актуальное расписание</b>\n👤 Васильев Р.А.\n"
        return header + "\n".join(schedule_data)
    except Exception as e:
        return f"❌ Ошибка при получении данных: {e}"

# Команда /start — создает кнопку
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📖 Получить расписание")
    markup.add(btn)
    bot.send_message(message.chat.id, "Привет! Нажми на кнопку ниже, чтобы я прислал расписание.", reply_markup=markup)

# Обработка нажатия на кнопку
@bot.message_handler(func=lambda message: message.text == "📖 Получить расписание")
def send_schedule(message):
    bot.send_message(message.chat.id, "⏳ Секунду, подключаюсь к Апексу...")
    text = get_schedule_text()
    bot.send_message(message.chat.id, text, parse_mode='HTML')

if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
