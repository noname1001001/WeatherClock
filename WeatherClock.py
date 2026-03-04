#TODO: больше обработки ошибок для повышения стабильности;
#      уменьшение количества операций над строками для повышения производительности;
#      неблокирующие или параллельные ввод-вывод и обновление погоды;
#      сохранение данных о погоде локально.
import serial
import os, datetime, time, requests
from dotenv import load_dotenv
# import usb.core
# import usb.util

WEATHER_UPDATE_INTERVAL = 3000


def GetWeather(id = 503978):
    try:
        load_dotenv()
        api_key = os.getenv('OPENWEATHER_API_KEY')
        if not api_key:
            print("Ошибка: API-ключ не найден в переменных окружения или файле .env")
            return None
        res = requests.get("http://api.openweathermap.org/data/2.5/weather",
            params={'q': 'Moscow', 'units': 'metric', 'APPID': api_key, 'lang' : 'ru'},
            timeout=30)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.HTTPError as errh:
        print ("Http Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:", errt)
    except Exception as exc:
        print("Exception (weather):", exc)
        return None


def TestDisplayCharacters():
    test = bytearray (b'\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0')
    for i in range (255):
        for j in range(20):
            test[j] = i
        port.write (test)
        port.write (test)
        print('%03d\t%02X' % i, i)
        os.system('pause')

def WindConvert(angle = None):
    windDirection = ''
    if angle is not None:
        try:
            direction = ['северный',  # [0-11.25)
                         'северо-северо-восточный',  # [11.25-22.5)
                         'северо-северо-восточный',  # [22.5-33.75)
                         'северо-восточный',
                         'северо-восточный',
                         'восточно-северо-восточный',
                         'восточно-северо-восточный',
                         'восточный',
                         'восточный',
                         'восточно-юго-восточный',
                         'восточно-юго-восточный',
                         'юго-восточный',
                         'юго-восточный',
                         'юго-юго-восточный',
                         'юго-юго-восточный',
                         'южный',
                         'южный',
                         'юго-юго-западный',
                         'юго-юго-западный',
                         'юго-западный',
                         'юго-западный',
                         'западно-юго-западный',
                         'западно-юго-западный',
                         'западный',
                         'западный',
                         'западно-северо-западный',
                         'западно-северо-западный',
                         'северо-западный',
                         'северо-западный',
                         'северо-северо-западный',
                         'северо-северо-западный',
                         'северный',
                         'северный']
            directionIndex = int(angle//11.25)
            windDirection = direction[directionIndex]
        except Exception as exc:
            print('Ошибка при конвертации угла в румбы ветра. Текст исключения: ', exc)
            return str(angle)+' градусов'
        else:
            return windDirection

def __UNITTEST__WindConvert():
    for i in range(361):
        print(i, WindConvert(i))


def UTFToASCIIPosUA(string=None):     # posua - таблица латиницы [128 - 159] (заглавные) и { [160-175] - [224-239] }
                                      # (прописные) последовательно (АБВГД)(!!!БЕЗ БУКВЫ 'Ё'!!!)
    result = None
    charDict = {'А': b'\x80',  'а': b'\xA0',      'Q': b'Q', 'q': b'q',
                'Б': b'\x81',  'б': b'\xA1',      'W': b'W', 'w': b'w',
                'В': b'\x82',  'в': b'\xA2',      'E': b'E', 'e': b'e',
                'Г': b'\x83',  'г': b'\xA3',      'R': b'R', 'r': b'r',
                'Д': b'\x84',  'д': b'\xA4',      'T': b'T', 't': b't',
                'Е': b'\x85',  'е': b'\xA5',      'Y': b'Y', 'y': b'y',
                'Ё': b'\x85',  'ё': b'\xA5',      'U': b'U', 'u': b'u',
                'Ж': b'\x86',  'ж': b'\xA6',      'I': b'I', 'i': b'i',
                'З': b'\x87',  'з': b'\xA7',      'O': b'O', 'o': b'o',
                'И': b'\x88',  'и': b'\xA8',      'P': b'P', 'p': b'p',
                'Й': b'\x89',  'й': b'\xA9',      'A': b'A', 'a': b'a',
                'К': b'\x8A',  'к': b'\xAA',      'S': b'S', 's': b's',
                'Л': b'\x8B',  'л': b'\xAB',      'D': b'D', 'd': b'd',
                'М': b'\x8C',  'м': b'\xAC',      'F': b'F', 'f': b'f',
                'Н': b'\x8D',  'н': b'\xAD',      'G': b'G', 'g': b'g',
                'О': b'\x8E',  'о': b'\xAE',      'H': b'H', 'h': b'h',
                'П': b'\x8F',  'п': b'\xAF',      'J': b'J', 'j': b'j',
                'Р': b'\x90',  'р': b'\xE0',      'K': b'K', 'k': b'k',
                'С': b'\x91',  'с': b'\xE1',      'L': b'L', 'l': b'l',
                'Т': b'\x92',  'т': b'\xE2',      'Z': b'Z', 'z': b'z',
                'У': b'\x93',  'у': b'\xE3',      'X': b'X', 'x': b'x',
                'Ф': b'\x94',  'ф': b'\xE4',      'C': b'C', 'c': b'c',
                'Х': b'\x95',  'х': b'\xE5',      'V': b'V', 'v': b'v',
                'Ц': b'\x96',  'ц': b'\xE6',      'B': b'B', 'b': b'b',
                'Ч': b'\x97',  'ч': b'\xE7',      'N': b'N', 'n': b'n',
                'Ш': b'\x98',  'ш': b'\xE8',      'M': b'M', 'm': b'm',
                'Щ': b'\x99',  'щ': b'\xE9',
                'Ь': b'\x9A',  'ь': b'\xEA',
                'Ы': b'\x9B',  'ы': b'\xEB',
                'Ъ': b'\x9C',  'ъ': b'\xEC',
                'Э': b'\x9D',  'э': b'\xED',
                'Ю': b'\x9E',  'ю': b'\xEE',
                'Я': b'\x9F',  'я': b'\xEF',
                ' ': b' '   ,  ':': b'\x3A',
                '/': b'/'   ,  '.': b'.',
                ',': b','   ,  ';': b';',
                "'": b"'"   ,  '"': b'"',
                '-': b'-'}
    
    if string != None:
        result = bytearray([charDict[string[i]][0]   for i in range(len(string))])#
    return result


def FormatWeatherData(weather):
    if weather is not None:
        print (weather)
        temperature = None
        pressure = None
        pressure = None
        humidity = None
        conditions = None
        try:
            temperature = weather['main']['temp']
            pressure = weather['main']['pressure']
            pressure = pressure/1.33333
            humidity = weather['main']['humidity']
            conditions = weather['weather'][0]['description']
            wind = weather['wind']['speed']
            if 'deg' in weather['wind']:
                windDeg = weather['wind']['deg']
            else:
                windDeg = 0
        except Exception as exc:
            print('Ошибка JSON.')
            textWeather = b'T???C P???mm H??%'
            textWeather = textWeather.ljust(20, b' ')
            conditions = UTFToASCIIPosUA('Ошибка доступа по ключу к элементам загруженного ')
            conditions += str('JSON-').encode('ascii') + UTFToASCIIPosUA('файла. Текст исключения: ')
            conditions += str(exc.with_traceback).encode('ascii') + str(exc).encode('ascii')
            print(exc.with_traceback, exc)
        else:
            temperature = str(temperature).encode ('ascii')
            pressure = str(pressure)[0:3].encode ('ascii')
            humidity = str(humidity).encode ('ascii')
            wind = str(wind).encode ('ascii')
            windDirection = UTFToASCIIPosUA(WindConvert(windDeg))
            conditions = UTFToASCIIPosUA(conditions) + b'; ' + UTFToASCIIPosUA('ветер ') + windDirection + b', ' + wind + UTFToASCIIPosUA(' м/с')
            celsium = bytearray(b'C ')
            textWeather = b'T' + temperature[0:4] + celsium + b'P' + pressure + b'mm ' + b'H' + humidity + b'%'
            textWeather = textWeather.ljust(20, b' ')
    else:
        textWeather = b'T???C P???mm H??%'
        textWeather = textWeather.ljust(20, b' ')
        conditions  = UTFToASCIIPosUA('Не удаётся подключиться к ресурсу ') + b'"http://api.openweathermap.org/". ' + UTFToASCIIPosUA('Отсутствует подключение к интернету')
    return textWeather, conditions


if __name__ == '__main__':
    found = False
    grad = bytearray(b'\0')
    grad[0] = 223
    floatingFlag = False
    fBegin = 0
    #foundPort = ' '
    #for i in range(64) :
    #    try :
    #        prt = "COM%d" % 99 # i
    #        ser = serial.Serial(prt)
    #        ser.close()
    #        print ("Найден последовательный порт: ", prt)
    #        foundPort = prt
    #        found = True
    #    except serial.serialutil.SerialException :
    #        pass
    #os.system('pause')
    #if not found :
    #    print ("Последовательных портов не обнаружено")
    #    pass
    #else:
    #    port = serial.Serial(foundPort, 9600, timeout=0)
    #    print ("порт открыт")
    #    i = 0
    i = 0
    port = serial.Serial("COM%d" % 1, 9600, timeout=0)
    #TestDisplayCharacters ()
    #os.system('pause')
    weather = GetWeather()
    textWeather, conditions = FormatWeatherData(weather)
    lString = textWeather
    while True:
        currentTime = datetime.datetime.now()
        ms = str(currentTime.microsecond)
        h = str(currentTime.hour)
        m = str(currentTime.minute)
        s = str(currentTime.second)
        day = str(currentTime.day)
        month = str(currentTime.month)
        year  = str(currentTime.year)
        if len(h) == 1:
            h = '0' + h
        if len(m) == 1:
            m = '0' + m
        if len(s) == 1:
            s = '0' + s
        if len(day) == 1:
            day = '0' + day
        if len(month) == 1:
            month = '0' + month
        s = s.encode('ascii')
        m = m.encode('ascii')
        h = h.encode('ascii')
        ms = ms.encode('ascii')
        day = day.encode('ascii')
        month = month.encode('ascii')
        year = year.encode('ascii')
        # форматирование верхней строки даты/времени
        i+=1
        date = day + b'.' + month + b'.' + year[2:4]
        hString = date.ljust(10, b' ')
        tm = h + b':' + m + b':' + s
        hString += tm + b'.' + ms[0:1]
        # обработка "плавающей" строки с погодными условиями
        if floatingFlag == True:
            if i % 1 == 0:
                if (len(conditions) + 48) > (20 + fBegin):
                    lString = (textWeather + b'  ' + conditions + 5*b' ' + textWeather)[fBegin:20+fBegin]
                    lString = lString.ljust(20, b' ')
                    fBegin += 1
                else:
                    fBegin = 1
                    floatingFlag = False
        else:
            if fBegin == 1:
                lString = textWeather
                fBegin = 0
            else:
                if i % 150 == 0:
                    if lString == textWeather:
                        lString = (textWeather + conditions)[fBegin:20+fBegin]
                        floatingFlag = True
                    else:
                        lString = textWeather
        if i == WEATHER_UPDATE_INTERVAL: # weather update
            i = 0
            os.system ('cls')
            weather = GetWeather() #print(weather)
            textWeather, conditions = FormatWeatherData(weather)
            lString = textWeather
        try:
            port.write(hString + lString)
        except serial.serialutil.SerialTimeoutException as exc:
            print(exc)
        except serial.serialutil.SerialException as exc:
            print(exc)
        time.sleep(0.1)