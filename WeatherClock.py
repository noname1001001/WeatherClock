# WeatherClock.py
import serial
import os, datetime, time, requests, json, threading
from dotenv import load_dotenv

# Константы
WEATHER_UPDATE_INTERVAL = 3000 
CACHE_FILE_CURRENT = 'weather_current.json'
CACHE_FILE_FORECAST = 'weather_forecast.json'

# Глобальные переменные
weather_text_bytes = b'T???C P???mm H??%'.ljust(20)
weather_conditions_bytes = b''
is_updating = False

def SaveCache(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения кэша {filename}: {e}")

def LoadCache(filename):
    if not os.path.exists(filename): return None
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка чтения кэша {filename}: {e}")
        return None

def WindConvert(angle=None):
    if angle is None: return ''
    try:
        direction = ['северный', 'северо-северо-восточный', 'северо-северо-восточный', 'северо-восточный',
                     'северо-восточный', 'восточно-северо-восточный', 'восточно-северо-восточный', 'восточный',
                     'восточный', 'восточно-юго-восточный', 'восточно-юго-восточный', 'юго-восточный',
                     'юго-восточный', 'юго-юго-восточный', 'юго-юго-восточный', 'южный', 'южный',
                     'юго-юго-западный', 'юго-юго-западный', 'юго-западный', 'юго-западный', 'западно-юго-западный',
                     'западно-юго-западный', 'западный', 'западный', 'западно-северо-западный', 'западно-северо-западный',
                     'северо-западный', 'северо-западный', 'северо-северо-западный', 'северо-северо-западный', 'северный', 'северный']
        return direction[int(angle // 11.25)]
    except: return str(angle) + ' град'

def UTFToASCIIPosUA(string=None):
    if string is None: return b''
    charDict = {'А': b'\x80', 'а': b'\xA0', 'Б': b'\x81', 'б': b'\xA1', 'В': b'\x82', 'в': b'\xA2', 'Г': b'\x83', 'г': b'\xA3',
                'Д': b'\x84', 'д': b'\xA4', 'Е': b'\x85', 'е': b'\xA5', 'Ё': b'\x85', 'ё': b'\xA5', 'Ж': b'\x86', 'ж': b'\xA6',
                'З': b'\x87', 'з': b'\xA7', 'И': b'\x88', 'и': b'\xA8', 'Й': b'\x89', 'й': b'\xA9', 'К': b'\x8A', 'к': b'\xAA',
                'Л': b'\x8B', 'л': b'\xAB', 'М': b'\x8C', 'м': b'\xAC', 'Н': b'\x8D', 'н': b'\xAD', 'О': b'\x8E', 'о': b'\xAE',
                'П': b'\x8F', 'п': b'\xAF', 'Р': b'\x90', 'р': b'\xE0', 'С': b'\x91', 'с': b'\xE1', 'Т': b'\x92', 'т': b'\xE2',
                'У': b'\x93', 'у': b'\xE3', 'Ф': b'\x94', 'ф': b'\xE4', 'Х': b'\x95', 'х': b'\xE5', 'Ц': b'\x96', 'ц': b'\xE6',
                'Ч': b'\x97', 'ч': b'\xE7', 'Ш': b'\x98', 'ш': b'\xE8', 'Щ': b'\x99', 'щ': b'\xE9', 'Ь': b'\x9A', 'ь': b'\xEA',
                'Ы': b'\x9B', 'ы': b'\xEB', 'Ъ': b'\x9C', 'ъ': b'\xEC', 'Э': b'\x9D', 'э': b'\xED', 'Ю': b'\x9E', 'ю': b'\xEE',
                'Я': b'\x9F', 'я': b'\xEF', ' ': b' ', ':': b'\x3A', '/': b'/', '.': b'.', ',': b',', ';': b';', "'": b"'", '"': b'"', '-': b'-'}
    res = []
    for char in string:
        res.append(charDict.get(char, char.encode('ascii', errors='ignore'))[0])
    return bytearray(res)

def FormatWeatherData(weather):
    try:
        temp = weather['main']['temp']
        press = int(weather['main']['pressure'] / 1.33333)
        hum = weather['main']['humidity']
        desc = weather['weather'][0]['description']
        wind = weather['wind']['speed']
        wind_deg = weather['wind'].get('deg', 0)

        # Формируем строку: T +0.0C P760mm H50%
        temp_str = f"{temp:+.1f}"
        line1 = f"T {temp_str}C P{press}mm H{hum}%".encode('ascii').ljust(20)
        line2 = UTFToASCIIPosUA(f"{desc}; ветер {WindConvert(wind_deg)}, {wind} м/с")
        return line1, line2
    except Exception as e:
        print(f"Ошибка форматирования: {e}")
        return b'T???C P???mm H??%'.ljust(20), UTFToASCIIPosUA("Ошибка данных")

def GetWeatherSync():
    load_dotenv()
    api_key = os.getenv('OPENWEATHER_API_KEY')
    proxies = {"http": None, "https": None}
    
    data = None
    try:
        r = requests.get("https://api.openweathermap.org/data/2.5/weather", 
                        params={'q': 'Moscow', 'units': 'metric', 'APPID': api_key, 'lang': 'ru'}, 
                        timeout=10, proxies=proxies)
        if r.status_code == 200:
            data = r.json()
            SaveCache(data, CACHE_FILE_CURRENT)
            print("API: Текущая погода обновлена")
            
            # Запрашиваем только 12 точек (на 36 часов вперед)
            rf = requests.get("https://api.openweathermap.org/data/2.5/forecast", 
                             params={'q': 'Moscow', 'units': 'metric', 'APPID': api_key, 'lang': 'ru', 'cnt': 12}, 
                             timeout=10, proxies=proxies)
            if rf.status_code == 200:
                SaveCache(rf.json(), CACHE_FILE_FORECAST)
                print("API: Прогноз на 36 часов обновлен")
    except Exception as e:
        print(f"Ошибка API: {e}")

    if not data:
        current = LoadCache(CACHE_FILE_CURRENT)
        forecast = LoadCache(CACHE_FILE_FORECAST)
        if current:
            data = current
            print("КЭШ: Использую текущую погоду")
        if forecast and 'list' in forecast:
            now = time.time()
            best = min(forecast['list'], key=lambda x: abs(x['dt'] - now))
            if not data or abs(best['dt'] - now) < 3600:
                data = best
                print(f"КЭШ: Взят прогноз (разница {int(abs(best['dt']-now)/60)} мин)")
    return data

def UpdateWeatherTask():
    global weather_text_bytes, weather_conditions_bytes, is_updating
    if is_updating: return
    is_updating = True
    try:
        data = GetWeatherSync()
        if data:
            weather_text_bytes, weather_conditions_bytes = FormatWeatherData(data)
    finally:
        is_updating = False

if __name__ == '__main__':
    port = serial.Serial("COM1", 9600, timeout=0)
    threading.Thread(target=UpdateWeatherTask, daemon=True).start()
    
    i_weather = 0 # Счетчик для обновления из интернета (5 мин)
    i_scroll = 0  # Счетчик для паузы между прокрутками (20 сек)
    fBegin = 0
    floatingFlag = False
    
    while True:
        # 1. Часы (верхняя строка)
        now = datetime.datetime.now()
        hString = now.strftime("%d.%m.%y  %H:%M:%S.%f")[:20].encode('ascii')
        
        # 2. Логика бегущей строки (нижняя строка)
        if floatingFlag:
            clean_temp = weather_text_bytes.strip()
            scroll_source = clean_temp + b'    ' + weather_conditions_bytes + b'     ' + clean_temp
            rawL = scroll_source[fBegin:20+fBegin]
            
            # Проверка завершения прокрутки
            if fBegin > 10 and rawL.startswith(clean_temp):
                floatingFlag = False
                fBegin = 0
                i_scroll = 0 # Сбрасываем только счетчик паузы!
                lString = clean_temp.ljust(20)
            else:
                lString = rawL.ljust(20)
                fBegin += 1
        else:
            i_scroll += 1
            lString = weather_text_bytes.strip().ljust(20)
            
            # Начинаем прокрутку через 20 секунд
            if i_scroll >= 200:
                if len(weather_conditions_bytes) > 0:
                    floatingFlag = True
                    fBegin = 1
                else:
                    i_scroll = 0

        # 3. Обновление погоды из интернета (каждые 5 минут)
        i_weather += 1
        if i_weather >= WEATHER_UPDATE_INTERVAL:
            i_weather = 0
            threading.Thread(target=UpdateWeatherTask, daemon=True).start()

        try:
            port.write(hString + lString)
        except Exception as e:
            print(f"Ошибка порта: {e}")
            
        time.sleep(0.1)
