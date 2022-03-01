import requests
import json
import time
import datetime
from typing import List
import telebot
from keys import BOT_PRIVATE_KEY

# Tinkoff
TINKOFF_BRAND_ID = 'tcs'
CHANNEL_NAME = '@tinkoff_cash_nsk'


def get_cloud_atms() -> List[dict]:
    """
    Получить банкоматы из облака
    """
    url = "https://api.tinkoff.ru/geo/withdraw/clusters"
    headers = {
        "accept": "*/*",
        "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "sec-ch-ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"98\", \"Google Chrome\";v=\"98\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"macOS\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site"
    }
    body = {
        'bounds': {
            'bottomLeft': {'lat': 54.96279534571581, 'lng': 82.8285085199824},
            'topRight': {'lat': 55.061444569513185, 'lng': 83.06025137886912}
        },
        'filters': {'showUnavailable': True, 'currencies': ['USD']},
        'zoom': 11
    }
    response = requests.post(url=url, headers=headers, data=json.dumps(body))

    if not response or response.status_code != 200:
        raise Exception('Wrong request')

    clusters = response.json().get('payload').get('clusters')
    available_atms = []
    for cluster in clusters:
        for point in cluster.get('points'):
            available_atms.append(point)

    return available_atms


def format_atm_info(atm: dict) -> dict:
    """
    Сформатировать информацию о банкомате
    :param atm: Банкомат
    :return: Информация о банкомате
    """
    brand = atm.get('brand')
    brand_name = brand.get('name')
    brand_id = brand.get('id')

    id = atm.get('id')
    place_name = atm.get('installPlace') or brand_name

    location = atm.get('location')
    location_lat = location.get('lat')
    location_lng = location.get('lng')

    address = atm.get('address')

    limits = atm.get('limits')
    currencies = []
    for currency in limits:
        currencies.append({'type': currency.get('currency'),
                           'amount': currency.get('amount'),
                           'max': currency.get('max')})

    return {
        'brand_id': brand_id,
        'brand_name': brand_name,
        'id': id,
        'place_name': place_name,
        'location_lat': location_lat,
        'location_lng': location_lng,
        'address': address,
        'currencies': currencies or []
    }


def get_atms_with_cash(currency_type='USD', only_tinkoff=False):
    """
    Получить банкоматы с валютой
    """
    atms_with_cash = dict()
    atms = get_cloud_atms()
    for atm in atms:
        atm_info = format_atm_info(atm)

        # Скипаем прочие банкоматы
        if only_tinkoff and atm_info.get('brand_id') != TINKOFF_BRAND_ID:
            continue

        # Скипаем банкоматы без нужной валюты
        atm_currencies = atm_info.get('currencies') or []
        for curr in atm_currencies:
            if curr.get('type') == currency_type and curr.get('max') > 0:
                atms_with_cash[atm_info.get('id')] = atm_info
    return atms_with_cash


def format_message(atm_info):
    """
    Сформировать сообщение
    :param atm_info:
    :return:
    """
    currencies_str = ''
    atm_currencies = atm_info.get('currencies')
    date_time = datetime.datetime.now().strftime("%Y.%m.%d %H:%M")
    for curr in atm_currencies:
        currencies_str += f'\n____\nТип: {curr.get("type")}\n' \
                          f'Макс: {curr.get("max")}\n' \
                          f'Доступно: {curr.get("amount") or 0}\n_____\n'
    return f'\n{atm_info.get("brand_name")} {currencies_str}' \
           f'Адрес: {atm_info.get("address")} \n' \
           f'Актуальность: {date_time}'


bot = telebot.TeleBot(BOT_PRIVATE_KEY, parse_mode=None)


@bot.message_handler(commands=["new"])
def start(m, res=False):
    for key, atm in get_atms_with_cash().items():
        message = format_message(atm)
        bot.send_message(m.chat.id, message)
        bot.send_location(m.chat.id, latitude=atm.get('location_lat'), longitude=atm.get('location_lng'),
                          disable_notification=True)


bot.polling(none_stop=True, interval=0)

available_atm_ids = dict().keys()
while True:
    time.sleep(120)
    available_atms = get_atms_with_cash()
    new_atms = set(available_atms.keys()) - set(available_atm_ids)
    if new_atms:
        new_atm_id = list(new_atms)[0]
        new_atm = available_atms[new_atm_id]
        message = format_message(new_atm)
        available_atm_ids = available_atms.keys()
        bot.send_message(CHANNEL_NAME, message)
        bot.send_location(CHANNEL_NAME, latitude=new_atm.get('location_lat'), longitude=new_atm.get('location_lng'),
                        disable_notification=True)
