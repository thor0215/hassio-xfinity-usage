import json
import os
from logging import WARNING
from requests import ConnectionError
from time import sleep
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential, before_sleep_log
from xfinity_globals import exit_code
from xfinity_helper import logger, SENSOR_URL
from xfinity_helper import is_hassio, get_addon_options, stop_addon, restart_addon, update_addon_options, clear_token, profile_cleanup
from xfinity_helper import update_ha_sensor_on_startup, update_ha_sensor, update_sensor_file
from xfinity_helper import process_usage_json
from xfinity_mqtt import XfinityMqtt, is_mqtt_available
from xfinity_token import XfinityOAuthToken
from xfinity_graphql import XfinityGraphQL
from xfinity_my_account import XfinityMyAccount

# Script polling rate
_BYPASS = int(os.environ.get('BYPASS',0))
_POLLING_RATE = float(os.environ.get('POLLING_RATE', 3600.0))

_CLEAR_TOKEN = json.loads(os.environ.get('CLEAR_TOKEN', 'false').lower()) # Convert CLEAR_TOKEN string into boolean

@retry(
    retry=retry_if_exception_type(ConnectionError),
    stop=stop_after_attempt(6),
    wait=wait_random_exponential(multiplier=3, min=3, max=90),
    before_sleep=before_sleep_log(logger, WARNING),
    reraise=True
)
def main():
    """
        Read token file or token from add-on config

        If no token
            run Playwright to get token
        else
            refresh token
            write token to file
            get usage data
            get plan data

        if mqtt
            connect to mqtt publish data
        else
            write usage to sensor file
        

    """
    addon_config_options = {}
    _usage_details_data = {}
    _plan_details_data = {}
    _gateway_details_data = {}


    if is_hassio():
        addon_config_options = get_addon_options()

    # Cleanup any old Playwright browser profiles
    profile_cleanup()

    if _CLEAR_TOKEN:
        clear_token(addon_config_options)


    xfinityToken = XfinityOAuthToken()

    if  xfinityToken.CLEAR_TOKEN:
        clear_token(addon_config_options)

    if  xfinityToken.OAUTH_CODE_FLOW:
        # Hitting step one of the OAuth code flow
        # if HASSIO clear any old username/password values
        # push code placeholder into code value
        # wait for step two

        if is_hassio():

            # Set code to placeholder
            addon_config_options['xfinity_code'] = xfinityToken.XFINITY_CODE_PLACEHOLDER
            
            # clear old username/password values
            if 'xfinity_username' in addon_config_options:
                    del addon_config_options['xfinity_username']
            if 'xfinity_password' in addon_config_options:
                    del addon_config_options['xfinity_password']

            update_addon_options(addon_config_options)

            # Stop the Addon to allow user to see url for code flow
            stop_addon()
        
        # Force exit if not HASSIO
        exit(exit_code.TOKEN_CODE.value)


    if xfinityToken.OAUTH_TOKEN: # Got token from file or REFRESH_TOKEN
        if is_hassio() and 'refresh_token' not in addon_config_options:
            addon_config_options['refresh_token'] = xfinityToken.OAUTH_TOKEN['refresh_token']

            if 'xfinity_code' in addon_config_options: 
                del addon_config_options['xfinity_code']

            #logger.debug(json.dumps(addon_config_options))
            update_addon_options(addon_config_options)
            xfinityToken.delete_token_code_file_data()
            restart_addon()

        if is_mqtt_available() :
            # Initialize and connect to MQTT server
            mqtt_client = XfinityMqtt()
        else:
            # if not MQTT, push sensor data into HA upon startup
            update_ha_sensor_on_startup()

        _continue = True
        while _continue:
            myAccount = XfinityMyAccount()
            xfinityGraphQL = XfinityGraphQL()
            
            _oauth_my_account = myAccount.oauth_refresh_tokens(xfinityToken.OAUTH_TOKEN)


            if 'access_token' in _oauth_my_account:
                #myAccount.get_bill_details_data()
                _usage_details_data = myAccount.get_usage_details_data()
                _plan_details_data = myAccount.get_plan_details_data()
                _gateway_details_data = myAccount.get_gateway_details_data()

            if not _usage_details_data:
                _usage_details_data = xfinityGraphQL.get_usage_details_data(xfinityToken.OAUTH_TOKEN)
            if not _plan_details_data:
                _plan_details_data = xfinityGraphQL.get_plan_details_data(xfinityToken.OAUTH_TOKEN)
            if not _gateway_details_data:
                _gateway_details_data = xfinityGraphQL.get_gateway_details_data(xfinityToken.OAUTH_TOKEN)

            # If we have the plan and usage data, success and lets process it
            if  _usage_details_data:

                    _usage_data = process_usage_json(_usage_details_data, _plan_details_data)

                    if _usage_data:
                        if is_mqtt_available() and _gateway_details_data:
                            # MQTT Home Assistant Device Config
                            mqtt_client.set_mqtt_device_details(_gateway_details_data)
                            
                            # MQTT Home Assistant Sensor State
                            mqtt_client.set_mqtt_state(_usage_data)

                            # MQTT Home Assistant Sensor Attributes
                            mqtt_client.set_mqtt_json_attributes(_usage_data)

                            # If RAW_USAGE enabled, set MQTT xfinity attributes
                            if mqtt_client.MQTT_RAW_USAGE:
                                mqtt_client.set_mqtt_raw_usage(_usage_details_data)

                            if mqtt_client.is_connected_mqtt():
                                mqtt_client.publish_mqtt(_usage_data)

                        else:
                            logger.debug(f"Sensor API Url: {SENSOR_URL}")
                            update_ha_sensor(_usage_data)
                            update_sensor_file(_usage_data)

            # If POLLING_RATE is zero and exit with success code
            if _BYPASS == 0 or _POLLING_RATE == 0:
                _continue = False
                if is_mqtt_available():
                    mqtt_client.disconnect_mqtt()

                exit(exit_code.SUCCESS.value)
            else:
                logger.info(f"Sleeping for {int(_POLLING_RATE)} seconds")
                sleep(_POLLING_RATE)


main()