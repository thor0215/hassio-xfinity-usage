import asyncio
import base64
import colorlog
import fnmatch
import glob
import hashlib
import json
import jwt
import logging
import os
import random
import re
import requests
import secrets
import shutil
import socket
import ssl
import string
import sys
import textwrap
import time
import uuid
import urllib.parse
from datetime import datetime
from enum import Enum
from tenacity import stop_after_attempt,  wait_exponential, retry, before_sleep_log
from time import sleep
from paho.mqtt import client as mqtt
from pathlib import Path
from playwright.async_api import async_playwright, Playwright, Route, Response, Request, Frame, Page, expect

from xfinity_helper import *
from xfinity_mqtt import XfinityMqtt

def convert_raw_usage_to_website_format(_raw_usage: dict) -> dict:
    """

    {
        "policy": "limited",
        "month": 2,
        "year": 2024,
        "startDate": "2024-02-01",
        "endDate": "2024-02-29",
        "daysRemaining": 0,
        "currentUsage": {
            "value": 558,
            "unit": "GB"
        },
        "allowableUsage": {
            "value": 1.23,
            "unit": "TB"
        },
        "overage": false,
        "overageCharge": 0,
        "maximumOverageCharge": 100,
        "courtesyCredit": false
    }

    {
        "startDate": "10/01/2024",
        "endDate": "10/31/2024",
        "totalUsage": 691,
        "allowableUsage": 1229,
        "unitOfMeasure": "GB",
        "policy": "limited"
    }
    """
    reversed_raw_usage = list(reversed(_raw_usage['monthlyUsage']))
    new_raw_usage = { 'usageMonths': [] }
    for item in reversed_raw_usage:
        split_start_date = item['startDate'].split('-')
        startDate = split_start_date[1] + '/' + split_start_date[2] + '/' + split_start_date[0]

        split_end_date = item['endDate'].split('-')
        endDate = split_end_date[1] + '/' + split_end_date[2] + '/' + split_end_date[0]

        if item['currentUsage']['unit'] == 'TB':
            totalUsage = int(item['currentUsage']['value'] * 1000)
        else: 
            totalUsage = int(item['currentUsage']['value'])

        allowableUsage = int(item['allowableUsage']['value'] * 1000)
        
        new_raw_usage['usageMonths'].append( {
            "startDate": startDate,
            "endDate": endDate,
            "totalUsage": totalUsage,
            "allowableUsage": allowableUsage,
            "unitOfMeasure": "GB",
            "policy": "limited"
        } )

    return new_raw_usage

def process_usage_json(_raw_internet_data: dict) -> bool:
    _plan_detail = _raw_internet_data.get('plan')

    _raw_usage = convert_raw_usage_to_website_format(_raw_internet_data.get('usage'))
    _cur_month = _raw_usage['usageMonths'][-1]
    # record current month's information
    # convert key names to 'snake_case'
    attributes = {}
    for k, v in _cur_month.items():
        attributes[camelTo_snake_case(k)] = v

    if _cur_month['policy'] == 'limited':
        # extend data for limited accounts
        #attributes['accountNumber'] = _raw_usage['accountNumber']
        #attributes['courtesy_used'] = _raw_usage['courtesyUsed']
        #attributes['courtesy_remaining'] = _raw_usage['courtesyRemaining']
        #attributes['courtesy_allowed'] = _raw_usage['courtesyAllowed']
        #attributes['courtesy_months'] = _raw_usage['courtesyMonths']
        #attributes['in_paid_overage'] = _raw_usage['inPaidOverage']
        attributes['remaining_usage'] = _cur_month['allowableUsage'] - _cur_month['totalUsage']

    # assign some values as properties
    total_usage = _cur_month['totalUsage']

    json_dict = {}
    json_dict['attributes'] = attributes
    json_dict['attributes']['friendly_name'] = 'Xfinity Usage'
    json_dict['attributes']['unit_of_measurement'] = _cur_month['unitOfMeasure']
    json_dict['attributes']['device_class'] = 'data_size'
    json_dict['attributes']['state_class'] = 'measurement'
    json_dict['attributes']['icon'] = 'mdi:wan'
    json_dict['state'] = total_usage

    if  _plan_detail is not None and \
        _plan_detail.get('downloadSpeed'):
            json_dict['attributes']['internet_download_speeds_Mbps'] = _plan_detail['downloadSpeed']['value']


    if total_usage >= 0:
        usage_data = json_dict
        logger.info(f"Usage data retrieved and processed")
        logger.debug(f"Usage Data JSON: {json.dumps(usage_data)}")
    else:
        usage_data = None
    
    return usage_data


def get_gateway_details_data(_TOKEN) -> None:
    _gateway_details = {}
    headers = {
        'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
        'x-id-token': f"{_TOKEN['id_token']}",
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 14; SM-G991B Build/UE1A.230829.050)',
        'x-apollo-operation-id': '34a752659014e11c5617dc4d469941230f2b25dffab3197d5bde752a9ecc5569',
        'x-apollo-operation-name': 'User'
    }
    headers.update(OAUTH_USAGE_EXTRA_HEADERS)
    data = '{"operationName":"User","variables":{"customerGuid":"' + _TOKEN['customer_guid'] + '"},"query":"query User($customerGuid: ID) { user(customerGuid: $customerGuid) { experience analytics eligibilities tabs account { serviceAccountId billingAccountId partner timeZone zipCode primaryGateway { make model macAddress deviceClass } router { make model macAddress deviceClass deviceType coam } modem { make model macAddress deviceClass deviceType coam } } } }"}'
    
    result = requests.post(GRAPHQL_URL, 
                            headers=headers, 
                            data=data,
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY)

    response_json = result.json()

    if result.ok:
        if  'errors' not in response_json and 'data' in response_json and \
            len(response_json['data']['user']['account']['primaryGateway']) > 0:
                _gateway_details = response_json['data']['user']['account']['primaryGateway']
                logger.info(f"Updating Device Details")
        logger.debug(f"Updating Device Details {json.dumps(response_json)}")
    else:
        raise AssertionError(f"GraphQL Gateway Error: {json.dumps(response_json)}")

    return _gateway_details


def get_internet_details_data(_TOKEN) -> None:
    _internet_details = {}
    headers = {
        'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
        'x-id-token': f"{_TOKEN['id_token']}",
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 14; SM-G991B Build/UE1A.230829.050)',
        'x-apollo-operation-id': 'cb26cdb7288e179b750ec86d62f8a16548902db3d79d2508ca98aa4a8864c7e1',
        'x-apollo-operation-name': 'AccountServicesWithoutXM'
    }
    headers.update(OAUTH_USAGE_EXTRA_HEADERS)
    data = '{"operationName":"AccountServicesWithoutXM","variables":{},"query":"query AccountServicesWithoutXM { accountByServiceAccountId { internet { plan { name downloadSpeed { unit value } uploadSpeed { unit value } } usage { inPaidOverage courtesy { totalAllowableCourtesy usedCourtesy remainingCourtesy } monthlyUsage { policy month year startDate endDate daysRemaining currentUsage { value unit } allowableUsage { value unit } overage overageCharge maximumOverageCharge courtesyCredit } } } home { plan } video { plan { name description flex stream x1 } } } }"}'
    
    result = requests.post(GRAPHQL_URL, 
                            headers=headers, 
                            data=data,
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY)

    response_json = result.json()

    if result.ok:
        if  'errors' not in response_json and 'data' in response_json and \
            len(response_json['data']['accountByServiceAccountId']['internet']['usage']['monthlyUsage']) > 0:
                logger.info(f"Updating Usage/Plan Details")
                _internet_details = response_json['data']['accountByServiceAccountId']['internet']
        logger.debug(f"Updating Usage/Plan Details {json.dumps(response_json)}")
    else:
        raise AssertionError(f"GraphQL Usage Error:  {json.dumps(response_json)}")
    return _internet_details

