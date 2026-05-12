import os
import requests
from bs4 import BeautifulSoup
import time
import schedule  # Добавьте эту библиотеку

# Данные из переменных окружения Railway
BASE_URL = 'https://apeksvuz.mosu-mvd.com'
USERNAME = os.getenv('VUZ_USER')
PASSWORD = os.getenv('VUZ_PASS')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
CHAT_ID = os.getenv('TG_CHAT_ID')

def send_telegram(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    try:
        for i in range(0, len(text), 4000):
            requests.post(url, data={
                'chat_id': CHAT_ID,
                'text': text[i:i+4000],
                'parse_mode': 'HTML'
            })
            time.sleep(0.5)
    except Exception as e:
        print(f"Ошибка отправки в ТГ: {e}")

def get_and_send_schedule():
    print("Запуск задачи получения расписания...")
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
        
        # Парсинг
        main_page = session.get(BASE_URL)
        soup_main = BeautifulSoup(main_page.content, 'html.parser')
        
        schedule_data = []
        seen_lessons = set()
        lines = soup_main.get_text().split('\n')
        in_schedule = False
        
        for line in lines:
            line = line.strip()
            if 'Мое расписание' in line: in_schedule = True
            if in_schedule and 'Настройка виджетов' in line: break
            if in_schedule and line:
                if any(y in line for y in ['.2025,', '.2026,']):
                    schedule_data.append({'type': 'date', 'text': line})
                    seen_lessons.clear()
                elif '913,' in line:
                    subj = ' '.join(line.replace('913, ', '').split())
                    if subj[:60] not in seen_lessons:
                        seen_lessons.add(subj[:60])
                        schedule_data.append({'type': 'lesson', 'text': subj})
        
        # Формирование сообщения
        if not schedule_data:
            send_telegram("📅 Расписание на сегодня не найдено.")
            return

        msg = "📅 <b>Расписание</b>\n👤 Васильев Р.А.\n"
        for item in schedule_data:
            if item['type'] == 'date':
                msg += f"\n<b>📆 {item['text']}</b>\n"
            else:
                msg += f"  • {item['text']}\n"
        
        send_telegram(msg)
        print("Сообщение успешно отправлено.")
        
    except Exception as e:
        send_telegram(f"❌ Ошибка в скрипте: {e}")

# Планировщик: запуск каждый день в 07:00
schedule.every().day.at("07:00").do(get_and_send_schedule)

if __name__ == '__main__':
    print("Бот запущен и ожидает времени отправки...")
    # Первый запуск при старте (опционально, чтобы проверить работу сразу)
    # get_and_send_schedule() 
    
    while True:
        schedule.run_pending()
        time.sleep(60)
