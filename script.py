import os
import requests
from bs4 import BeautifulSoup
import telebot
from telebot import types
import re
import schedule
import time
import threading

TOKEN = os.getenv('TG_TOKEN')
USERNAME = os.getenv('VUZ_USER')
PASSWORD = os.getenv('VUZ_PASS')
# ID вашего чата (куда бот будет писать сам в 6 утра)
CHAT_ID = os.getenv('CHAT_ID') 
BASE_URL = 'https://apeksvuz.mosu-mvd.com'

bot = telebot.TeleBot(TOKEN)

def get_schedule_text():
    """Ваша рабочая функция парсинга (оставляем без изменений)"""
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
        
        schedule_widget = soup_main.find('div', id='widget-schedule')
        if not schedule_widget:
            return "📅 Расписание не найдено."

        card_body = schedule_widget.find('div', class_='card-body')
        schedule_data = []
        
        for h4 in card_body.find_all('h4'):
            date_text = h4.get_text(strip=True)
            schedule_data.append({'type': 'date', 'text': date_text})
            timeline_div = h4.find_next_sibling('div', class_='profiletimeline')
            if timeline_div:
                seen_lessons = set()
                for item in timeline_div.find_all('div', class_='sl-item'):
                    subject_tag = item.find('h5')
                    time_tag = item.find('p', class_='text-muted')
                    room_tag = item.find('div', class_='gx-9')
                    
                    if subject_tag and time_tag:
                        subject = ' '.join(subject_tag.get_text().split()).replace('913,', '').strip()
                        time_full = ' '.join(time_tag.get_text().split())
                        time_match = re.search(r'\d{2}:\d{2}\s*-\s*\d{2}:\d{2}', time_full)
                        lesson_time = time_match.group(0) if time_match else ""
                        room = ' '.join(room_tag.get_text().split()) if room_tag else ""
                        
                        lesson_key = f"{lesson_time}_{subject}"
                        if lesson_key not in seen_lessons:
                            seen_lessons.add(lesson_key)
                            schedule_data.append({'type': 'lesson', 'time': lesson_time, 'subject': subject, 'room': room.strip(',')})

        if not schedule_data: return "📅 Расписание не найдено."
        
        msg_lines = ["📅 <b>Доброе утро! Расписание:</b>", "👤 Васильев Р.А.", ""]
        for item in schedule_data:
            if item['type'] == 'date':
                msg_lines.append(f"\n<b>📆 {item['text']}</b>")
            else:
                msg_lines.append(f"  🕒 <b>{item['time']}</b>\n      📖 {item['subject']}")
                if item['room']: msg_lines.append(f"      📍 <i>{item['room']}</i>")
        return "\n".join(msg_lines)
    except Exception as e:
        return f"❌ Ошибка: {e}"

# --- ФУНКЦИИ РАССЫЛКИ ---

def send_morning_schedule():
    """Функция, которую вызовет будильник в 6 утра"""
    print("Выполняю утреннюю рассылку...")
    text = get_schedule_text()
    if CHAT_ID:
        bot.send_message(CHAT_ID, text, parse_mode='HTML')
    else:
        print("Ошибка: Не указан CHAT_ID в переменных Railway!")

def run_scheduler():
    """Фоновый цикл для проверки времени"""
    # Настраиваем время (Railway обычно работает по UTC, проверьте часовой пояс!)
    # Если в Москве 6:00, а сервер в UTC, ставим 03:00
    schedule.every().day.at("03:00").do(send_morning_schedule)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- ОБРАБОТКА КОМАНД ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📖 Получить расписание")
    markup.add(btn)
    bot.send_message(message.chat.id, f"Привет! Я буду присылать расписание каждый день в 6:00. Твой Chat ID: {message.chat.id}\n(Убедись, что добавил его в настройки Railway)", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📖 Получить расписание")
def send_button_schedule(message):
    text = get_schedule_text()
    bot.send_message(message.chat.id, text, parse_mode='HTML')

if __name__ == '__main__':
    # Запускаем планировщик в отдельном потоке
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    print("Бот запущен с будильником на 06:00...")
    bot.infinity_polling()
