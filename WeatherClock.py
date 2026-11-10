# WeatherClock.py
import serial
import os, sys, datetime, time, requests, json, threading
from pathlib import Path

# Константы
SCRIPT_DIR = Path(__file__).parent.absolute()
WEATHER_UPDATE_INTERVAL = 300     # секунд — штатный интервал обновления
WEATHER_RETRY_BASE = 60           # секунд — первая пауза после неудачи (далее удваивается)
WEATHER_MAX_INTERVAL = 1800       # секунд — потолок паузы при повторяющихся неудачах
CONNECT_TIMEOUT = 5               # секунд — на установку соединения
READ_TIMEOUT = 10                 # секунд — на чтение ответа
TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)
CACHE_STALE_AFTER = 3 * 3600      # данные старше этого возраста помечаются на табло как устаревшие
CACHE_EXPIRED_AFTER = 24 * 3600   # старше этого возраста кэш уже не показывается
FORECAST_WINDOW = 3 * 3600        # секунд — насколько прогноз может отстоять от текущего времени
CACHE_FILE_CURRENT = SCRIPT_DIR / 'weather_current.json'
CACHE_FILE_FORECAST = SCRIPT_DIR / 'weather_forecast.json'

LOC_LAT, LOC_LON = 55.7558, 37.6173
LOC_NAME = 'Moscow'
SIMPLE_UA = 'WeatherClock/1.0'
BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Порядок = приоритет источников. Первый успешно ответивший задаёт данные для табло.
SOURCES = ['openweathermap', 'open-meteo', 'met.no']

# Глобальные переменные
weather_text_bytes = b'T???C P???mm H??%'.ljust(20)
weather_conditions_bytes = b''

def Log(msg):
    print(f"[{datetime.datetime.now()}] {msg}", flush=True)

def LoadEnv(path=None):
    Мини-парсер .env.
    path = path or (SCRIPT_DIR / '.env')
    res = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                res[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    except Exception as e:
        Log(f"Ошибка чтения {path}: {e}")
    return res

ENV = LoadEnv()

def Env(name, default=None):
    #Сначала переменные окружения, затем .env рядом со скриптом.
    return os.environ.get(name, ENV.get(name, default))

# Порядок источников можно задать и без правки кода: WEATHER_SOURCES=open-meteo,met.no
_env_sources = Env('WEATHER_SOURCES')
if _env_sources:
    SOURCES = [s.strip() for s in _env_sources.split(',') if s.strip()]

def BuildSession(user_agent):
    """Session с User-Agent и настройкой прокси.

    По умолчанию используются системные/переменные прокси (requests trust_env).
    WEATHER_PROXY=http://127.0.0.1:10808 — явный прокси.
    WEATHER_NO_PROXY=1 — ходить строго напрямую (старое поведение).
    """
    session = requests.Session()
    session.headers.update({'User-Agent': user_agent, 'Accept': 'application/json'})
    proxy = Env('WEATHER_PROXY')
    if proxy:
        session.proxies = {'http': proxy, 'https': proxy}
    elif str(Env('WEATHER_NO_PROXY', '0')).lower() in ('1', 'true', 'yes'):
        session.proxies = {'http': None, 'https': None}
    return session

def GetJSON(session, url, params=None):
    #GET с проверкой статуса. Возвращает (json, None) либо (None, описание_ошибки).
    try:
        r = session.get(url, params=params, timeout=TIMEOUT)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:140]}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code} {r.reason}: {r.text[:120].strip()}"
    try:
        return r.json(), None
    except Exception as e:
        return None, f"некорректный JSON: {e}"

def SaveCache(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({'fetched_at': time.time(), 'data': data}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        Log(f"Ошибка сохранения кэша {filename}: {e}")

def LoadCache(filename):
    """Возвращает (data, возраст_в_секундах) либо (None, None).

    Поддерживает и старый формат файла (без поля fetched_at): тогда возраст берётся
    по времени модификации файла.
    """
    if not os.path.exists(filename):
        return None, None
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception as e:
        Log(f"Ошибка чтения кэша {filename}: {e}")
        return None, None
    if isinstance(raw, dict) and 'fetched_at' in raw and 'data' in raw:
        return raw['data'], max(0, time.time() - float(raw['fetched_at']))
    try:
        return raw, max(0, time.time() - os.path.getmtime(filename))
    except Exception:
        return raw, None

def FormatAge(seconds):
    if seconds is None:
        return 'неизвестно'
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds} сек"
    if seconds < 5400:
        return f"{seconds // 60} мин"
    if seconds < 172800:
        return f"{seconds // 3600} ч"
    return f"{seconds // 86400} сут"

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
        temp = float(weather['main']['temp'])
        press = int(float(weather['main']['pressure']) / 1.33333)
        hum = float(weather['main']['humidity'])
        desc = weather['weather'][0]['description']
        wind = float(weather['wind']['speed'])
        wind_deg = weather['wind'].get('deg')

        line1 = f"T {temp:+.1f}C P{press}mm H{hum:.0f}%".encode('ascii', errors='replace').ljust(20)
        line2 = UTFToASCIIPosUA(f"{desc}; ветер {WindConvert(wind_deg)}, {wind:.1f} м/с")
        return line1, line2
    except Exception as e:
        Log(f"Ошибка форматирования: {e}")
        return b'T???C P???mm H??%'.ljust(20), UTFToASCIIPosUA("Ошибка данных")

def MakeWeather(temp, pressure_hpa, humidity, description, wind_ms, wind_deg):
    return {
        'main': {'temp': temp, 'pressure': pressure_hpa, 'humidity': humidity},
        'weather': [{'description': description}],
        'wind': {'speed': wind_ms, 'deg': wind_deg}
    }

def FetchOpenWeatherMap():
    api_key = Env('OPENWEATHER_API_KEY')
    if not api_key:
        return None, None, ["openweathermap: в .env нет OPENWEATHER_API_KEY"]
    session = BuildSession(SIMPLE_UA)
    params = {'q': LOC_NAME, 'units': 'metric', 'lang': 'ru', 'APPID': api_key}

    curr, err = GetJSON(session, "https://api.openweathermap.org/data/2.5/weather", params)
    if err:
        return None, None, [f"openweathermap: {err}"]

    forecast = None
    problems = []
    fc, err = GetJSON(session, "https://api.openweathermap.org/data/2.5/forecast", dict(params, cnt=48))
    if err:
        problems.append(f"openweathermap (прогноз): {err}")
    elif isinstance(fc, dict) and fc.get('list'):
        forecast = fc['list']
    return curr, forecast, problems

WMO_CODES = {
    0: "Ясно", 1: "Преимущ. ясно", 2: "Переменная облачность", 3: "Пасмурно",
    45: "Туман", 48: "Иней", 51: "Морось", 53: "Умеренная морось", 55: "Плотная морось",
    61: "Небольшой дождь", 63: "Умеренный дождь", 65: "Сильный дождь",
    71: "Небольшой снег", 73: "Умеренный снег", 75: "Сильный снег",
    77: "Снежная крупа", 80: "Ливень", 81: "Сильный ливень", 82: "Оч. сильный ливень",
    85: "Снегопад", 86: "Сильный снегопад", 95: "Гроза", 96: "Гроза, град", 99: "Гроза, сильный град"
}

def FetchOpenMeteo():
    session = BuildSession(SIMPLE_UA)
    common = {'latitude': LOC_LAT, 'longitude': LOC_LON, 'timezone': 'Europe/Moscow'}

    raw, err = GetJSON(session, "https://api.open-meteo.com/v1/forecast",
                       dict(common, current='temperature_2m,relative_humidity_2m,weather_code,'
                                             'pressure_msl,wind_speed_10m,wind_direction_10m'))
    if err:
        return None, None, [f"open-meteo: {err}"]
    curr = raw.get('current') or {}
    data = MakeWeather(curr.get('temperature_2m'), curr.get('pressure_msl'), curr.get('relative_humidity_2m'),
                       WMO_CODES.get(curr.get('weather_code'), "Погода"),
                       round(curr['wind_speed_10m'] / 3.6, 1) if curr.get('wind_speed_10m') is not None else None,
                       curr.get('wind_direction_10m'))

    forecast, problems = None, []
    raw_f, err = GetJSON(session, "https://api.open-meteo.com/v1/forecast",
                         dict(common, hourly='temperature_2m,relative_humidity_2m,weather_code,'
                                              'pressure_msl,wind_speed_10m,wind_direction_10m', forecast_days=2))
    if err:
        problems.append(f"open-meteo (прогноз): {err}")
    else:
        hours = (raw_f or {}).get('hourly') or {}
        times = hours.get('time') or []
        forecast = []
        for i, t in enumerate(times):
            try:
                forecast.append({'dt': datetime.datetime.fromisoformat(t).timestamp(),
                                 **MakeWeather(hours['temperature_2m'][i], hours['pressure_msl'][i],
                                               hours['relative_humidity_2m'][i],
                                               WMO_CODES.get(hours['weather_code'][i], "Погода"),
                                               round(hours['wind_speed_10m'][i] / 3.6, 1),
                                               hours['wind_direction_10m'][i])})
            except Exception as e:
                problems.append(f"open-meteo (прогноз, строка {i}): {e}")
                break
    return data, forecast or None, problems

METNO_SYMBOLS = sorted([
    ('clearsky', 'Ясно'), ('fair', 'Преимущ. ясно'), ('partlycloudy', 'Переменная облачность'),
    ('cloudy', 'Пасмурно'), ('fog', 'Туман'), ('sleet', 'Мокрый снег'), ('snow', 'Снег'),
    ('rain', 'Дождь'), ('drizzle', 'Морось'), ('thunder', 'Гроза'), ('thunderlight', 'Гроза с ливнем'),
    ('sun', 'Ясно'), ('polartwilight', 'Сумерки'),
], key=lambda x: -len(x[0]))

def MetNoDescription(symbol_code):
    if not symbol_code:
        return 'Погода'
    code = symbol_code
    for suffix in ('_polartwilight', '_day', '_night'):
        if code.endswith(suffix):
            code = code[:-len(suffix)]
            break
    for prefix, name in METNO_SYMBOLS:
        if code.startswith(prefix):
            return name
    return code.replace('_', ' ')

def FetchMetNo():
    session = BuildSession(BROWSER_UA)
    raw, err = GetJSON(session, "https://api.met.no/weatherapi/locationforecast/2.0/compact",
                       {'lat': LOC_LAT, 'lon': LOC_LON})
    if err:
        return None, None, [f"met.no: {err}"]

    series = (raw.get('properties') or {}).get('timeseries') or raw.get('timeseries') or []
    if not series:
        return None, None, ["met.no: пустой timeseries"]

    def Details(entry):
        node = (entry or {}).get('data') or {}
        instant = node.get('instant') or {}
        next6 = node.get('next_6_hours') or {}
        det, ndet = instant.get('details') or {}, next6.get('details') or {}
        return MakeWeather(
            det.get('air_temperature'),
            det.get('air_pressure_at_sea_level') or ndet.get('air_pressure_at_sea_level'),
            det.get('relative_humidity') or ndet.get('relative_humidity'),
            MetNoDescription(next6.get('summary', {}).get('symbol_code') or instant.get('symbol_code')),
            det.get('wind_speed'), det.get('wind_from_direction') or det.get('wind_direction'))

    def Stamp(entry):
        try:
            return datetime.datetime.fromisoformat(entry['time'].replace('Z', '+00:00')).timestamp()
        except Exception:
            return None

    now = time.time()
    best, best_diff = None, None
    for entry in series:
        stamp = Stamp(entry)
        if stamp is None:
            continue
        diff = abs(stamp - now)
        if best_diff is None or diff < best_diff:
            best, best_diff = Details(entry), diff

    forecast = []
    for entry in series:
        stamp = Stamp(entry)
        if stamp is None:
            continue
        forecast.append({'dt': stamp, **Details(entry)})
    return best, (forecast or None), []

FETCHERS = {
    'openweathermap': FetchOpenWeatherMap,
    'open-meteo': FetchOpenMeteo,
    'met.no': FetchMetNo,
}

def FetchFromSources():
    #Опрос источников по приоритету. Возвращает (есть_текущая_погода, список_проблем).
    problems = []
    for name in SOURCES:
        fetcher = FETCHERS.get(name)
        if not fetcher:
            problems.append(f"{name}: неизвестный источник")
            continue
        try:
            curr, forecast, errs = fetcher()
        except Exception as e:
            curr, forecast, errs = None, None, [f"{name}: {type(e).__name__}: {str(e)[:140]}"]
        for msg in errs or []:
            problems.append(msg)
        if curr:
            SaveCache(curr, CACHE_FILE_CURRENT)
            Log(f"API [{name}]: текущая погода обновлена")
        if forecast:
            SaveCache({'list': forecast}, CACHE_FILE_FORECAST)
            Log(f"API [{name}]: прогноз обновлен ({len(forecast)} значений)")
        if curr or forecast:
            return bool(curr), problems
    return False, problems

def PickCachedData():
    #Выбор данных из кэша. Возвращает (data, возраст, подпись) либо (None, None, причина).
    current, current_age = LoadCache(CACHE_FILE_CURRENT)
    forecast, forecast_age = LoadCache(CACHE_FILE_FORECAST)
    now = time.time()

    from_forecast = None
    if isinstance(forecast, dict) and forecast.get('list'):
        near = [x for x in forecast['list'] if abs(x.get('dt', 0) - now) < FORECAST_WINDOW]
        if near:
            best = min(near, key=lambda x: abs(x['dt'] - now))
            from_forecast = (best, forecast_age,
                             f"прогноз (разница {int(abs(best['dt'] - now) / 60)} мин)")

    from_current = None
    if isinstance(current, dict) and 'main' in current:
        from_current = (current, current_age, "текущая погода")

    # Текущая погода предпочтительнее; прогноз берём только если он заметно свежее
    if from_current and from_forecast:
        ca, fa = from_current[1], from_forecast[1]
        data, age, note = from_forecast if (fa is not None and (ca is None or ca - fa > 3600)) else from_current
    else:
        data, age, note = from_current or from_forecast
    if data is None:
        return None, None, "в кэше нет подходящих данных"
    if age is not None and age > CACHE_EXPIRED_AFTER:
        return None, age, f"кэш устарел ({FormatAge(age)})"
    return data, age, note

def UpdateOnce():
    """Один цикл: сначала живые источники, при неудаче — кэш.

    Возвращает (data, возраст_данных, подпись_источника, успех_запроса).
    """
    ok, problems = FetchFromSources()
    data = age = note = None
    if ok:
        data, age = LoadCache(CACHE_FILE_CURRENT)
        note = "API"
    if data is None:
        data, age, note = PickCachedData()
        if data is not None:
            Log(f"КЭШ: использую {note}, возрастом {FormatAge(age)}")
    for msg in problems:
        Log(f"Ошибка API: {msg}")
    return data, age, note, ok

def ApplyToDisplay(data, age, note):
    #Сбор строк для табло. Делаем это целиком, чтобы поток дисплея не видел «полуправки».
    global weather_text_bytes, weather_conditions_bytes
    if data is None:
        weather_text_bytes = b'T???C P???mm H??%'.ljust(20)
        weather_conditions_bytes = bytes(UTFToASCIIPosUA("нет данных с API"))
        return
    text, conditions = FormatWeatherData(data)
    conditions = bytearray(conditions)
    if age is not None and age > CACHE_STALE_AFTER:
        conditions += UTFToASCIIPosUA(f"; нет обновлений {FormatAge(age)}")
        Log(f"ВНИМАНИЕ: данные устарели на {FormatAge(age)} (источник: {note})")
    weather_text_bytes, weather_conditions_bytes = text, bytes(conditions)

def WeatherWorker():
    fails = 0
    while True:
        data, age, note, ok = UpdateOnce()
        ApplyToDisplay(data, age, note)
        if ok:
            fails = 0
            delay = WEATHER_UPDATE_INTERVAL
        else:
            fails += 1
            delay = min(WEATHER_RETRY_BASE * (2 ** min(fails - 1, 5)), WEATHER_MAX_INTERVAL)
            Log(f"Неудача #{fails}, следующий через {FormatAge(delay)}")
        time.sleep(delay)

if __name__ == '__main__':
    if '--once' in sys.argv:
        # Диагностика: один цикл обновления, вывод того, что ушло бы на табло
        data, age, note, ok = UpdateOnce()
        ApplyToDisplay(data, age, note)
        Log(f"ТЕСТ: источник={note} успешен={ok} возраст={FormatAge(age)}")
        Log(f"ТЕСТ: строка1={bytes(weather_text_bytes)!r}")
        Log(f"ТЕСТ: строка2={bytes(weather_conditions_bytes)!r}")
        sys.exit(0 if ok else 1)

    # Запуск потока обновления погоды
    t = threading.Thread(target=WeatherWorker, daemon=True)
    t.start()

    port = None
    def open_port():
        global port
        try:
            if port: port.close()
            port = serial.Serial("COM5", 9600, timeout=0)
            Log(f"Порт COM5 открыт")
        except Exception as e:
            Log(f"Ошибка открытия порта: {e}")
            port = None

    open_port()

    i_scroll = 0
    fBegin = 0
    floatingFlag = False
    last_port_try = time.time()

    while True:
        now = datetime.datetime.now()
        days = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']
        time_str = f"{days[now.weekday()]} {now.strftime('%d.%m.%y %H:%M:%S')}"
        hString = UTFToASCIIPosUA(time_str.ljust(20))

        if floatingFlag:
            clean_temp = weather_text_bytes.strip()
            scroll_source = clean_temp + b'    ' + weather_conditions_bytes + b'     ' + clean_temp
            rawL = scroll_source[fBegin:20+fBegin]
            if fBegin > 10 and rawL.startswith(clean_temp):
                floatingFlag = False
                fBegin = 0
                i_scroll = 0
                lString = clean_temp.ljust(20)
            else:
                lString = rawL.ljust(20)
                fBegin += 1
        else:
            i_scroll += 1
            lString = weather_text_bytes.strip().ljust(20)
            if i_scroll >= 200:
                if len(weather_conditions_bytes) > 0:
                    floatingFlag = True
                    fBegin = 1
                else:
                    i_scroll = 0

        if port:
            try:
                port.write(hString + lString)
            except Exception as e:
                Log(f"Ошибка записи в порт: {e}")
                open_port() # Пробуем переоткрыть
        else:
            if time.time() - last_port_try >= 10: # Каждые 10 секунд пробуем переоткрыть
                last_port_try = time.time()
                open_port()

        time.sleep(0.1)
