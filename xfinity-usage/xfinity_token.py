import json
import jwt
import requests
from time import strftime, localtime
from jwt import PyJWKClient
from xfinity_helper import *

class XfinityOauthToken():
    def __init__(self):
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


    def get_code_token(self, _CODE, _ACTIVITY_ID, _CODE_VERIFIER) -> None:
        self.OAUTH_TOKEN = {}
        data = {
            'code': _CODE,
            'grant_type': 'authorization_code',
            'activity_id': _ACTIVITY_ID,
            'redirect_uri': 'xfinitydigitalhome%3A%2F%2Fauth',
            'client_secret': XFINITY_ANDROID_APPLICATION_CLIENT_SECRET,
            'code_verifier': _CODE_VERIFIER
        }
        data.update(self.OAUTH_TOKEN_DATA)

        response = requests.post(OAUTH_TOKEN_URL, 
                                headers=self.OAUTH_TOKEN_EXTRA_HEADERS, 
                                data=data, 
                                proxies=OAUTH_PROXY,
                                verify=OAUTH_CERT_VERIFY)
        
        response_json = response.json()
        logger.debug(f"Response Status Code: {response.status_code}")
        logger.debug(f"Response: {response.text}")
        logger.debug(f"Response JSON: {response.json()}")

        if response.ok:
            if  'error' not in response_json:
                    logger.debug(f"Updating code: {_CODE}")
                    logger.debug(f"         code_verifier: {_CODE_VERIFIER}")
                    logger.debug(f"         activity_id: {_ACTIVITY_ID}")
                    self.OAUTH_TOKEN = self.oauth_update_tokens(response_json)
            logger.debug(f"Updating code Details {json.dumps(response_json)}")
        else:
            raise AssertionError(f"Oauth Code Token Error: {json.dumps(response_json)}")

        return self.OAUTH_TOKEN

    def oauth_refresh_tokens(self, _TOKEN) -> None:
        self.OAUTH_TOKEN = {}
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': _TOKEN['refresh_token'],
            'client_secret': XFINITY_ANDROID_APPLICATION_CLIENT_SECRET
        }
        data.update(self.OAUTH_TOKEN_DATA)

        response = requests.post(OAUTH_TOKEN_URL, 
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
                    logger.info(f"Updating Oauth Token")
                    self.OAUTH_TOKEN = self.oauth_update_tokens(response_json)
            logger.debug(f"Updating Oauth Token Details {json.dumps(response_json)}")
        else:
            raise AssertionError(f"Oauth Token Error: {json.dumps(response_json)}")
        
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

        write_token_file_data(token_response,OAUTH_TOKEN_FILE)

        _expire_formatted_time = strftime("%Y-%m-%d %H:%M:%S", localtime(int(token_response['expires_at'])))

        logger.debug(f"Oauth Access Token: {token_response['access_token']}")
        logger.debug(f"Oauth Id Token: {token_response['id_token']}")
        logger.info(f"Oauth Refresh Token: {token_response['refresh_token']}")
        logger.debug(f"Oauth Activity Id: {token_response['activity_id']}")
        logger.info(f"Oauth Expires At: {token_response['expires_at']} ({_expire_formatted_time})")
        logger.debug(f"Xfinity Customer Guid: {token_response['customer_guid']}")

        return token_response


