from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import os
import sys

def setup_driver():
    """Настройка драйвера"""
    try:
        service = Service()
        options = Options()
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--headless")  # Добавляем headless режим
        
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Ошибка настройки драйвера: {e}")
        return None

def parse_schedule_from_html(html_content):
    """Парсинг расписания из HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    schedule_data = {
        'days': [],
        'total_lessons': 0,
        'parsed_at': datetime.now().isoformat()
    }

    day_headers = soup.find_all('div', class_=['flex', 'flex-row', 'p-2', 'items-center', 'justify-between'])
    
    for header in day_headers:
        day_name_element = header.find('p', class_=['text-xl', 'font-medium'])
        date_element = header.find('p', class_=['text-zinc-500', 'dark:text-zinc-400'])
        
        if day_name_element and date_element:
            day_name = day_name_element.get_text(strip=True)
            date = date_element.get_text(strip=True)
            
            day_data = {
                'day_name': day_name,
                'date': date,
                'lessons': []
            }
            
            next_element = header.find_next_sibling()
            while next_element and (not next_element.has_attr('class') or 
                                  'flex-row' not in next_element.get('class', []) or 
                                  'p-2' not in next_element.get('class', []) or
                                  'justify-between' not in next_element.get('class', [])):
                
                if next_element.name == 'button' and 'grid-cols-5' in next_element.get('class', []):
                    lesson_data = parse_lesson_button(next_element)
                    if lesson_data:
                        day_data['lessons'].append(lesson_data)
                
                next_element = next_element.find_next_sibling()
            
            schedule_data['days'].append(day_data)
            schedule_data['total_lessons'] += len(day_data['lessons'])
    
    return schedule_data

def parse_lesson_button(button_element):
    """Парсинг информации о занятии"""
    try:
        columns = button_element.find_all('div', class_=lambda x: x and 'col-span' in x)
        
        if len(columns) < 3:
            return None
        
        time_col = columns[0]
        time_elements = time_col.find_all('div')
        start_time = time_elements[0].get_text(strip=True) if len(time_elements) > 0 else ''
        end_time = time_elements[1].get_text(strip=True) if len(time_elements) > 1 else ''
        
        subject_col = columns[1]
        subject_elements = subject_col.find_all('div')
        subject = subject_elements[0].get_text(strip=True) if len(subject_elements) > 0 else ''
        teacher = subject_elements[1].get_text(strip=True) if len(subject_elements) > 1 else ''
        
        room_col = columns[2]
        room_elements = room_col.find_all('div')
        room = room_elements[0].get_text(strip=True) if len(room_elements) > 0 else ''

        type_element = room_col.find('div', class_=lambda x: x and 'rounded-sm' in x and 'px-1' in x and 'text-sm' in x)
        lesson_type = type_element.get_text(strip=True) if type_element else ''
        
        return {
            'subject': subject,
            'teacher': teacher,
            'room': room,
            'type': lesson_type,
            'time_range': f"{start_time}-{end_time}"
        }
    
    except Exception as e:
        print(f"Ошибка парсинга занятия: {e}")
        return None

def merge_duplicate_days(schedule_data):
    """Удаляет дублирующиеся дни из расписания"""
    if 'days' not in schedule_data:
        return schedule_data
    
    day_dict = {}
    
    for day in schedule_data['days']:
        day_key = f"{day['day_name']}_{day['date']}"
        
        if day_key not in day_dict:
            day_dict[day_key] = day.copy()
        else:
            existing_day = day_dict[day_key]
            for lesson in day['lessons']:
                lesson_exists = any(
                    existing_lesson['time_range'] == lesson['time_range'] and 
                    existing_lesson['subject'] == lesson['subject'] and
                    existing_lesson['teacher'] == lesson['teacher']
                    for existing_lesson in existing_day['lessons']
                )
                
                if not lesson_exists:
                    existing_day['lessons'].append(lesson)
    
    schedule_data['days'] = list(day_dict.values())
    
    # Пересчитываем общее количество занятий
    schedule_data['total_lessons'] = sum(len(day['lessons']) for day in schedule_data['days'])
    schedule_data['merged_at'] = datetime.now().isoformat()
    
    print(f"Удалены дубликаты. Осталось дней: {len(schedule_data['days'])}, занятий: {schedule_data['total_lessons']}")
    
    return schedule_data

def save_schedule_json(schedule_data, filename="schedule_201_2.json"):
    """Сохранение расписания в JSON"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, ensure_ascii=False, indent=2)
        print(f"Сохранено: {filename}")
        return True
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        return False

def get_schedule_advanced():
    """Основная функция получения расписания"""
    print("=== ЗАПУСК ПАРСЕРА РАСПИСАНИЯ ===")
    driver = setup_driver()
    
    if not driver:
        print("ОШИБКА: Не удалось запустить браузер")
        return False
    
    try:
        print("[1/10] Открываем сайт расписания...")
        driver.get("https://timetable.of.by/")
        time.sleep(5)
        
        print("[2/10] Нажимаем кнопку 'Открыть расписание'...")
        open_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//p[contains(text(), 'Открыть расписание')]]"))
        )
        open_btn.click()
        time.sleep(3)
        
        print("[3/10] Выбираем факультет...")
        faculty_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "faculty"))
        )
        faculty_btn.click()
        time.sleep(2)
        
        pf_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'ПФ')]"))
        )
        pf_option.click()
        time.sleep(2)

        print("[4/10] Выбираем очную форму обучения...")
        offline_radio = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "offline"))
        )
        
        if offline_radio.get_attribute("data-state") != "checked":
            offline_radio.click()
            time.sleep(2)
        
        print("[5/10] Вводим номер группы...")
        group_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Введите номер']"))
        )
        group_input.clear()
        group_input.send_keys("201/2")
        time.sleep(3)
        
        group_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), '201/2')]"))
        )
        group_option.click()
        time.sleep(2)
        
        print("[6/10] Нажимаем 'Продолжить'...")
        continue_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Продолжить') and not(@disabled)]"))
        )
        continue_btn.click()
        
        print("[7/10] Ожидаем загрузки расписания...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'flex-col')]//button[contains(@class, 'grid-cols-5')]"))
        )
        time.sleep(5)
        
        # Сохраняем расписание текущей недели
        print("[8/10] Сохранение расписания текущей недели...")
        html_content = driver.page_source
        schedule_data_current = parse_schedule_from_html(html_content)
        
        # Очищаем от дубликатов текущую неделю
        schedule_data_current = merge_duplicate_days(schedule_data_current)
        
        # Переключаемся на следующую неделю
        print("[9/10] Переключение на следующую неделю...")
        try:
            next_week_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//p[contains(text(), 'След. нед.')]]"))
            )
            next_week_btn.click()
            time.sleep(5)
            
            # Ждем загрузки расписания следующей недели
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'flex-col')]//button[contains(@class, 'grid-cols-5')]"))
            )
            time.sleep(5)
            
            print("[10/10] Сохранение расписания следующей недели...")
            html_content_next_week = driver.page_source
            schedule_data_next_week = parse_schedule_from_html(html_content_next_week)
            
            # Очищаем от дубликатов следующую неделю
            schedule_data_next_week = merge_duplicate_days(schedule_data_next_week)
            
        except Exception as e:
            print(f"ОШИБКА: Не удалось переключиться на следующую неделю: {e}")
            # Если не удалось переключиться, создаем пустую следующую неделю
            schedule_data_next_week = {
                'days': [],
                'total_lessons': 0,
                'parsed_at': datetime.now().isoformat(),
                'merged_at': datetime.now().isoformat()
            }
        
        # Создаем объединенный файл
        combined_schedule = {
            'current_week': schedule_data_current,
            'next_week': schedule_data_next_week,
            'combined_at': datetime.now().isoformat()
        }
        
        # Сохраняем результат
        success = save_schedule_json(combined_schedule, "schedule_201_2.json")
        
        if success:
            print("=== УСПЕХ ===")
            print(f"Текущая неделя: {schedule_data_current['total_lessons']} занятий")
            print(f"Следующая неделя: {schedule_data_next_week['total_lessons']} занятий")
            print("Расписание успешно обновлено!")
            return True
        else:
            print("ОШИБКА: Не удалось сохранить расписание")
            return False
        
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        return False
    
    finally:
        driver.quit()
        print("Браузер закрыт")

if __name__ == "__main__":
    success = get_schedule_advanced()
    sys.exit(0 if success else 1)