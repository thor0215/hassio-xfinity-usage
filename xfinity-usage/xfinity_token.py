import json
import jwt
import requests
import time
from jwt import PyJWKClient
from xfinity_helper import *


def get_code_token(_CODE, _ACTIVITY_ID, _CODE_VERIFIER) -> None:
    new_token = {}
    data = {
        'code': _CODE,
        'grant_type': 'authorization_code',
        'activity_id': _ACTIVITY_ID,
        'redirect_uri': 'xfinitydigitalhome%3A%2F%2Fauth',
        'client_secret': CLIENT_SECRET,
        'code_verifier': _CODE_VERIFIER
    }
    data.update(OAUTH_TOKEN_DATA)

    result = requests.post(OAUTH_TOKEN_URL, 
                            headers=OAUTH_TOKEN_EXTRA_HEADERS, 
                            data=data, 
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY)
    
    response_json = result.json()

    if result.ok:
        if  'error' not in response_json:
                logger.debug(f"Updating code: {_CODE}")
                logger.debug(f"         code_verifier: {_CODE_VERIFIER}")
                logger.debug(f"         activity_id: {_ACTIVITY_ID}")
                new_token = oauth_update_tokens(response_json)
        logger.debug(f"Updating code Details {json.dumps(response_json)}")
    else:
        raise AssertionError(f"Oauth Code Token Error: {json.dumps(response_json)}")

    return new_token

def oauth_refresh_tokens(_TOKEN) -> None:
    new_token = {}
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': _TOKEN['refresh_token'],
        'client_secret': CLIENT_SECRET
    }
    data.update(OAUTH_TOKEN_DATA)

    result = requests.post(OAUTH_TOKEN_URL, 
                           headers=OAUTH_TOKEN_EXTRA_HEADERS, 
                           data=data, 
                           proxies=OAUTH_PROXY,
                           verify=OAUTH_CERT_VERIFY)
    
    response_json = result.json()
    if result.ok:   
        if  'error' not in response_json and 'access_token' in response_json:
                logger.info(f"Updating Oauth Token")
                new_token = oauth_update_tokens(response_json)
        logger.debug(f"Updating Oauth Token Details {json.dumps(response_json)}")
    else:
        raise AssertionError(f"Oauth Token Error: {json.dumps(response_json)}")
    
    return new_token


def oauth_update_tokens(token_response) -> None:
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

    write_token_file_data(token_response)

    _expire_formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(token_response['expires_at'])))

    logger.debug(f"Oauth Access Token: {token_response['access_token']}")
    logger.debug(f"Oauth Id Token: {token_response['id_token']}")
    logger.info(f"Oauth Refresh Token: {token_response['refresh_token']}")
    logger.debug(f"Oauth Activity Id: {token_response['activity_id']}")
    logger.info(f"Oauth Expires At: {token_response['expires_at']} ({_expire_formatted_time})")
    logger.debug(f"Xfinity Customer Guid: {token_response['customer_guid']}")

    return token_response

