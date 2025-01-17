import os
import uuid

from time import sleep
from xfinity_helper import *
from xfinity_mqtt import XfinityMqtt
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

    if addon_config_options and CLEAR_TOKEN:
        clear_token(addon_config_options)

    _oauth_token = read_token_file_data()

    if not _oauth_token: # Token File is empty
        if not REFRESH_TOKEN:
            #_oauth_token = asyncio.run(playwright_get_code())
            
            if XFINITY_CODE and XFINITY_CODE != XFINITY_CODE_PLACEHOLDER:
                 _token_code = read_token_code_file_data()
                 if _token_code:
                    _oauth_token = get_code_token(XFINITY_CODE, _token_code['activity_id'], _token_code['code_verifier'])
            else:
                CODE_VERIFIER = generate_code_verifier()
                CODE_CHALLENGE = generate_code_challenge(CODE_VERIFIER)
                STATE = generate_state()
                ACTIVITY_ID = str(uuid.uuid1())

                AUTH_URL = OAUTH_AUTHORIZE_URL + '?redirect_uri=xfinitydigitalhome%3A%2F%2Fauth&client_id=xfinity-android-application&response_type=code&prompt=select_account&state=' + STATE + '&scope=profile&code_challenge=' + CODE_CHALLENGE + '&code_challenge_method=S256&activity_id=' + ACTIVITY_ID + '&active_x1_account_count=true&rm_hint=true&partner_id=comcast&mso_partner_hint=true'
                _token_code = {
                    "activity_id": ACTIVITY_ID,
                    "code_verifier": CODE_VERIFIER,
                }
                write_token_code_file_data(_token_code)



                logger.error(
f"""
************************************************************************************

Using a browser, manually go to this url and login:
{AUTH_URL}

************************************************************************************
""")
                if is_hassio() and 'refresh_token' not in addon_config_options:

                    addon_config_options['xfinity_code'] = XFINITY_CODE_PLACEHOLDER
                    
                    if 'xfinity_username' in addon_config_options:
                         del addon_config_options['xfinity_username']
                    if 'xfinity_password' in addon_config_options:
                         del addon_config_options['xfinity_password']
                        

                    if update_addon_options(addon_config_options):
                        stop_addon()

                exit(exit_code.TOKEN_CODE.value)

        else:
            token_len = len(REFRESH_TOKEN)
            if len(REFRESH_TOKEN) == 644:
                _oauth_token['refresh_token'] = REFRESH_TOKEN
                _oauth_token = oauth_refresh_tokens(_oauth_token)

    if _oauth_token: # Got token from file or REFRESH_TOKEN
        if is_hassio() and 'refresh_token' not in addon_config_options:
            addon_config_options['refresh_token'] = _oauth_token['refresh_token']

            if 'xfinity_code' in addon_config_options: 
                del addon_config_options['xfinity_code']

            #logger.debug(json.dumps(addon_config_options))
            if update_addon_options(addon_config_options):
                    delete_token_code_file_data()
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
                # If token expires in 5 minutes (300 seconds)
                # refresh the token
                if get_current_unix_epoch() > _oauth_token['expires_at'] - 300:
                    _oauth_token = oauth_refresh_tokens(_oauth_token)
                
                _usage_details_data = get_usage_details_data(_oauth_token)

                _gateway_details_data = get_gateway_details_data(_oauth_token)

                _plan_details_data = get_plan_details_data(_oauth_token)

                # If we have the plan and usage data, success and lets process it
                if  _gateway_details_data and \
                    _usage_details_data:

                        _usage_data = process_usage_json(_usage_details_data, _plan_details_data)

                        if _usage_data:
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
                                    mqtt_client.mqtt_json_raw_usage = convert_raw_usage_to_website_format(_usage_details_data)

                                if mqtt_client.is_connected_mqtt():
                                    mqtt_client.publish_mqtt(_usage_data)
                                    #mqtt_client.disconnect_mqtt()

                            else:
                                logger.debug(f"Sensor API Url: {SENSOR_URL}")
                                update_ha_sensor(_usage_data)
                                update_sensor_file(_usage_data)

                # If POLLING_RATE is zero and exit with success code
                if BYPASS == 0 or POLLING_RATE == 0:
                    _continue = False
                    if is_mqtt_available():
                        mqtt_client.disconnect_mqtt()

                    exit(exit_code.SUCCESS.value)
                else:
                    logger.info(f"Sleeping for {int(POLLING_RATE)} seconds")
                    sleep(POLLING_RATE)


