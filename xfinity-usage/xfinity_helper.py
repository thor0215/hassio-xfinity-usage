import base64
import glob
import hashlib
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
from xfinity_globals import *
from xfinity_logger import *




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

def generate_code_challenge(code_verifier) -> str:
    """Generates a code challenge from a code verifier."""

    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').rstrip('=')
    return code_challenge

def generate_code_verifier() -> str:
    """Generates a random code verifier."""

    return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')

def generate_state(length=22) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

def generate_activity_id() -> str:
    return str(uuid.uuid1())

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

def is_mqtt_available() -> bool:
    if MQTT_SERVICE and bool(MQTT_HOST) and bool(MQTT_PORT):
        return True
    else:
        return False
    
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

def read_token_code_file_data() -> dict:
    token = {}
    if os.path.isfile(OAUTH_CODE_TOKEN_FILE) and os.path.getsize(OAUTH_CODE_TOKEN_FILE):
        with open(OAUTH_CODE_TOKEN_FILE, 'r') as file:
            token = json.load(file)
    return token

def write_token_code_file_data(token_data: dict) -> None:
    token_object = json.dumps(token_data)
    if  os.path.exists('/config/'):
        with open(OAUTH_CODE_TOKEN_FILE, 'w') as file:
            if file.write(token_object):
                logger.info(f"Updating Token Code File")
                file.close()

def delete_token_code_file_data() -> None:
    if os.path.isfile(OAUTH_CODE_TOKEN_FILE) and os.path.getsize(OAUTH_CODE_TOKEN_FILE):
        os.remove(OAUTH_CODE_TOKEN_FILE)

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
            data=usage_data
        )

        if response.ok:
            return None

        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            logger.debug(f"Response: {response.text}")
            logger.debug(f"Response JSON: {response.json()}")

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
            headers=headers
        )


        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            #logger.debug(f"Response: {response.text}")
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
            headers=headers
        )


        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            #logger.debug(f"Response: {response.text}")
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
            json=new_options
        )


        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            logger.debug(f"Response JSON: {response.json()}")
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
            json=addon_options
        )

        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            logger.debug(f"Response JSON: {response.json()}")
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
            headers=headers
        )

        if response.status_code == 401:
            logger.error(f"Unable to authenticate with the API, permission denied")
        else:
            logger.debug(f"Response Status Code: {response.status_code}")
            #logger.debug(f"Response: {response.text}")
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

    if  _plan_detail is not None and \
        _plan_detail.get('downloadSpeed'):
            json_dict['attributes']['internet_download_speeds_Mbps'] = _plan_detail['downloadSpeed']
            json_dict['attributes']['internet_upload_speeds_Mbps'] = _plan_detail['uploadSpeed']

    if total_usage >= 0:
        usage_data = json_dict
        logger.info(f"Usage data retrieved and processed")
        logger.debug(f"Usage Data JSON: {json.dumps(usage_data)}")
    else:
        usage_data = None
    
    return usage_data


