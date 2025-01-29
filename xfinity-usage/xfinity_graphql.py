import base64
import requests
from time import sleep
from xfinity_globals import OAUTH_PROXY, OAUTH_CERT_VERIFY, REQUESTS_TIMEOUT
from xfinity_helper import logger

class XfinityGraphQL():
    def __init__(self) -> None:
        self.GRAPHQL_URL = 'https://gw.api.dh.comcast.com/galileo/graphql'

        self.GRAPHQL_EXTRA_HEADERS = {
            'user-agent':              'Digital Home / Samsung SM-G991B / Android 14',
            'client':                  'digital-home-android',
            'client-detail':           'MOBILE;Samsung;SM-G991B;Android 14;v5.38.0',
            'accept-language':         'en-US',
            'content-type':            'application/json'
        }

        self.GRAPHQL_GATGEWAY_DETAILS_HEADERS = {
            'x-apollo-operation-id': '34a752659014e11c5617dc4d469941230f2b25dffab3197d5bde752a9ecc5569',
            'x-apollo-operation-name': 'User',
            'accept':                  'multipart/mixed; deferSpec=20220824, application/json'
        }

        self.GRAPHQL_USAGE_DETAILS_HEADERS = {
            'x-apollo-operation-id': '61994c6016ac8c0ebcca875084919e5e01cb3b116a86aaf9646e597c3a1fbd06',
            'x-apollo-operation-name': 'InternetDataUsage',
            'accept':                  'multipart/mixed; deferSpec=20220824, application/json'
        }

        self.GRAPHQL_PLAN_DETAILS_HEADERS = {
            'x-apollo-operation-id': 'cb26cdb7288e179b750ec86d62f8a16548902db3d79d2508ca98aa4a8864c7e1',
            'x-apollo-operation-name': 'AccountServicesWithoutXM',
            'accept':                  'multipart/mixed; deferSpec=20220824, application/json'
        }


    def convert_raw_usage_to_website_format(self, _raw_usage: dict) -> dict:
        """

        {
            "policy": "limited",
            "month": 2,
            "year": 2024,
            "startDate": "2024-02-01",
            "endDate": "2024-02-29",
            "daysRemaining": 0,
            "currentUsage": {
                "value": 558,
                "unit": "GB"
            },
            "allowableUsage": {
                "value": 1.23,
                "unit": "TB"
            },
            "overage": false,
            "overageCharge": 0,
            "maximumOverageCharge": 100,
            "courtesyCredit": false
        }

        {
            "startDate": "10/01/2024",
            "endDate": "10/31/2024",
            "totalUsage": 691,
            "allowableUsage": 1229,
            "unitOfMeasure": "GB",
            "policy": "limited"
        }
        """
        reversed_raw_usage = list(reversed(_raw_usage['monthlyUsage']))
        new_raw_usage = { 'usageMonths': [] }
        for item in reversed_raw_usage:
            split_start_date = item['startDate'].split('-')
            startDate = split_start_date[1] + '/' + split_start_date[2] + '/' + split_start_date[0]

            split_end_date = item['endDate'].split('-')
            endDate = split_end_date[1] + '/' + split_end_date[2] + '/' + split_end_date[0]

            if item['currentUsage']['unit'] == 'TB':
                totalUsage = int(item['currentUsage']['value'] * 1000)
            else: 
                totalUsage = int(item['currentUsage']['value'])

            allowableUsage = int(item['allowableUsage']['value'] * 1000)

            policy = item['policy']
            
            new_raw_usage['usageMonths'].append( {
                "startDate": startDate,
                "endDate": endDate,
                "totalUsage": totalUsage,
                "allowableUsage": allowableUsage,
                "unitOfMeasure": "GB",
                "policy": policy
            } )

        return new_raw_usage

    def convert_raw_plan_to_website_format(self, _raw_plan: dict) -> dict:
        new_raw_plan = {
             'downloadSpeed': _raw_plan['downloadSpeed']['value'],
             'uploadSpeed': -1
        }
        return new_raw_plan

    def get_gateway_details_data(self, _TOKEN) -> dict:
        _retry_counter = 1
        _gateway_details = {}
        headers = {}
        headers.update(self.GRAPHQL_GATGEWAY_DETAILS_HEADERS)
        headers.update({
            'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
            'x-id-token': f"{_TOKEN['id_token']}"
        })
        headers.update(self.GRAPHQL_EXTRA_HEADERS)
        #data = '{"operationName":"User","variables":{"customerGuid":"' + _TOKEN['customer_guid'] + '"},"query":"query User($customerGuid: ID) { user(customerGuid: $customerGuid) { experience analytics eligibilities tabs account { serviceAccountId billingAccountId partner timeZone zipCode primaryGateway { make model macAddress deviceClass } router { make model macAddress deviceClass deviceType coam } modem { make model macAddress deviceClass deviceType coam } } } }"}'
        query = """
                query User($customerGuid: ID) {
                    user(customerGuid: $customerGuid) {
                        experience
                        account {
                            serviceAccountId
                            billingAccountId
                            partner
                            timeZone
                            zipCode
                            primaryGateway {
                                make
                                model
                                macAddress
                                deviceClass
                            }
                            router {
                                make
                                model
                                macAddress
                                deviceClass
                                deviceType
                                coam
                            }
                            modem {
                                make
                                model
                                macAddress
                                deviceClass
                                deviceType
                                coam
                            }
                        }
                    }
                }
        """
        data =  {
                "operationName": "User",
                "variables": {
                    "customerGuid": _TOKEN['customer_guid']
                },
                "query": query
        }

        while(_retry_counter < 3):
            response = requests.post(self.GRAPHQL_URL, 
                                    headers=headers, 
                                    json=data,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)

            response_json = response.json()
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")

            if  response.ok:
                if  'errors' not in response_json and \
                    'data' in response_json and \
                    len(response_json['data']['user']['account']['modem']) > 0:
                        _gateway_details = response_json['data']['user']['account']['modem']
                        logger.info(f"Updating Device Details")
                        return _gateway_details
            else:
                _retry_counter += 1
                sleep(1* pow(_retry_counter, _retry_counter))
             
        else:
            logger.error(f"GraphQL Gateway Error:")
            logger.error(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.error(f"Response: {response_content_b64}")

        sleep(1)
        return _gateway_details


    def get_usage_details_data(self, _TOKEN) -> dict:
        _retry_counter = 1
        _usage_details = {}
        headers = {}
        headers.update(self.GRAPHQL_USAGE_DETAILS_HEADERS)
        headers.update({
            'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
            'x-id-token': f"{_TOKEN['id_token']}"
        })
        headers.update(self.GRAPHQL_EXTRA_HEADERS)
        #data = '{"operationName": "InternetDataUsage","variables": {},"query": "query InternetDataUsage { accountByServiceAccountId { internet { usage { inPaidOverage courtesy { totalAllowableCourtesy usedCourtesy remainingCourtesy } monthlyUsage { policy month year startDate endDate daysRemaining currentUsage { value unit } allowableUsage { value unit } overage overageCharge maximumOverageCharge courtesyCredit } } } } }"}'
        query = """
                query InternetDataUsage {
                    accountByServiceAccountId {
                        internet {
                            usage {
                                monthlyUsage {
                                policy
                                startDate
                                endDate
                                daysRemaining
                                currentUsage {
                                    value
                                    unit
                                }
                                allowableUsage {
                                    value
                                    unit
                                }
                                }
                            }
                        }
                    }
                }
        """
        data =  {
                "operationName": "InternetDataUsage",
                "variables": {},
                "query": query
        }

        while(_retry_counter < 3):
            response = requests.post(self.GRAPHQL_URL,
                            headers=headers, 
                            json=data,
                            proxies=OAUTH_PROXY,
                            verify=OAUTH_CERT_VERIFY,
                            timeout=REQUESTS_TIMEOUT)
            

            response_json = response.json()
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")

            if  response.ok:
                if  'errors' not in response_json and \
                    'data' in response_json and \
                    len(response_json['data']['accountByServiceAccountId']['internet']['usage']['monthlyUsage']) > 0:
                        logger.info(f"Updating Usage Details")
                        _usage_details = response_json['data']['accountByServiceAccountId']['internet']['usage']
                        return self.convert_raw_usage_to_website_format(_usage_details)
                else:
                    _retry_counter += 1
                    sleep(1* pow(_retry_counter, _retry_counter))
            else:
                logger.error(f"GraphQL Usage Error:")
                logger.error(f"Response Status Code: {response.status_code}")
                response_content_b64 = base64.b64encode(response.content).decode()
                logger.error(f"Response: {response_content_b64}")


        return _usage_details


    def get_plan_details_data(self, _TOKEN) -> dict:
        _retry_counter = 1
        _plan_details = {}
        headers = {}
        headers.update(self.GRAPHQL_PLAN_DETAILS_HEADERS)
        headers.update({
            'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
            'x-id-token': f"{_TOKEN['id_token']}"
        })
        headers.update(self.GRAPHQL_EXTRA_HEADERS)

        #data =  '{"operationName":"AccountServicesWithoutXM","variables":{},"query":"query AccountServicesWithoutXM { accountByServiceAccountId { internet { plan { name downloadSpeed { unit value } uploadSpeed { unit value } } usage { inPaidOverage courtesy { totalAllowableCourtesy usedCourtesy remainingCourtesy } monthlyUsage { policy month year startDate endDate daysRemaining currentUsage { value unit } allowableUsage { value unit } overage overageCharge maximumOverageCharge courtesyCredit } } } home { plan } video { plan { name description flex stream x1 } } } }"}'
        query = """
                query AccountServicesWithoutXM {
                    accountByServiceAccountId {
                        internet {
                        plan {
                            name
                            downloadSpeed {
                            unit
                            value
                            }
                            uploadSpeed {
                            unit
                            value
                            }
                        }
                        }
                    }
                }
        """
        data =  {
                "operationName": "AccountServicesWithoutXM",
                "variables": {},
                "query": query
        }

        while(_retry_counter < 3):
            response = requests.post(self.GRAPHQL_URL, 
                                    headers=headers, 
                                    json=data,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)

            response_json = response.json()
            logger.debug(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.debug(f"Response: {response_content_b64}")
            #logger.debug(f"Response JSON: {response.json()}")

            if  response.ok:
                if  'errors' not in response_json and \
                    'data' in response_json and \
                    len(response_json['data']['accountByServiceAccountId']['internet']['plan']) > 0:
                        logger.info(f"Updating Plan Details")
                        _plan_details = response_json['data']['accountByServiceAccountId']['internet']['plan']
                        return self.convert_raw_plan_to_website_format(_plan_details)
                else:
                    _retry_counter += 1
                    sleep(1* pow(_retry_counter, _retry_counter))


        else:
            logger.error(f"GraphQL Plan Error: ")
            logger.error(f"Response Status Code: {response.status_code}")
            response_content_b64 = base64.b64encode(response.content).decode()
            logger.error(f"Response: {response_content_b64}")

        return _plan_details
