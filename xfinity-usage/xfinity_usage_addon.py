import asyncio
import os
import time

from xfinity_helper import *
from xfinity_mqtt import XfinityMqtt
from xfinity_web_auth import playwright_get_code
from xfinity_token import *
from xfinity_graphql import *


if __name__ == '__main__':
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
    addon_config_options = get_addon_options()

    # Cleanup any old Playwright browser profiles
    profile_cleanup()

    _oauth_token = read_token_file_data()

    if not _oauth_token: # Token File is empty
        if not REFRESH_TOKEN:
            try:
                _oauth_token = asyncio.run(playwright_get_code())
                
                # Only allow one run of the script
                if DEBUG_SUPPORT: exit(exit_code.DEBUG_SUPPORT.value)

            except BaseException as e:

                if type(e) == SystemExit:
                    exit(e.code)
                else: 
                    exit(exit_code.MAIN_EXCEPTION.value)

        else:
            token_len = len(REFRESH_TOKEN)
            if len(REFRESH_TOKEN) == 644:
                _oauth_token['refresh_token'] = REFRESH_TOKEN
                _oauth_token = oauth_refresh_tokens(_oauth_token)

    if _oauth_token: # Got token from file or XFINITY_REFRESH_TOKEN
        if  bool(BASHIO_SUPERVISOR_API) and \
            bool(BASHIO_SUPERVISOR_TOKEN) and \
            not addon_config_options.get('refresh_token'):
                addon_config_options['refresh_token'] = _oauth_token['refresh_token']
                logger.info(json.dumps(addon_config_options))
                if  validate_addon_options(addon_config_options) and \
                    update_addon_options(addon_config_options):
                        restart_addon()

        if is_mqtt_available() :
            # Initialize and connect to MQTT server
            mqtt_client = XfinityMqtt()
        else:
            if os.path.isfile(SENSOR_BACKUP) and os.path.getsize(SENSOR_BACKUP):
                with open(SENSOR_BACKUP, 'r') as file:
                    usage_data = file.read()
                    update_ha_sensor(usage_data)

        _continue = True
        while _continue:
            try:   
                # If token expires in 5 minutes (300 seconds)
                # refresh the token
                if get_current_unix_epoch() > _oauth_token['expires_at'] - 300:
                    _oauth_token = oauth_refresh_tokens(_oauth_token)

                _gateway_details_data = get_gateway_details_data(_oauth_token)

                _internet_details_data = get_internet_details_data(_oauth_token)

                # If we have the plan and usage data, success and lets process it
                if  _gateway_details_data is not None and \
                    _internet_details_data.get('plan', None) is not None and \
                    _internet_details_data.get('usage', None) is not None:

                        _usage_data = process_usage_json(_internet_details_data)

                        if _usage_data is not None:
                            if is_mqtt_available():
                                """
                                "deviceDetails": {
                                    "mac": "44:A5:6E:B9:E3:60",
                                    "serialNumber": "44A56EB9E360",
                                    "model": "cm1000v2",
                                    "make": "NETGEAR",
                                    "platform": "CM",
                                    "type": "Cable Modem",
                                    "hasCableModem": true,
                                    "lineOfBusiness": "INTERNET"
                                    }
                                """
                                # MQTT Home Assistant Device Config
                                mqtt_client.mqtt_device_config_dict['device']['identifiers'] = _gateway_details_data.get('macAddress', '00:00:00:00:00')
                                mqtt_client.mqtt_device_config_dict['device']['model'] = _gateway_details_data.get('model', 'xFinity') or 'unknown'
                                mqtt_client.mqtt_device_config_dict['device']['manufacturer'] = _gateway_details_data.get('make', 'xFi Gateway') or 'unknown'
                                mqtt_client.mqtt_device_config_dict['device']['name'] = "Xfinity"
                                
                                # MQTT Home Assistant Sensor State
                                mqtt_client.mqtt_state = _usage_data['state']

                                # MQTT Home Assistant Sensor Attributes
                                mqtt_client.mqtt_json_attributes_dict = _usage_data['attributes']

                                # If RAW_USAGE enabled, set MQTT xfinity attributes
                                if MQTT_RAW_USAGE:
                                    mqtt_client.mqtt_json_raw_usage = convert_raw_usage_to_website_format(_internet_details_data.get('usage'))

                                if mqtt_client.is_connected_mqtt():
                                    mqtt_client.publish_mqtt(_usage_data)
                                    #mqtt_client.disconnect_mqtt()

                            else:
                                logger.debug(f"Sensor API Url: {SENSOR_URL}")
                                update_ha_sensor(_usage_data)
                                update_sensor_file(_usage_data)

                # Only allow one run of the script
                if DEBUG_SUPPORT: exit(exit_code.DEBUG_SUPPORT.value)

                # If POLLING_RATE is zero and exit with success code
                if BYPASS == 0 or POLLING_RATE == 0:
                    _continue = False
                    exit(exit_code.SUCCESS.value)
                else:
                    logger.info(f"Sleeping for {int(POLLING_RATE)} seconds")
                    time.sleep(POLLING_RATE)


            except BaseException as e:
                if is_mqtt_available():
                    mqtt_client.disconnect_mqtt()

                if type(e) == SystemExit:
                    exit(e.code)
                else: 
                    exit(exit_code.MAIN_EXCEPTION.value)