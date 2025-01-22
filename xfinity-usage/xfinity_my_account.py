import json
from datetime import datetime
from time import sleep
from xfinity_helper import *


class XfinityMyAccount():
    def __init__(self):
        self.BILL_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/bill'
        self.BILL_STATEMENT_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/'
        self.DEVICE_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/devices'
        self.PLAN_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/services/internet/plan'
        self.USAGE_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/services/internet/usage?filter=internet'
        self.OAUTH_TOKEN_FILE = '/config/.myaccount.json'
        self.OAUTH_TOKEN = {}
        self.BILL_STATEMENT_PATH = '/config'

        self.OAUTH_TOKEN_URL = 'https://oauth.xfinity.com/oauth/token'
        self.OAUTH_USER_AGENT = 'okhttp/4.12.0'

        self.OAUTH_TOKEN_EXTRA_HEADERS = {
            'Content-Type':             'application/x-www-form-urlencoded',
            'Accept':                   'application/json',
            'User-Agent':               self.OAUTH_USER_AGENT,
            'Accept-Encoding':          'gzip'
        }

        self.EXTRA_HEADERS = {
            'user-agent':              'Digital Home / Samsung SM-G991B / Android 14',
            'client':                  'dotcom_xfinity',
            'client-detail':           'MOBILE;Samsung;SM-G991B;Android 14;v5.38.0',
            'accept-language':         'en-US'
        }
        self.CLIENT_SECRET = os.environ.get('MY_ACCOUNT_MOBILE_CLIENT_SECRET', decrypt_message(b'gAAAAABnj94zACvGaKtNLckXDwvdiE3s8QI6BZncDU4ONwVCcH1wPG76zZg_L-X5yvv7bS4EULqVtfbZzKZVEopuNT2m9fO6K31e1C_3qh9n9kU3-IlhaPFXu4EF9ki31gyp-sk_lNfa'))


    def process_usage_json(self, _raw_usage_data: dict, _raw_plan_data: dict) -> bool:
        _plan_detail = _raw_plan_data

        _cur_month = _raw_usage_data['usageMonths'][-1]
        # record current month's information
        # convert key names to 'snake_case'
        attributes = {}
        for k, v in _cur_month.items():
            attributes[camelTo_snake_case(k)] = v

        if _cur_month['policy'] == 'limited':
            # extend data for limited accounts
            #attributes['accountNumber'] = _raw_usage_data['accountNumber']
            attributes['courtesy_used'] = _raw_usage_data['courtesyUsed']
            attributes['courtesy_remaining'] = _raw_usage_data['courtesyRemaining']
            attributes['courtesy_allowed'] = _raw_usage_data['courtesyAllowed']
            attributes['courtesy_months'] = _raw_usage_data['courtesyMonths']
            attributes['in_paid_overage'] = _raw_usage_data['inPaidOverage']
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
                json_dict['attributes']['internet_download_speeds_Mbps'] = int(_plan_detail['downloadSpeed'])
                json_dict['attributes']['internet_upload_speeds_Mbps'] = int(_plan_detail['uploadSpeed'])

        if total_usage >= 0:
            usage_data = json_dict
            logger.info(f"Usage data retrieved and processed")
            logger.debug(f"Usage Data JSON: {json.dumps(usage_data)}")
        else:
            usage_data = None
        
        return usage_data


    def oauth_refresh_tokens(self, _TOKEN: dict ) -> dict:
        self.OAUTH_TOKEN = {}
        data = {
            'client_id': 'my-account-mobile',
            'client_secret': self.CLIENT_SECRET,
            'grant_type': 'urn:comcast:oauth:grant-type:syndicated-id-token',
            'assertion': _TOKEN['id_token']
        }

        response = requests.post(self.OAUTH_TOKEN_URL, 
                            headers=self.OAUTH_TOKEN_EXTRA_HEADERS, 
                            data=data, 
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY)
        
        response_json = response.json()
        logger.debug(f"Response Status Code: {response.status_code}")
        logger.debug(f"Response: {response.text}")
        logger.debug(f"Response JSON: {response.json()}")

        if response.ok:   
            if  'error' not in response_json and 'access_token' in response_json:
                    logger.info(f"Updating My Account Mobile  Oauth Token")
                    self.OAUTH_TOKEN = self.oauth_update_tokens(response_json)
            logger.debug(f"Updating Oauth Token Details {json.dumps(response_json)}")
        else:
            raise AssertionError(f"Oauth Token Error: {json.dumps(response_json)}")
        
        return self.OAUTH_TOKEN

    # https://oauth-token-decoder.b2.app.cloud.comcast.net/
    def oauth_update_tokens(self, token_response: dict) -> dict:

        write_token_file_data(token_response, self.OAUTH_TOKEN_FILE)

        logger.info(f"Oauth Access Token: {token_response['access_token']}")
        
        return token_response

    def download_statement(self, url, filename, path):
        fullpath = path + '/' + filename

        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
            'accept': 'application/pdf;v=2'
        })
        headers.update(self.EXTRA_HEADERS)

        response = requests.get(url,
                                headers=headers,
                                proxies=OAUTH_PROXY,
                                verify=OAUTH_CERT_VERIFY,
                                timeout=REQUESTS_TIMEOUT)

        with open(fullpath, 'wb') as out_file:
            out_file.write(response.content)

        if os.path.getsize(fullpath):
            logger.info(f'Xfinity Statement file was saved successfully as {fullpath}')

    def get_bill_details_data(self) -> None:
        datetime_now_str = datetime.now().strftime("%Y-%m-%dT00:00:00.000Z")
        datetime_now = datetime.now()

        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(self.EXTRA_HEADERS)
        
        response = requests.get(self.BILL_URL, 
                                headers=headers,
                                proxies=OAUTH_PROXY,
                                verify=OAUTH_CERT_VERIFY,
                                timeout=REQUESTS_TIMEOUT)

        response_json = response.json()
        logger.debug(f"Response Status Code: {response.status_code}")
        logger.debug(f"Response: {response.text}")
        logger.debug(f"Response JSON: {response.json()}")


        if  response.ok and \
            'statements' in response_json:
                statement = response_json['statements'][0]
                statement_date = datetime.strptime(statement['statementDate'], "%Y-%m-%dT%H:%M:%S.%fZ")
                download_filename = statement_date.strftime("Xfinity - Statement - %Y-%m-%d.pdf")

                if  datetime.now().year == statement_date.year and \
                    datetime.now().month == statement_date.month:
                        logger.info(f"Attempting to download latest Bill")

                        download_url = self.BILL_STATEMENT_URL + statement['statementUrl']
                        self.download_statement(download_url, download_filename, self.BILL_STATEMENT_PATH)
                     

                logger.debug(f"Updating Device Details {json.dumps(response_json)}")
        else:
            #raise AssertionError(f"GraphQL Gateway Error: {json.dumps(response_json)}")
            logger.error(f"Bill Statement Error: {json.dumps(response_json)}")

        #sleep(1)
        return 

    def get_usage_details_data(self) -> None:
        _usage_details = {}
        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(self.EXTRA_HEADERS)
        
        response = requests.get(self.USAGE_URL, 
                                headers=headers,
                                proxies=OAUTH_PROXY,
                                verify=OAUTH_CERT_VERIFY,
                                timeout=REQUESTS_TIMEOUT)

        response_json = response.json()
        logger.debug(f"Response Status Code: {response.status_code}")
        logger.debug(f"Response: {response.text}")
        logger.debug(f"Response JSON: {response.json()}")


        if  response.ok and \
            'usageMonths' in response_json and \
            len(response_json) > 0:
                _usage_details = response_json
                logger.info(f"Updating Usage Details")
                logger.debug(f"Updating Usage Details {json.dumps(response_json)}")
        else:
            logger.error(f"Usage Details Error: {json.dumps(response_json)}")

        #sleep(1)
        return _usage_details

    def get_plan_details_data(self) -> None:
        _plan_details = {}
        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(self.EXTRA_HEADERS)
        
        response = requests.get(self.PLAN_URL, 
                                headers=headers,
                                proxies=OAUTH_PROXY,
                                verify=OAUTH_CERT_VERIFY,
                                timeout=REQUESTS_TIMEOUT)

        response_json = response.json()
        logger.debug(f"Response Status Code: {response.status_code}")
        logger.debug(f"Response: {response.text}")
        logger.debug(f"Response JSON: {response.json()}")


        if  response.ok and \
            'tier' in response_json and \
            len(response_json) > 0:
                _plan_details = response_json['tier']
                logger.info(f"Updating Plan Details")
                logger.debug(f"Updating Plan Details {json.dumps(response_json)}")
        else:
            logger.error(f"Usage Plan Error: {json.dumps(response_json)}")

        #sleep(1)
        return _plan_details

    def get_gateway_details_data(self) -> None:
        _gateway_details = {}
        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(self.EXTRA_HEADERS)
        
        response = requests.get(self.DEVICE_URL, 
                                headers=headers,
                                proxies=OAUTH_PROXY,
                                verify=OAUTH_CERT_VERIFY,
                                timeout=REQUESTS_TIMEOUT)

        response_json = response.json()
        logger.debug(f"Response Status Code: {response.status_code}")
        logger.debug(f"Response: {response.text}")
        logger.debug(f"Response JSON: {response.json()}")


        if  response.ok and \
            'devices' in response_json and \
            len(response_json) > 0:
                _gateway_details = response_json['devices'][0]
                _gateway_details['macAddress'] = _gateway_details['mac']
                logger.info(f"Updating Gateway Details")
                logger.debug(f"Updating Gateway Details {json.dumps(response_json)}")
        else:
            logger.error(f"Usage Gateway Error: {json.dumps(response_json)}")

        #sleep(1)
        return _gateway_details

