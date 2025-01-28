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
        
        return self.OAUTH_TOKEN

    # https://oauth-token-decoder.b2.app.cloud.comcast.net/
    def oauth_update_tokens(self, token_response: dict) -> dict:

        token_response['encrypted_access_token'] = base64.b64encode(encrypt_message(token_response['access_token'])).decode()

        write_token_file_data(token_response, self.OAUTH_TOKEN_FILE)

        logger.debug(f"OAuth Access Token: {token_response['encrypted_access_token']}")
        
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

                        download_url = self.BILL_STATEMENT_URL + statement['statementUrl']
                        self.download_statement(download_url, download_filename, self.BILL_STATEMENT_PATH)
        else:
            logger.error(f"Bill Statement Error:")
            logger.error(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.error(f"Response: {response_content_b64}")

        #sleep(1)
        return 

    def get_usage_details_data(self) -> None:
        _retry_counter = 1
        self.usage_details = {}
        headers = {}
        headers.update({
            'authorization': f"{self.OAUTH_TOKEN['token_type']} {self.OAUTH_TOKEN['access_token']}",
        })
        headers.update(self.EXTRA_HEADERS)
        
        while(_retry_counter < 3):
            response = requests.get(self.USAGE_URL, 
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
                    len(response_json) > 0:
                        self.usage_details = response_json
                        logger.info(f"Updating Usage Details")
                        return self.usage_details

                else:
                    _retry_counter +=1
                    sleep(1 * pow(_retry_counter, _retry_counter))
            else:
                logger.error(f"Usage Details Error:")
                logger.error(f"Response Status Code: {response.status_code}")
                response_content_b64 = base64.b64encode(response.content).decode()
                logger.error(f"Response: {response_content_b64}")

        return self.usage_details

    def get_plan_details_data(self) -> None:
        self.plan_details = {}
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
        response_content_b64 = base64.b64encode(response.content).decode()
        logger.debug(f"Response: {response_content_b64}")
        #logger.debug(f"Response JSON: {response.json()}")


        if  response.ok and \
            'tier' in response_json and \
            len(response_json) > 0:
                self.plan_details = response_json['tier']
                logger.info(f"Updating Plan Details")
        else:
            logger.error(f"Usage Plan Error:")
            logger.error(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.error(f"Response: {response_content_b64}")

        #sleep(1)
        return self.plan_details

    def get_gateway_details_data(self) -> None:
        self.gateway_details = {}
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
        response_content_b64 = base64.b64encode(response.content).decode()
        logger.debug(f"Response: {response_content_b64}")
        #logger.debug(f"Response JSON: {response.json()}")


        if  response.ok and \
            'devices' in response_json and \
            len(response_json) > 0:
                self.gateway_details = response_json['devices'][0]
                self.gateway_details['macAddress'] = self.gateway_details['mac']
                logger.info(f"Updating Gateway Details")
        else:
            logger.error(f"Usage Gateway Error: ")
            logger.error(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.error(f"Response: {response_content_b64}")

        #sleep(1)
        return self.gateway_details

