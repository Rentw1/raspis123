import os
import requests
from bs4 import BeautifulSoup
import telebot
from telebot import types
import re

TOKEN = os.getenv('TG_TOKEN')
USERNAME = os.getenv('VUZ_USER')
PASSWORD = os.getenv('VUZ_PASS')
BASE_URL = 'https://apeksvuz.mosu-mvd.com'

bot = telebot.TeleBot(TOKEN)

def get_schedule_text():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        # 1. Авторизация
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
        
        # 2. Получение главной страницы
        main_page = session.get(BASE_URL)
        soup_main = BeautifulSoup(main_page.content, 'html.parser')
        
        # Ищем блок с расписанием
        schedule_widget = soup_main.find('div', id='widget-schedule')
        if not schedule_widget:
            return "📅 Расписание не найдено (или нет пар)."

        card_body = schedule_widget.find('div', class_='card-body')
        schedule_data = []
        
        # 3. Парсим строго по тегам HTML
        # Ищем все даты (они лежат в тегах <h4>)
        for h4 in card_body.find_all('h4'):
            date_text = h4.get_text(strip=True)
            schedule_data.append({'type': 'date', 'text': date_text})
            
            # Расписание на день лежит в следующем блоке после <h4>
            timeline_div = h4.find_next_sibling('div', class_='profiletimeline')
            if timeline_div:
                seen_lessons = set() # Сюда будем складывать уникальные пары
                
                # Перебираем все пары за день
                for item in timeline_div.find_all('div', class_='sl-item'):
                    # Достаем название
                    subject_tag = item.find('h5')
                    # Достаем время
                    time_tag = item.find('p', class_='text-muted')
                    # Достаем аудиторию/преподавателя
                    room_tag = item.find('div', class_='gx-9')
                    
                    if subject_tag and time_tag:
                        # Чистим название от переносов и слова "913,"
                        subject = ' '.join(subject_tag.get_text().split())
                        if '913,' in subject:
                            subject = subject.replace('913,', '').strip()
                            
                        # Чистим время (вытаскиваем только формат 00:00 - 00:00)
                        time_full = ' '.join(time_tag.get_text().split())
                        time_match = re.search(r'\d{2}:\d{2}\s*-\s*\d{2}:\d{2}', time_full)
                        lesson_time = time_match.group(0) if time_match else ""
                        
                        # Чистим аудиторию
                        room = ' '.join(room_tag.get_text().split()) if room_tag else ""
                        room = room.strip(',') # Убираем лишние запятые в конце
                        
                        # --- ЛОГИКА УДАЛЕНИЯ ДУБЛИКАТОВ ---
                        # Создаем уникальный ключ: "Время + Название"
                        lesson_key = f"{lesson_time}_{subject}"
                        
                        # Если такой пары в это время еще не было, добавляем!
                        if lesson_key not in seen_lessons:
                            seen_lessons.add(lesson_key)
                            schedule_data.append({
                                'type': 'lesson',
                                'time': lesson_time,
                                'subject': subject,
                                'room': room
                            })

        # 4. Формируем сообщение
        if not schedule_data:
            return "📅 Расписание не найдено."
        
        msg_lines = ["📅 <b>Актуальное расписание</b>", "👤 Васильев Р.А.", ""]
        for item in schedule_data:
            if item['type'] == 'date':
                msg_lines.append(f"\n<b>📆 {item['text']}</b>")
            else:
                msg_lines.append(f"  🕒 <b>{item['time']}</b>")
                msg_lines.append(f"      📖 {item['subject']}")
                if item['room']:
                    msg_lines.append(f"      📍 <i>{item['room']}</i>")
                
        return "\n".join(msg_lines)

    except Exception as e:
        return f"❌ Ошибка при получении данных: {e}"

# --- ТЕЛЕГРАМ БОТ ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📖 Получить расписание")
    markup.add(btn)
    bot.send_message(message.chat.id, "Привет! Нажми на кнопку, чтобы получить расписание.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📖 Получить расписание")
def send_schedule(message):
    bot.send_message(message.chat.id, "⏳ Подключаюсь к Апексу...")
    text = get_schedule_text()
    
    # Режем сообщение, если оно большое
    for i in range(0, len(text), 4000):
        bot.send_message(message.chat.id, text[i:i+4000], parse_mode='HTML')

if __name__ == '__main__':
    print("Бот запущен, ожидаю команд...")
    bot.infinity_polling()
