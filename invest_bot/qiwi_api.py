import json
import logging
import requests
import traceback
from urllib.parse import urlencode, quote_plus

from invest_bot.utils import get_exp_date


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level = logging.INFO,
    filename = 'log.log'
    )


def get_payment_url_old(billid, sum, user_id, qiwi_secret_key):
    headers = {
        'accept': 'application/json',
        'Authorization': 'Bearer ' + qiwi_secret_key,
        'content-type': 'application/json'
    }

    params = {
        'amount': {
            'currency': 'RUB',
            'value': str(sum)
            },
        'expirationDateTime': get_exp_date(),
        'comment': str(user_id)
    }

    url = f'https://api.qiwi.com/partner/bill/v1/bills/{str(billid)}'
    try:
        resp = requests.put(url, json=params, headers=headers)
        resp.raise_for_status()
    except Exception:
        logging.info(str(traceback.format_exc()))
        return False

    return resp.json().get('payUrl')


def get_payment_url(billid, sum, qiwi_comment, qiwi_public_key, qiwi_code):
    params = {
        'publicKey': qiwi_public_key,
        'billId': billid,
        'amount': str(sum),
        'lifetime': get_exp_date(),
        'customFields[themeCode]': qiwi_code
    }
    if qiwi_comment:
        params['comment'] = qiwi_comment

    tail = urlencode(params, quote_via=quote_plus)
    return f'https://oplata.qiwi.com/create?{tail}'


def get_payment_status(billid, qiwi_secret_key):
    headers = {
        'accept': 'application/json',
        'Authorization': 'Bearer ' + qiwi_secret_key
    }

    url = f'https://api.qiwi.com/partner/bill/v1/bills/{billid}'
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
    except Exception:
        logging.info(str(traceback.format_exc()))
        return False

    try:
        status = resp.json()['status']['value']
        amount = resp.json()['amount']['value']
    except KeyError:
        logging.info(str(traceback.format_exc()))
        return False

    if status:
        return status, amount
