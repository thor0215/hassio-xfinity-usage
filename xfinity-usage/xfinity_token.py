import json
import jwt
import os
import base64
import requests
from time import strftime, localtime
from jwt import PyJWKClient
from xfinity_globals import OAUTH_PROXY, OAUTH_CERT_VERIFY, REQUESTS_TIMEOUT
from xfinity_helper import logger, get_current_unix_epoch
from xfinity_helper import decrypt_message, encrypt_message
from xfinity_helper import read_token_file_data, write_token_file_data
from xfinity_helper import generate_activity_id, generate_code_challenge, generate_code_verifier, generate_state


class XfinityOAuthToken():
    def __init__(self):
        self.OAUTH_AUTHORIZE_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/oauth/authorize'
        #self.OAUTH_CODE_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-jwt/oauth/code'
        self.OAUTH_TOKEN_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/oauth/token'
        #self.OAUTH_JWKS_URL = 'https://xerxes-sub.xerxessecure.com/xerxes-ctrl/keys/jwks'
        self.CLIENT_SECRET = os.environ.get('XFINITY_ANDROID_APPLICATION_CLIENT_SECRET', decrypt_message(b'gAAAAABnhT0W7BB3IbVeR-vt_MGn7i1hiMtfIkpKjQ63al5vhomDpHJrEJ53_9xEBWp88SPXEYpW72r18vH4tcD-szw_EEPgkc5Dit1iusWLwr-3VA2_tlcdInSQBn0yMWFa0J4c5CqE'))
        self.REFRESH_TOKEN = os.environ.get('REFRESH_TOKEN', None)
        self.XFINITY_CODE = os.environ.get('XFINITY_CODE', None)
        self.XFINITY_CODE_PLACEHOLDER = 'Example Code 251774815a2140a5abf64fa740dabf0c'

        self.OAUTH_TOKEN_FILE = '/config/.token.json'
        self.OAUTH_CODE_TOKEN_FILE = '/config/.code.json'


        self.OAUTH_CODE_FLOW = False
        self.OAUTH_TOKEN = {}
        self.OAUTH_USER_AGENT = 'Dalvik/2.1.0 (Linux; U; Android 14; SM-G991B Build/G991BXXUEGXJE)'

        self.OAUTH_TOKEN_EXTRA_HEADERS = {
            'Content-Type':             'application/x-www-form-urlencoded',
            'Accept':                   'application/json',
            'User-Agent':               self.OAUTH_USER_AGENT,
            'Accept-Encoding':          'gzip'
        }
        self.OAUTH_TOKEN_DATA = {
            'active_x1_account_count':  'true',
            'partner_id':               'comcast',
            'mso_partner_hint':         'true',
            'scope':                    'profile',
            'rm_hint':                  'true',
            'client_id':                'xfinity-android-application'
        }

        self.OAUTH_TOKEN = read_token_file_data(self.OAUTH_TOKEN_FILE)

        if self.REFRESH_TOKEN:
            # REFRESH_TOKEN is set

            if not self.OAUTH_TOKEN: 
                # Token File is empty use REFRESH_TOKEN
                self.oauth_refresh_tokens({'refresh_token': self.REFRESH_TOKEN})

            else: 
                # Read Token from file

                if self.OAUTH_TOKEN.get('refresh_token', '') != self.REFRESH_TOKEN:
                    # If file token does not match REFRESH_TOKEN

                    # Refresh token using REFRESH_TOKEN
                    self.oauth_refresh_tokens({'refresh_token': self.REFRESH_TOKEN})
                else:
                    # File token and REFRESH_TOKEN match

                    # If file token expires in 5 minutes (300 seconds)
                    # refresh the token
                    if  'expires_at' in self.OAUTH_TOKEN and \
                        get_current_unix_epoch() > self.OAUTH_TOKEN['expires_at'] - 300:
                            self.OAUTH_TOKEN = self.oauth_refresh_tokens(self.OAUTH_TOKEN)
        elif self.OAUTH_TOKEN:
            # Read Token from file and REFRESH_TOKEN is not set

            # If file token expires in 5 minutes (300 seconds)
            # refresh the token
            if  'expires_at' in self.OAUTH_TOKEN and \
                get_current_unix_epoch() > self.OAUTH_TOKEN['expires_at'] - 300:
                    self.OAUTH_TOKEN = self.oauth_refresh_tokens(self.OAUTH_TOKEN)

        else:
            # Token File is empty but REFRESH_TOKEN is not set

            if self.XFINITY_CODE and self.XFINITY_CODE != self.XFINITY_CODE_PLACEHOLDER:
                # OAuth Code Flow step two
                # If OAuth Code is provided and the code is not set to the placeholder
             
                # Read the saved code file to get activity_id and code_verifier
                _token_code = self.read_token_code_file_data()

                if _token_code:
                    self.OAUTH_TOKEN = self.get_code_token(self.XFINITY_CODE, _token_code['activity_id'], _token_code['code_verifier'])
            else:
                # OAuth Code is not provided, print Authentication URL
                # Step one of OAuth Code Flow
            
                CODE_VERIFIER = generate_code_verifier()
                CODE_CHALLENGE = generate_code_challenge(CODE_VERIFIER)
                STATE = generate_state()
                ACTIVITY_ID = generate_activity_id()

                AUTH_URL = self.OAUTH_AUTHORIZE_URL + '?redirect_uri=xfinitydigitalhome%3A%2F%2Fauth&client_id=xfinity-android-application&response_type=code&prompt=select_account&state=' + STATE + '&scope=profile&code_challenge=' + CODE_CHALLENGE + '&code_challenge_method=S256&activity_id=' + ACTIVITY_ID + '&active_x1_account_count=true&rm_hint=true&partner_id=comcast&mso_partner_hint=true'
                _token_code = {
                    "activity_id": ACTIVITY_ID,
                    "code_verifier": CODE_VERIFIER,
                }
                self.write_token_code_file_data(_token_code)

                logger.error(
f"""
************************************************************************************

Using a browser, manually go to this url and login:
{AUTH_URL}

************************************************************************************
""")

                self.OAUTH_CODE_FLOW = True


    def read_token_code_file_data(self) -> dict:
        token = {}
        if os.path.isfile(self.OAUTH_CODE_TOKEN_FILE) and os.path.getsize(self.OAUTH_CODE_TOKEN_FILE):
            with open(self.OAUTH_CODE_TOKEN_FILE, 'r') as file:
                token = json.load(file)
        return token

    def write_token_code_file_data(self, token_data: dict) -> None:
        token_object = json.dumps(token_data)
        if  os.path.exists('/config/'):
            with open(self.OAUTH_CODE_TOKEN_FILE, 'w') as file:
                if file.write(token_object):
                    logger.info(f"Updating Token Code File")
                    file.close()

    def delete_token_code_file_data(self) -> None:
        if os.path.isfile(self.OAUTH_CODE_TOKEN_FILE) and os.path.getsize(self.OAUTH_CODE_TOKEN_FILE):
            os.remove(self.OAUTH_CODE_TOKEN_FILE)


    def get_code_token(self, _CODE, _ACTIVITY_ID, _CODE_VERIFIER) -> None:
        self.OAUTH_TOKEN = {}
        data = {
            'code': _CODE,
            'grant_type': 'authorization_code',
            'activity_id': _ACTIVITY_ID,
            'redirect_uri': 'xfinitydigitalhome%3A%2F%2Fauth',
            'client_secret': self.CLIENT_SECRET,
            'code_verifier': _CODE_VERIFIER
        }
        data.update(self.OAUTH_TOKEN_DATA)

        response = requests.post(self.OAUTH_TOKEN_URL, 
                                headers=self.OAUTH_TOKEN_EXTRA_HEADERS, 
                                data=data, 
                                proxies=OAUTH_PROXY,
                                verify=OAUTH_CERT_VERIFY,
                                timeout=REQUESTS_TIMEOUT)
        
        response_json = response.json()
        logger.debug(f"Response Status Code: {response.status_code}")
        response_content_b64 = base64.b64encode(response.content).decode()
        logger.debug(f"Response: {response_content_b64}")
        #logger.debug(f"Response JSON: {response.json()}")

        if response.ok:
            if  'error' not in response_json:
                    logger.debug(f"Updating code: {_CODE}")
                    logger.debug(f"         code_verifier: {_CODE_VERIFIER}")
                    logger.debug(f"         activity_id: {_ACTIVITY_ID}")
                    self.OAUTH_TOKEN = self.oauth_update_tokens(response_json)
        else:
            logger.error(f"Updating code: {_CODE}")
            logger.error(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.error(f"Response: {response_content_b64}")
            raise AssertionError()

        return self.OAUTH_TOKEN

    def oauth_refresh_tokens(self, _TOKEN) -> None:
        self.OAUTH_TOKEN = {}
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': _TOKEN['refresh_token'],
            'client_secret': self.CLIENT_SECRET
        }
        data.update(self.OAUTH_TOKEN_DATA)

        response = requests.post(self.OAUTH_TOKEN_URL, 
                            headers=self.OAUTH_TOKEN_EXTRA_HEADERS, 
                            data=data, 
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY,
                            timeout=REQUESTS_TIMEOUT)
        
        response_json = response.json()
        logger.debug(f"Response Status Code: {response.status_code}")
        response_content_b64 = base64.b64encode(response.content).decode()
        logger.debug(f"Response: {response_content_b64}")

        if response.ok:   
            if  'error' not in response_json and 'access_token' in response_json:
                    logger.info(f"Updating OAuth Token")
                    self.OAUTH_TOKEN = self.oauth_update_tokens(response_json)
        else:
            logger.error("Updating OAuth Token")
            logger.error(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.error(f"Response: {response_content_b64}")
            raise AssertionError()
        
        return self.OAUTH_TOKEN


    def oauth_update_tokens(self, token_response) -> None:
        token_header = jwt.get_unverified_header(token_response['id_token'])

        if token_header['jku'] is not None and token_header['alg'] is not None:
            jwks_client = PyJWKClient(token_header['jku'])
            signing_key = jwks_client.get_signing_key_from_jwt(token_response['id_token'])
            algorithm = token_header['alg']
            jwt_token = jwt.decode(token_response['id_token'], 
                                signing_key, 
                                algorithms=[algorithm], 
                                options={"verify_signature": True,
                                            "require": ['exp','iss','aud','cust_guid'],
                                            "verify_aud": True,
                                            "verify_iss": True,
                                            "verify_exp": True
                                            },
                                audience='xfinity-android-application',
                                issuer='xerxeslite-prod')
        else:
            jwt_token = jwt.decode(token_response['id_token'], options={"verify_signature": False})

        token_response['expires_at'] = jwt_token['exp']
        token_response['customer_guid'] = jwt_token['cust_guid']
        token_response['encrypted_refresh_token'] = base64.b64encode(encrypt_message(token_response['refresh_token'])).decode()

        write_token_file_data(token_response,self.OAUTH_TOKEN_FILE)

        _expire_formatted_time = strftime("%Y-%m-%d %H:%M:%S", localtime(int(token_response['expires_at'])))

        logger.debug(f"OAuth Access Token: {token_response['access_token']}")
        logger.debug(f"OAuth Id Token: {token_response['id_token']}")
        logger.info(f"OAuth Refresh Token: {token_response['encrypted_refresh_token']}")
        logger.debug(f"OAuth Activity Id: {token_response['activity_id']}")
        logger.info(f"OAuth Expires At: {token_response['expires_at']} ({_expire_formatted_time})")
        logger.debug(f"Xfinity Customer Guid: {token_response['customer_guid']}")

        return token_response


