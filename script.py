import os
import requests
from bs4 import BeautifulSoup
import telebot
from telebot import types
import re # Добавили библиотеку для поиска времени

TOKEN = os.getenv('TG_TOKEN')
USERNAME = os.getenv('VUZ_USER')
PASSWORD = os.getenv('VUZ_PASS')
BASE_URL = 'https://apeksvuz.mosu-mvd.com'

bot = telebot.TeleBot(TOKEN)

def get_schedule_text():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        # Авторизация
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
        
        # Получаем главную страницу
        main_page = session.get(BASE_URL)
        soup_main = BeautifulSoup(main_page.content, 'html.parser')
        
        # Извлекаем текст, разделяя блоки переносом строки, чтобы слова не слипались
        text = soup_main.get_text(separator='\n')
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        schedule_data = []
        in_schedule = False
        
        # Шаблон для поиска времени (например: 08:30 - 10:00 или 08:30–10:00)
        time_pattern = re.compile(r'\d{2}:\d{2}\s*(?:-|–)\s*\d{2}:\d{2}')
        
        current_date = None
        lessons_today = []
        seen_lessons_today = set() # Уникальные пары ТОЛЬКО для одного дня
        current_lesson = {}
        
        for line in lines:
            if 'Мое расписание' in line:
                in_schedule = True
                continue
            if in_schedule and 'Настройка виджетов' in line:
                break
                
            if in_schedule:
                # 1. Ищем дату (новый день)
                if any(y in line for y in ['.2025,', '.2026,']):
                    # Сохраняем пары предыдущего дня, если они были
                    if current_date and lessons_today:
                        schedule_data.append({'type': 'date', 'text': current_date})
                        schedule_data.extend(lessons_today)
                    
                    current_date = line
                    lessons_today = []
                    seen_lessons_today.clear()
                    current_lesson = {}
                    continue
                
                # 2. Ищем время пары
                time_match = time_pattern.search(line)
                if time_match:
                    current_lesson = {'time': time_match.group(0), 'details': []}
                    continue
                
                # 3. Собираем всё, что относится к текущей паре (предмет, преподаватель, аудитория)
                if current_lesson and 'time' in current_lesson:
                    current_lesson['details'].append(line)
                    
                    # 4. Если наткнулись на номер вашей группы — пара собрана!
                    if '913' in line:
                        # Убираем строку с номером группы, оставляем только предмет и аудиторию
                        details_clean = [l for l in current_lesson['details'] if '913' not in l]
                        
                        # Склеиваем всё в одну красивую строку
                        lesson_text = " | ".join(details_clean)
                        time_str = current_lesson['time']
                        
                        # Ключ уникальности = Время + Название предмета
                        dedup_key = f"{time_str} {lesson_text}"
                        
                        if dedup_key not in seen_lessons_today:
                            seen_lessons_today.add(dedup_key)
                            lessons_today.append({
                                'type': 'lesson', 
                                'time': time_str,
                                'text': lesson_text
                            })
                        
                        # Сбрасываем текущую пару, чтобы начать искать следующую
                        current_lesson = {}

        # Не забываем добавить последний найденный день
        if current_date and lessons_today:
            schedule_data.append({'type': 'date', 'text': current_date})
            schedule_data.extend(lessons_today)
        
        # --- Формируем красивое сообщение ---
        if not schedule_data:
            return "📅 Расписание не найдено."
        
        msg_lines = ["📅 <b>Актуальное расписание</b>", "👤 Васильев Р.А.", ""]
        for item in schedule_data:
            if item['type'] == 'date':
                msg_lines.append(f"\n<b>📆 {item['text']}</b>")
            else:
                msg_lines.append(f"  🕒 <b>{item['time']}</b>\n      {item['text']}")
                
        return "\n".join(msg_lines)
        
    except Exception as e:
        return f"❌ Ошибка при получении данных: {e}"

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📖 Получить расписание")
    markup.add(btn)
    bot.send_message(message.chat.id, "Привет! Нажми на кнопку, чтобы получить расписание с аудиториями и временем.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📖 Получить расписание")
def send_schedule(message):
    bot.send_message(message.chat.id, "⏳ Секунду, собираю расписание (с временем и аудиториями)...")
    text = get_schedule_text()
    
    # Режем сообщение, если оно вдруг превысит лимит Telegram
    for i in range(0, len(text), 4000):
        bot.send_message(message.chat.id, text[i:i+4000], parse_mode='HTML')

if __name__ == '__main__':
    print("Бот запущен, ожидаю команд...")
    bot.infinity_polling()
