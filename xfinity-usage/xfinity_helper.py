import base64
import glob
import json
import os
import requests
import secrets
import shutil
import string
import time
import uuid
from pathlib import Path
from cryptography.fernet import Fernet
from xfinity_globals import REQUESTS_TIMEOUT, exit_code
from xfinity_logger import logger

# Home Assistant API
BASHIO_SUPERVISOR_API = os.environ.get('BASHIO_SUPERVISOR_API', '')
BASHIO_SUPERVISOR_TOKEN = os.environ.get('BASHIO_SUPERVISOR_TOKEN', '')
SENSOR_NAME = "sensor.xfinity_usage"
SENSOR_URL = f"{BASHIO_SUPERVISOR_API}/core/api/states/{SENSOR_NAME}"
SENSOR_BACKUP = '/config/.sensor-backup'
ADDON_RESTART_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/restart"
ADDON_STOP_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/stop"
ADDON_OPTIONS_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options"
ADDON_OPTIONS_VALIDATE_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options/validate"
ADDON_OPTIONS_CONFIG_URL = f"{BASHIO_SUPERVISOR_API}/addons/self/options/config"



def load_key() -> bytes:
    """
    Load the previously generated key
    """
    return open("secret.key", "rb").read()

def encrypt_message(message) -> bytes:
    """
    Encrypts a message
    """
    key = load_key()
    encoded_message = message.encode()
    f = Fernet(key)
    encrypted_message = f.encrypt(encoded_message)

    #logger.info(base64.b64encode(encrypted_message).decode())
    return encrypted_message

def decrypt_message(encrypted_message) -> str:
    """
    Decrypts an encrypted message
    """
    key = load_key()
    f = Fernet(key)
    decrypted_message = f.decrypt(encrypted_message)
    return decrypted_message.decode()

def profile_cleanup() -> None:
    # Remove browser profile path to clean out cookies and cache
    profile_path = '/config/profile*'
    directories = glob.glob(profile_path)
    for directory in directories:
        if Path(directory).exists() and Path(directory).is_dir(): shutil.rmtree(directory)

def get_current_unix_epoch() -> float:
    return time.time()

def ordinal(n) -> str:
    s = ('th', 'st', 'nd', 'rd') + ('th',)*10
    v = n%100
    if v > 13:
      return f'{n}{s[v%10]}'
    else:
      return f'{n}{s[v]}'

def camelTo_snake_case(string: str) -> str:
    """Converts camelCase strings to snake_case"""
    return ''.join(['_' + i.lower() if i.isupper() else i for i in string]).lstrip('_')
    
def is_hassio() -> bool:
    if  bool(BASHIO_SUPERVISOR_API) and bool(BASHIO_SUPERVISOR_TOKEN):
        return True
    else:
        return False


def read_token_file_data(token_file: str) -> dict:
    token = {}
    if os.path.isfile(token_file) and os.path.getsize(token_file):
        with open(token_file, 'r') as file:
            token = json.load(file)
    return token

def write_token_file_data(token_data: dict, token_file: str) -> None:
    token_object = json.dumps(token_data)
    if  os.path.exists('/config/'):
        with open(token_file, 'w') as file:
            if file.write(token_object):
                logger.info(f"Updating OAuth Token File {token_file}")
                file.close()

def delete_token_file_data(token_file: str) -> None:
    if os.path.isfile(token_file) and os.path.getsize(token_file):
        os.remove(token_file)

def update_sensor_file(usage_data) -> None:
    if  usage_data is not None and \
        os.path.exists('/config/'):

        with open(SENSOR_BACKUP, 'w') as file:
            if file.write(json.dumps(usage_data)):
                logger.info(f"Updating Sensor File")
                file.close()


def update_ha_sensor(usage_data) -> None:
    if  is_hassio() and \
        usage_data is not None:

        headers = {
            'Authorization': 'Bearer ' + BASHIO_SUPERVISOR_TOKEN,
            'Content-Type': 'application/json',
        }

        logger.info(f"Updating Sensor: {SENSOR_NAME}")

        response = requests.post(
            SENSOR_URL,
            headers=headers,
            data=usage_data,
            timeout=REQUESTS_TIMEOUT
        )

        if response.ok:
            return None

        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")

    return None

def update_ha_sensor_on_startup() -> None:
    if os.path.isfile(SENSOR_BACKUP) and os.path.getsize(SENSOR_BACKUP):
        with open(SENSOR_BACKUP, 'r') as file:
            usage_data = file.read()
            update_ha_sensor(usage_data)

def restart_addon() -> None:
    if is_hassio():

        headers = {
            'Authorization': 'Bearer ' + BASHIO_SUPERVISOR_TOKEN,
            'Content-Type': 'application/json',
        }

        logger.info(f"Restarting Addon")

        response = requests.post(
            ADDON_RESTART_URL,
            headers=headers,
            timeout=REQUESTS_TIMEOUT
        )


        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")

    return None

def stop_addon() -> None:
    if is_hassio():

        headers = {
            'Authorization': 'Bearer ' + BASHIO_SUPERVISOR_TOKEN,
            'Content-Type': 'application/json',
        }

        logger.info(f"Stopping Addon")

        response = requests.post(
            ADDON_STOP_URL,
            headers=headers,
            timeout=REQUESTS_TIMEOUT
        )


        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")

    return None

def update_addon_options(addon_options) -> bool:
    if validate_addon_options(addon_options):
        new_options = {'options': addon_options}

        headers = {
            'Authorization': 'Bearer ' + BASHIO_SUPERVISOR_TOKEN,
            'Content-Type': 'application/json',
        }

        logger.info(f"Updating Addon Config")
        logger.debug(f"Updated Options: {new_options}")

        response = requests.post(
            ADDON_OPTIONS_URL,
            headers=headers,
            json=new_options,
            timeout=REQUESTS_TIMEOUT
        )


        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")
        if response.ok:
            return True

    return False

def validate_addon_options(addon_options) -> bool:

    if is_hassio() and addon_options:

        headers = {
            'Authorization': 'Bearer ' + BASHIO_SUPERVISOR_TOKEN,
            'Content-Type': 'application/json',
        }

        logger.info(f"Validating Addon Config")
        logger.debug(addon_options)

        response = requests.post(
            ADDON_OPTIONS_VALIDATE_URL,
            headers=headers,
            json=addon_options,
            timeout=REQUESTS_TIMEOUT
        )

        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")
        if response.ok:
            json_result = response.json()
            return bool(json_result['data']['valid'])

    return False

def get_addon_options() -> dict:
    json_result = {}
    if is_hassio():

        headers = {
            'Authorization': 'Bearer ' + BASHIO_SUPERVISOR_TOKEN,
            'Content-Type': 'application/json',
        }

        logger.debug(f"Retrieving Addon Config")

        response = requests.get(
            ADDON_OPTIONS_CONFIG_URL,
            headers=headers,
            timeout=REQUESTS_TIMEOUT
        )

        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")

        if response.ok:
            json_result = response.json()
            if 'data' in json_result:
                return json_result['data']

    return json_result

def clear_token(addon_options={}) -> None:

    if is_hassio():
        if 'refresh_token' in addon_options:
            del addon_options['refresh_token']

        if 'clear_token' in addon_options:
            addon_options['clear_token'] = False

    for file_path in glob.glob(os.path.join('/config', f'.*.json')):
        try:
            os.remove(file_path)
            logger.info(f"Deleted: {file_path}")
        except OSError as e:
            logger.error(f"Error deleting {file_path}: {e}")

    logger.info(f"Clearing saved tokens")
    logger.debug(f"{addon_options}")

    if is_hassio():
        if update_addon_options(addon_options):
            restart_addon()
        else:
            stop_addon()
    else:
        exit(exit_code.TOKEN_CODE.value)


def process_usage_json(_raw_usage_data: dict, _raw_plan_data: dict) -> bool:
    _plan_detail = _raw_plan_data
    _cur_month = _raw_usage_data['usageMonths'][-1]
    usage_data = {}
    
    # record current month's information
    # convert key names to 'snake_case'
    attributes = {}
    for k, v in _cur_month.items():
        attributes[camelTo_snake_case(k)] = v

    if _cur_month['policy'] == 'limited':
        # extend data for limited accounts
        #attributes['accountNumber'] = _raw_usage_data['accountNumber']
        attributes['courtesy_used'] = _raw_usage_data.get('courtesyUsed', None)
        attributes['courtesy_remaining'] = _raw_usage_data.get('courtesyRemaining', None)
        attributes['courtesy_allowed'] = _raw_usage_data.get('courtesyAllowed', None)
        attributes['courtesy_months'] = _raw_usage_data.get('courtesyMonths', None)
        attributes['in_paid_overage'] = _raw_usage_data.get('inPaidOverage', None)
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

    if 'downloadSpeed' in _plan_detail:
        json_dict['attributes']['internet_download_speeds_Mbps'] = _plan_detail['downloadSpeed']
        json_dict['attributes']['internet_upload_speeds_Mbps'] = _plan_detail['uploadSpeed']
    else:
        json_dict['attributes']['internet_download_speeds_Mbps'] =  -1
        json_dict['attributes']['internet_upload_speeds_Mbps'] = -1

    if total_usage >= 0:
        usage_data = json_dict
        logger.info(f"Usage data retrieved and processed")
        usage_data_b64 = base64.b64encode(json.dumps(usage_data).encode()).decode()
        logger.debug(f"Usage Data: {usage_data_b64}")
    else:
        usage_data = None
    
    return usage_data


