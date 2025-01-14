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

        policy = item['policy']
        
        new_raw_usage['usageMonths'].append( {
            "startDate": startDate,
            "endDate": endDate,
            "totalUsage": totalUsage,
            "allowableUsage": allowableUsage,
            "unitOfMeasure": "GB",
            "policy": policy
        } )

    return new_raw_usage

def process_usage_json(_raw_usage_data: dict, _raw_plan_data: dict) -> bool:
    _plan_detail = _raw_plan_data

    _raw_usage = convert_raw_usage_to_website_format(_raw_usage_data)
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
        'x-id-token': f"{_TOKEN['access_token']}"
    }
    headers.update(GRAPHQL_GATGEWAY_DETAILS_HEADERS)
    headers.update(GRAPHQL_EXTRA_HEADERS)
    #data = '{"operationName":"User","variables":{"customerGuid":"' + _TOKEN['customer_guid'] + '"},"query":"query User($customerGuid: ID) { user(customerGuid: $customerGuid) { experience analytics eligibilities tabs account { serviceAccountId billingAccountId partner timeZone zipCode primaryGateway { make model macAddress deviceClass } router { make model macAddress deviceClass deviceType coam } modem { make model macAddress deviceClass deviceType coam } } } }"}'
    query = """
            query User($customerGuid: ID) {
                user(customerGuid: $customerGuid) {
                    experience
                    account {
                        serviceAccountId
                        billingAccountId
                        partner
                        timeZone
                        zipCode
                        primaryGateway {
                            make
                            model
                            macAddress
                            deviceClass
                        }
                        router {
                            make
                            model
                            macAddress
                            deviceClass
                            deviceType
                            coam
                        }
                        modem {
                            make
                            model
                            macAddress
                            deviceClass
                            deviceType
                            coam
                        }
                    }
                }
            }
    """
    data =  {
            "operationName": "User",
            "variables": {
                 "customerGuid": _TOKEN['customer_guid']
            },
            "query": query
    }
    
    response = requests.post(GRAPHQL_URL, 
                            headers=headers, 
                            json=data,
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY,
                            timeout=REQUESTS_TIMEOUT)

    response_json = response.json()
    logger.debug(f"Response Status Code: {response.status_code}")
    logger.debug(f"Response: {response.text}")
    logger.debug(f"Response JSON: {response.json()}")


    if  response.ok and \
        'errors' not in response_json and \
        'data' in response_json and \
        len(response_json['data']['user']['account']['modem']) > 0:
            _gateway_details = response_json['data']['user']['account']['modem']
            logger.info(f"Updating Device Details")
            logger.debug(f"Updating Device Details {json.dumps(response_json)}")
    else:
        #raise AssertionError(f"GraphQL Gateway Error: {json.dumps(response_json)}")
        logger.error(f"GraphQL Gateway Error: {json.dumps(response_json)}")

    return _gateway_details


def get_usage_details_data(_TOKEN) -> None:
    _usage_details = {}
    headers = {
        'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
        'x-id-token': f"{_TOKEN['access_token']}"
    }
    headers.update(GRAPHQL_USAGE_DETAILS_HEADERS)
    headers.update(GRAPHQL_EXTRA_HEADERS)
    #data = '{"operationName": "InternetDataUsage","variables": {},"query": "query InternetDataUsage { accountByServiceAccountId { internet { usage { inPaidOverage courtesy { totalAllowableCourtesy usedCourtesy remainingCourtesy } monthlyUsage { policy month year startDate endDate daysRemaining currentUsage { value unit } allowableUsage { value unit } overage overageCharge maximumOverageCharge courtesyCredit } } } } }"}'
    query = """
            query InternetDataUsage {
                accountByServiceAccountId {
                    internet {
                        usage {
                            monthlyUsage {
                            policy
                            startDate
                            endDate
                            daysRemaining
                            currentUsage {
                                value
                                unit
                            }
                            allowableUsage {
                                value
                                unit
                            }
                            }
                        }
                    }
                }
            }
    """
    data =  {
            "operationName": "InternetDataUsage",
            "variables": {},
            "query": query
    }

    response = requests.post(GRAPHQL_URL, 
                            headers=headers, 
                            json=data,
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY,
                            timeout=REQUESTS_TIMEOUT)

    response_json = response.json()
    logger.debug(f"Response Status Code: {response.status_code}")
    logger.debug(f"Response: {response.text}")
    logger.debug(f"Response JSON: {response.json()}")

    if  response.ok and \
        'errors' not in response_json and \
        'data' in response_json and \
        len(response_json['data']['accountByServiceAccountId']['internet']['usage']['monthlyUsage']) > 0:
            logger.info(f"Updating Usage Details")
            _usage_details = response_json['data']['accountByServiceAccountId']['internet']['usage']
            logger.debug(f"Updating Usage Details {json.dumps(response_json)}")
            return _usage_details

    else:
        #raise AssertionError(f"GraphQL Usage Error:  {json.dumps(response_json)}")
        logger.error(f"GraphQL Usage Error:  {json.dumps(response_json)}")

    return _usage_details


def get_plan_details_data(_TOKEN) -> None:
    _plan_details = {}
    headers = {
        'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
        'x-id-token': f"{_TOKEN['access_token']}"
    }
    headers.update(GRAPHQL_PLAN_DETAILS_HEADERS)
    headers.update(GRAPHQL_EXTRA_HEADERS)
    #data =  '{"operationName":"AccountServicesWithoutXM","variables":{},"query":"query AccountServicesWithoutXM { accountByServiceAccountId { internet { plan { name downloadSpeed { unit value } uploadSpeed { unit value } } usage { inPaidOverage courtesy { totalAllowableCourtesy usedCourtesy remainingCourtesy } monthlyUsage { policy month year startDate endDate daysRemaining currentUsage { value unit } allowableUsage { value unit } overage overageCharge maximumOverageCharge courtesyCredit } } } home { plan } video { plan { name description flex stream x1 } } } }"}'
    query = """
            query AccountServicesWithoutXM {
                accountByServiceAccountId {
                    internet {
                    plan {
                        name
                        downloadSpeed {
                        unit
                        value
                        }
                        uploadSpeed {
                        unit
                        value
                        }
                    }
                    }
                }
            }
    """
    data =  {
            "operationName": "AccountServicesWithoutXM",
            "variables": {},
            "query": query
    }
    
    response = requests.post(GRAPHQL_URL, 
                            headers=headers, 
                            json=data,
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY,
                            timeout=REQUESTS_TIMEOUT)

    response_json = response.json()
    logger.debug(f"Response Status Code: {response.status_code}")
    logger.debug(f"Response: {response.text}")
    logger.debug(f"Response JSON: {response.json()}")

    if  response.ok and \
        'errors' not in response_json and \
        'data' in response_json and \
        len(response_json['data']['accountByServiceAccountId']['internet']['plan']) > 0:
            logger.info(f"Updating Plan Details")
            _plan_details = response_json['data']['accountByServiceAccountId']['internet']['plan']
            logger.debug(f"Updating Usage/Plan Details {json.dumps(response_json)}")
            return _plan_details

    else:
        #raise AssertionError(f"GraphQL Plan Error:  {json.dumps(response_json)}")
        logger.error(f"GraphQL Plan Error:  {json.dumps(response_json)}")

    return _plan_details
