import base64
import os
import requests
from datetime import datetime
from time import sleep
from .xfinity_globals import OAUTH_PROXY, OAUTH_CERT_VERIFY, REQUESTS_TIMEOUT
from .xfinity_helper import logger, encrypt_message, decrypt_message, write_token_file_data, handle_requests_exception

_BILL_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/bill'
_BILL_STATEMENT_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/'
_DEVICE_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/devices'
_PLAN_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/services/internet/plan'
_USAGE_URL = 'https://csp-pci-prod.codebig2.net/selfhelp/account/me/services/internet/usage?filter=internet'
_OAUTH_TOKEN_FILE = '/config/.myaccount.json'
_BILL_STATEMENT_PATH = '/config'

_OAUTH_TOKEN_URL = 'https://oauth.xfinity.com/oauth/token'

_CLIENT_SECRET = os.environ.get('MY_ACCOUNT_MOBILE_CLIENT_SECRET', decrypt_message(b'gAAAAABnj94zACvGaKtNLckXDwvdiE3s8QI6BZncDU4ONwVCcH1wPG76zZg_L-X5yvv7bS4EULqVtfbZzKZVEopuNT2m9fO6K31e1C_3qh9n9kU3-IlhaPFXu4EF9ki31gyp-sk_lNfa'))

_OAUTH_TOKEN_EXTRA_HEADERS = {
    'Content-Type':             'application/x-www-form-urlencoded',
    'Accept':                   'application/json',
    'User-Agent':               'okhttp/4.12.0',
    'Accept-Encoding':          'gzip'
}
_EXTRA_HEADERS = {
    'user-agent':              'Digital Home / Samsung SM-G991B / Android 14',
    'client':                  'dotcom_xfinity',
    'client-detail':           'MOBILE;Samsung;SM-G991B;Android 14;v5.38.0',
    'accept-language':         'en-US'
}

class XfinityMyAccount():
    def __init__(self):
        self.OAUTH_TOKEN = {}
        self.usage_details = {}
        self.plan_details = {}
        self.gateway_details = {}

    def handle_requests_exception(self, e, response=None):
        handle_requests_exception(e, response)

    def oauth_refresh_tokens(self, _TOKEN: dict ) -> dict:
        self.OAUTH_TOKEN = {}
        data = {
            'client_id': 'my-account-mobile',
            'client_secret': _CLIENT_SECRET,
            'grant_type': 'urn:comcast:oauth:grant-type:syndicated-id-token',
            'assertion': _TOKEN['id_token']
        }

        try:
            response = requests.post(_OAUTH_TOKEN_URL, 
                                headers=_OAUTH_TOKEN_EXTRA_HEADERS, 
                                data=data, 
                                proxies=OAUTH_PROXY,
                                verify=OAUTH_CERT_VERIFY)
            
            response_json = response.json()
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")

            if response.ok:   
                if  'error' not in response_json and 'access_token' in response_json:
                        logger.info(f"Updating My Account OAuth Token")
                        self.OAUTH_TOKEN = self.oauth_update_tokens(response_json)
            else:
                logger.error("Updating My Account OAuth Token")
                logger.error(f"Response Status Code: {response.status_code}")
                response_content_b64 = base64.b64encode(response.content).decode()
                logger.error(f"Response: {response_content_b64}")
                raise AssertionError()
        
        except Exception as e:
            if response is None:
                self.handle_requests_exception(e)
            else:
                self.handle_requests_exception(e, response)
        finally:
            return self.OAUTH_TOKEN

    # https://oauth-token-decoder.b2.app.cloud.comcast.net/
    def oauth_update_tokens(self, token_response: dict) -> dict:

        token_response['encrypted_access_token'] = base64.b64encode(encrypt_message(token_response['access_token'])).decode()

        write_token_file_data(token_response, _OAUTH_TOKEN_FILE)

        logger.debug(f"OAuth Access Token: {token_response['encrypted_access_token']}")
        
        return token_response

    def download_statement(self, url, filename, path):
        fullpath = path + '/' + filename

        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
            'accept': 'application/pdf;v=2'
        })
        headers.update(_EXTRA_HEADERS)

        try:
            response = requests.get(url,
                                    headers=headers,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)

            with open(fullpath, 'wb') as out_file:
                out_file.write(response.content)

            if os.path.getsize(fullpath):
                logger.info(f'Xfinity Statement file was saved successfully as {fullpath}')
        except Exception as e:
            if response is None:
                self.handle_requests_exception(e)
            else:
                self.handle_requests_exception(e, response)
        
            
    def get_bill_details_data(self) -> None:
        datetime_now_str = datetime.now().strftime("%Y-%m-%dT00:00:00.000Z")
        datetime_now = datetime.now()

        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(_EXTRA_HEADERS)
        
        try:
            response = requests.get(_BILL_URL, 
                                    headers=headers,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)

            response_json = response.json()
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")


            if  response.ok and \
                'statements' in response_json:
                    statement = response_json['statements'][0]
                    statement_date = datetime.strptime(statement['statementDate'], "%Y-%m-%dT%H:%M:%S.%fZ")
                    download_filename = statement_date.strftime("Xfinity - Statement - %Y-%m-%d.pdf")

                    if  datetime.now().year == statement_date.year and \
                        datetime.now().month == statement_date.month:
                            logger.info(f"Attempting to download latest Bill")

                            download_url = _BILL_STATEMENT_URL + statement['statementUrl']
                            self.download_statement(download_url, download_filename, _BILL_STATEMENT_PATH)
            else:
                logger.error(f"Bill Statement Error:")
                logger.error(f"Response Status Code: {response.status_code}")
                response_content_b64 = base64.b64encode(response.content).decode()
                logger.error(f"Response: {response_content_b64}")
        except Exception as e:
            if response is None:
                self.handle_requests_exception(e)
            else:
                self.handle_requests_exception(e, response)
        finally:
            #sleep(1)
            return 

    def get_usage_details_data(self) -> dict:
        _retry_counter = 1
        self.usage_details = {}
        response = None
        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(_EXTRA_HEADERS)
        
        while(_retry_counter <= 3):
            try:
                response = requests.get(_USAGE_URL, 
                                    headers=headers,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)

                response_json = response.json()
                logger.debug(f"Response Status Code: {response.status_code}")
                response_content_b64 = base64.b64encode(response.content).decode()
                logger.debug(f"Response: {response_content_b64}")
                #logger.debug(f"Response JSON: {response.json()}")

                if  response.ok:
                    if  'usageMonths' in response_json and \
                        len(response_json['usageMonths']) > 0:
                            self.usage_details = response_json
                            logger.info(f"Updating Usage Details")
                            return self.usage_details

                    else:
                        sleep(1 * pow(_retry_counter, _retry_counter))
                else:
                    logger.error(f"Usage Details Error:")
                    logger.error(f"Response Status Code: {response.status_code}")
                    response_content_b64 = base64.b64encode(response.content).decode()
                    logger.error(f"Response: {response_content_b64}")
                    if  response.status_code == 404 and \
                        'message' in response_json:
                        if response_json['message'] == 'Plan does not support the usage meter feature.':
                            raise AssertionError('Unlimited plan does not support the usage meter feature.')
            except Exception as e:
                if response is None:
                    self.handle_requests_exception(e)
                else:
                    self.handle_requests_exception(e, response)
            finally:
                _retry_counter +=1
            
        return self.usage_details

    def get_plan_details_data(self) -> dict:
        self.plan_details = {}
        response = None
        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(_EXTRA_HEADERS)
        
        try:
            response = requests.get(_PLAN_URL, 
                                    headers=headers,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)

            response_json = response.json()
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")


            if  response.ok and \
                'tier' in response_json and \
                len(response_json['tier']) > 0:
                    self.plan_details = response_json['tier']
                    logger.info(f"Updating Plan Details")
            else:
                logger.error(f"Usage Plan Error:")
                logger.error(f"Response Status Code: {response.status_code}")
                response_content_b64 = base64.b64encode(response.content).decode()
                logger.error(f"Response: {response_content_b64}")

        except Exception as e:
            if response is None:
                self.handle_requests_exception(e)
            else:
                self.handle_requests_exception(e, response)
        finally:
            #sleep(1)
            return self.plan_details

    def get_gateway_details_data(self) -> dict:
        self.gateway_details = {}
        response = None
        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(_EXTRA_HEADERS)
        
        try:
            response = requests.get(_DEVICE_URL, 
                                    headers=headers,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)

            response_json = response.json()
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")


            if  response.ok and \
                'devices' in response_json and \
                len(response_json['devices']) > 0:
                    self.gateway_details = response_json['devices'][0]
                    self.gateway_details['macAddress'] = self.gateway_details['mac']
                    logger.info(f"Updating Gateway Details")
            else:
                logger.error(f"Usage Gateway Error: ")
                logger.error(f"Response Status Code: {response.status_code}")
                response_content_b64 = base64.b64encode(response.content).decode()
                logger.error(f"Response: {response_content_b64}")

        except Exception as e:
            if response is None:
                self.handle_requests_exception(e)
            else:
                self.handle_requests_exception(e, response)
        finally:
            #sleep(1)
            return self.gateway_details

