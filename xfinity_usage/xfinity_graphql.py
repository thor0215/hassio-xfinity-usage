import hashlib
import math
import requests
from time import sleep
from typing import Optional
from .xfinity_globals import OAUTH_PROXY, OAUTH_CERT_VERIFY, REQUESTS_TIMEOUT
from .xfinity_helper import logger

_GRAPHQL_URL = 'https://gw.api.dh.comcast.com/galileo/graphql'

_GRAPHQL_APP_MAJOR_MINOR_PATCH_VERSION = '6.14.0'
_GRAPHQL_DEVICE_MANUFACTURER = 'Google'
_GRAPHQL_DEVICE_MODEL = 'Pixel 11 Pro'
_GRAPHQL_ANDROID_VERSION = '16'

# The APK appends a per-install DeviceIdProvider ID, which is not available here.
_GRAPHQL_EXTRA_HEADERS = {
    'user-agent':              f'Digital Home / {_GRAPHQL_DEVICE_MANUFACTURER} {_GRAPHQL_DEVICE_MODEL} / Android {_GRAPHQL_ANDROID_VERSION}',
    'client':                  'digital-home-android',
    'client-detail':           f'MOBILE;{_GRAPHQL_DEVICE_MANUFACTURER};{_GRAPHQL_DEVICE_MODEL};Android {_GRAPHQL_ANDROID_VERSION};v{_GRAPHQL_APP_MAJOR_MINOR_PATCH_VERSION}',
    'accept-language':         'en-US',
    'content-type':            'application/json'
}

_GRAPHQL_GATEWAY_DETAILS_HEADERS = {
    'x-apollo-operation-id': '3a71cb1fb63295ee5a4a74a73e889b88320a63237f420afcc9cc86f73cc909c1',
    'x-apollo-operation-name': 'User',
    'accept':                  'multipart/mixed; deferSpec=20220824, application/json'
}

_GRAPHQL_USAGE_DETAILS_HEADERS = {
    'x-apollo-operation-id': '61994c6016ac8c0ebcca875084919e5e01cb3b116a86aaf9646e597c3a1fbd06',
    'x-apollo-operation-name': 'InternetDataUsage',
    'accept':                  'multipart/mixed; deferSpec=20220824, application/json'
}

_GRAPHQL_PLAN_DETAILS_HEADERS = {
    'x-apollo-operation-id': '6bc115e8e4f48df95aad92c07c8536d76a779ae17dc1d786b3ffab014eab3804',
    'x-apollo-operation-name': 'AccountServicesWithoutXM',
    'accept':                  'multipart/mixed; deferSpec=20220824, application/json'
}

_GRAPHQL_MOBILE_SERVICE_HEADERS = {
    'x-apollo-operation-id': '6658062ef8a21b956b40bcce04ff922c84553d459754ff7b9a68c2c16ce9a2a5',
    'x-apollo-operation-name': 'XMService',
    'accept':                  'multipart/mixed; deferSpec=20220824, application/json'
}

_GRAPHQL_MOBILE_USAGE_HEADERS = {
    'x-apollo-operation-id': '8b7633c573e39c9f42aa3109481370d828153f44987005ff4c6bb9f6ae62f553',
    'x-apollo-operation-name': 'XMAccountSummary',
    'accept':                  'multipart/mixed; deferSpec=20220824, application/json'
}

class XfinityGraphQL():

    def convert_raw_mobile_usage_to_website_format(self, _raw_usage: dict) -> dict:
        data = _raw_usage.get('data')
        if not isinstance(data, dict):
            logger.error("Xfinity Mobile account summary returned an invalid data value")
            return {}

        account = data.get('accountByServiceAccountId')
        if not isinstance(account, dict):
            logger.error("Xfinity Mobile account summary did not include account details")
            return {}

        mobile = account.get('mobile')
        if not mobile:
            return {}
        if not isinstance(mobile, dict):
            logger.error("Xfinity Mobile account summary returned an invalid mobile value")
            return {}

        current_cycle = mobile.get('currentCycle')
        if current_cycle is None:
            current_cycle = {}
        elif not isinstance(current_cycle, dict):
            logger.warning("Xfinity Mobile account summary returned an invalid current cycle")
            current_cycle = {}
        cycle_end_date = current_cycle.get('endDate')
        days_remaining = current_cycle.get('daysLeft')
        sensors = {}
        line_keys = set()
        total_usage = 0.0
        plan_count = 0

        def usage_gb(usage, description):
            if not isinstance(usage, dict):
                logger.warning(f"Skipping Xfinity Mobile {description}: usage data is missing")
                return None

            value = usage.get('value')
            unit = usage.get('unit')
            factors = {'GB': 1.0, 'TB': 1000.0, 'MB': 0.001}
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                logger.warning(f"Skipping Xfinity Mobile {description}: usage value is invalid")
                return None
            if unit not in factors:
                logger.warning(f"Skipping Xfinity Mobile {description}: unsupported usage unit")
                return None

            return value * factors[unit]

        plans = mobile.get('plans', [])
        if not isinstance(plans, list):
            logger.error("Xfinity Mobile account summary returned an invalid plans value")
            return {}

        plan_details = []
        for plan_index, plan in enumerate(plans, start=1):
            if not isinstance(plan, dict):
                logger.warning("Skipping malformed Xfinity Mobile plan")
                continue

            plan_type = plan.get('type')
            subgroup = plan.get('subgroup')
            plan_detail = {}
            if isinstance(plan_type, str) and plan_type:
                plan_detail['plan_type'] = plan_type
            if isinstance(subgroup, str) and subgroup:
                plan_detail['subgroup'] = subgroup
            if isinstance(plan.get('dataLimit'), dict):
                data_limit_gb = usage_gb(plan.get('dataLimit'), f"plan {plan_index} data limit")
                if data_limit_gb is not None:
                    plan_detail['data_limit_gb'] = round(data_limit_gb, 2)
            plan_details.append(plan_detail)

            plan_usage = None
            if plan.get('currentUsage') is not None:
                plan_usage = usage_gb(plan.get('currentUsage'), f"plan {plan_index}")
            line_usage_total = 0.0

            lines = plan.get('lines') or []
            if not isinstance(lines, list):
                logger.warning(f"Skipping malformed Xfinity Mobile lines in plan {plan_index}")
                lines = []
            line_has_usage = False

            for line_index, line in enumerate(lines, start=1):
                if not isinstance(line, dict):
                    logger.warning(f"Skipping malformed Xfinity Mobile line in plan {plan_index}")
                    continue

                line_key = line.get('key')
                if not isinstance(line_key, str) or not line_key.strip():
                    logger.warning(f"Skipping Xfinity Mobile line {line_index}: line key is missing")
                    continue
                if line_key in line_keys:
                    continue

                line_usage = usage_gb(line.get('currentUsage'), f"line {line_index}")
                if line_usage is None:
                    continue

                line_keys.add(line_key)
                line_has_usage = True
                line_usage_total += line_usage
                line_name = line.get('nickname') or f"Line {len(sensors) + 1}"
                line_id = hashlib.sha256(line_key.encode()).hexdigest()[:12]
                entity_id = f"sensor.xfinity_mobile_line_{line_id}"
                attributes = {
                    'friendly_name': f"Xfinity Mobile - {line_name}",
                    'line_name': line_name,
                    'unit_of_measurement': 'GB',
                    'device_class': 'data_size',
                    'state_class': 'measurement',
                    'icon': 'mdi:signal-cellular-3',
                }
                if plan_type:
                    attributes['plan_type'] = plan_type
                if subgroup:
                    attributes['plan_subgroup'] = subgroup
                if 'data_limit_gb' in plan_detail:
                    attributes['data_limit_gb'] = plan_detail['data_limit_gb']
                if cycle_end_date:
                    attributes['cycle_end_date'] = cycle_end_date
                if isinstance(days_remaining, int) and not isinstance(days_remaining, bool):
                    attributes['days_remaining'] = days_remaining

                sensors[entity_id] = {
                    'state': round(line_usage, 2),
                    'attributes': attributes,
                }

            if plan_usage is not None:
                total_usage += plan_usage
                plan_count += 1
            else:
                total_usage += line_usage_total
                if line_has_usage:
                    plan_count += 1

        if not plan_count:
            return {}

        total_attributes = {
            'friendly_name': 'Xfinity Mobile Usage',
            'unit_of_measurement': 'GB',
            'device_class': 'data_size',
            'state_class': 'measurement',
            'icon': 'mdi:signal-cellular-3',
            'line_count': len(sensors),
            'mobile_plans': plan_details,
        }
        if cycle_end_date:
            total_attributes['cycle_end_date'] = cycle_end_date
        if isinstance(days_remaining, int) and not isinstance(days_remaining, bool):
            total_attributes['days_remaining'] = days_remaining

        sensors['sensor.xfinity_mobile_usage'] = {
            'state': round(total_usage, 2),
            'attributes': total_attributes,
        }
        return sensors

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
        monthly_usage = _raw_usage.get('monthlyUsage')
        if not isinstance(monthly_usage, list):
            logger.error("Xfinity Internet usage did not include monthly usage data")
            return {}

        def usage_gb(usage, description):
            if not isinstance(usage, dict):
                logger.warning(f"Skipping Xfinity Internet month: {description} is missing")
                return None

            value = usage.get('value')
            unit = usage.get('unit')
            factors = {'GB': 1.0, 'TB': 1000.0, 'MB': 0.001}
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                logger.warning(f"Skipping Xfinity Internet month: {description} is invalid")
                return None
            factor = factors.get(str(unit).upper())
            if factor is None:
                logger.warning(f"Skipping Xfinity Internet month: {description} has an unsupported unit")
                return None
            return value * factor

        new_raw_usage = {'usageMonths': []}
        for item in reversed(monthly_usage):
            if not isinstance(item, dict):
                logger.warning("Skipping malformed Xfinity Internet usage month")
                continue

            total_usage = usage_gb(item.get('currentUsage'), 'current usage')
            if total_usage is None:
                continue
            policy = item.get('policy')
            allowable_usage = usage_gb(item.get('allowableUsage'), 'allowable usage')
            if allowable_usage is None:
                if policy == 'limited':
                    continue
                allowable_usage = -1

            start_date = item.get('startDate')
            end_date = item.get('endDate')
            if not isinstance(start_date, str) or not isinstance(end_date, str):
                logger.warning("Skipping Xfinity Internet month: dates are missing or invalid")
                continue
            start_parts = start_date.split('-')
            end_parts = end_date.split('-')
            if len(start_parts) != 3 or len(end_parts) != 3:
                logger.warning("Skipping Xfinity Internet month: dates are not in ISO format")
                continue

            new_raw_usage['usageMonths'].append({
                'startDate': f'{start_parts[1]}/{start_parts[2]}/{start_parts[0]}',
                'endDate': f'{end_parts[1]}/{end_parts[2]}/{end_parts[0]}',
                'totalUsage': round(total_usage, 2),
                'allowableUsage': round(allowable_usage, 2),
                'unitOfMeasure': 'GB',
                'policy': policy,
            })

        return new_raw_usage if new_raw_usage['usageMonths'] else {}

    def convert_raw_plan_to_website_format(self, _raw_plan: dict) -> dict:
        if not isinstance(_raw_plan, dict):
            return {}

        def speed_mbps(speed, name):
            if speed is None:
                return -1
            if isinstance(speed, dict):
                value = speed.get('value')
                unit = speed.get('unit', 'Mbps')
            else:
                value = speed
                unit = 'Mbps'

            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                logger.warning(f"Xfinity Internet plan returned an invalid {name} speed")
                return -1

            factors = {'mbps': 1.0, 'gbps': 1000.0, 'kbps': 0.001}
            factor = factors.get(str(unit).lower())
            if factor is None:
                logger.warning(f"Xfinity Internet plan returned an unsupported {name} speed unit")
                return -1
            return round(value * factor, 2)

        plan_name = _raw_plan.get('name') or _raw_plan.get('tierOfService') or ''
        has_plan_data = bool(plan_name) or any(
            key in _raw_plan for key in ('downloadSpeed', 'uploadSpeed')
        )
        if not has_plan_data:
            return {}

        return {
            'service_available': True,
            'planName': plan_name,
            'downloadSpeed': speed_mbps(_raw_plan.get('downloadSpeed'), 'download'),
            'uploadSpeed': speed_mbps(_raw_plan.get('uploadSpeed'), 'upload'),
        }

    def get_gateway_details_data(self, _TOKEN) -> dict:
        headers = dict(_GRAPHQL_GATEWAY_DETAILS_HEADERS)
        headers.update({
            'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
            'x-id-token': f"{_TOKEN['id_token']}"
        })
        headers.update(_GRAPHQL_EXTRA_HEADERS)
        query = """
                query User($customerGuid: ID) {
                    user(customerGuid: $customerGuid) {
                        experience
                        analytics
                        eligibilities
                        tabs
                        featurePermissions {
                            name
                            privileges
                        }
                        account {
                            serviceAccountId
                            billingAccountId
                            partner
                            timeZone
                            zipCode
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
                            preActiveGateway {
                                deviceClass
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

        try:
            response = requests.post(_GRAPHQL_URL, 
                                    headers=headers, 
                                    json=data,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)
            response_json = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GraphQL gateway request failed: {e}")
            return {}
        except ValueError as e:
            logger.error(f"GraphQL gateway response was not valid JSON: {e}")
            return {}

        if not response.ok:
            logger.error(f"GraphQL gateway request failed with status {response.status_code}")
            return {}
        if not isinstance(response_json, dict) or 'errors' in response_json:
            logger.error("GraphQL gateway request returned errors or an invalid response")
            return {}

        response_data = response_json.get('data')
        user = response_data.get('user') if isinstance(response_data, dict) else None
        account = user.get('account') if isinstance(user, dict) else None
        if not isinstance(account, dict):
            logger.error("GraphQL gateway response did not include account details")
            return {}

        gateway_details = account.get('modem') or account.get('router') or {}
        if gateway_details:
            logger.info("Updating Internet Device Details")
        else:
            logger.info("No modem or router details were returned")
        return gateway_details


    def get_usage_details_data(self, _TOKEN) -> dict:
        headers = dict(_GRAPHQL_USAGE_DETAILS_HEADERS)
        headers.update({
            'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
            'x-id-token': f"{_TOKEN['id_token']}"
        })
        headers.update(_GRAPHQL_EXTRA_HEADERS)
        data = {
            'operationName': 'InternetDataUsage',
            'variables': {},
            'query': 'query InternetDataUsage { accountByServiceAccountId { internet { usage { inPaidOverage courtesy { totalAllowableCourtesy usedCourtesy remainingCourtesy } monthlyUsage { policy month year startDate endDate daysRemaining currentUsage { value unit } allowableUsage { value unit } overage overageCharge maximumOverageCharge courtesyCredit } } } } }',
        }

        for attempt in range(2):
            try:
                response = requests.post(
                    _GRAPHQL_URL,
                    headers=headers,
                    json=data,
                    proxies=OAUTH_PROXY,
                    verify=OAUTH_CERT_VERIFY,
                    timeout=REQUESTS_TIMEOUT,
                )
                response_json = response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"GraphQL usage request failed: {e}")
                return {}
            except ValueError as e:
                logger.error(f"GraphQL usage response was not valid JSON: {e}")
                return {}

            if response.ok and isinstance(response_json, dict) and 'errors' not in response_json:
                response_data = response_json.get('data')
                account = response_data.get('accountByServiceAccountId') if isinstance(response_data, dict) else None
                internet = account.get('internet') if isinstance(account, dict) else None
                usage = internet.get('usage') if isinstance(internet, dict) else None
                monthly_usage = usage.get('monthlyUsage') if isinstance(usage, dict) else None
                if isinstance(monthly_usage, list) and monthly_usage:
                    logger.info("Updating Internet Usage Details")
                    return self.convert_raw_usage_to_website_format(usage)
                if isinstance(monthly_usage, list):
                    logger.info("No monthly Internet usage data was returned")
                    return {}
                logger.error("GraphQL usage response did not contain monthly Internet usage data")
            else:
                if response.ok:
                    logger.error("GraphQL usage response was invalid or contained errors")
                else:
                    logger.error(f"GraphQL usage request failed with status {response.status_code}")
            if attempt == 0:
                sleep(1)

        return {}

    def get_mobile_usage_details_data(self, _TOKEN) -> dict:
        headers = {}
        headers.update(_GRAPHQL_MOBILE_USAGE_HEADERS)
        headers.update({
            'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
            'x-id-token': f"{_TOKEN['id_token']}"
        })
        headers.update(_GRAPHQL_EXTRA_HEADERS)
        query = """query XMAccountSummary { accountByServiceAccountId { __typename mobile { __typename numberOfLines accountSegment currentCycle { __typename endDate daysLeft } canAddLine plans { __typename ...accountSummaryFragment } } } } fragment accountSummaryFragment on MobilePlan { __typename type ... on UnlimitedPlan { subgroup } ... on SmartWatchPlan { subgroup } ... on ByTheGigSharedPlan { currentUsage { __typename unit value } dataLimit { __typename unit value } } lines { __typename id key nickname status activationStatus phoneNumber isPaymentPastDue currentUsage { __typename unit value } primaryDevice { __typename id key make model type image { __typename url } } pairedLines { __typename id key status activationStatus nickname phoneNumber primaryDevice { __typename id key make model type image { __typename url } } } } }"""
        data = {
            'operationName': 'XMAccountSummary',
            'variables': {},
            'query': query,
        }

        try:
            response = requests.post(
                _GRAPHQL_URL,
                headers=headers,
                json=data,
                proxies=OAUTH_PROXY,
                verify=OAUTH_CERT_VERIFY,
                timeout=REQUESTS_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Xfinity Mobile usage request failed: {e}")
            return {}

        if not response.ok:
            logger.error(f"Xfinity Mobile usage request failed with status {response.status_code}")
            return {}

        try:
            response_json = response.json()
        except ValueError as e:
            logger.error(f"Xfinity Mobile usage response was not valid JSON: {e}")
            return {}

        if not isinstance(response_json, dict) or 'errors' in response_json:
            logger.error("Xfinity Mobile usage request returned GraphQL errors")
            return {}

        return self.convert_raw_mobile_usage_to_website_format(response_json)

    def get_mobile_service_details_data(self, _TOKEN) -> Optional[dict]:
        headers = dict(_GRAPHQL_MOBILE_SERVICE_HEADERS)
        headers.update({
            'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
            'x-id-token': f"{_TOKEN['id_token']}"
        })
        headers.update(_GRAPHQL_EXTRA_HEADERS)
        data = {
            'operationName': 'XMService',
            'variables': {},
            'query': 'query XMService { accountByServiceAccountId { mobile { hasUnlinkedLines numberOfLines pendingActivationsCount plans { lines { nickname status } } } } }',
        }

        try:
            response = requests.post(
                _GRAPHQL_URL,
                headers=headers,
                json=data,
                proxies=OAUTH_PROXY,
                verify=OAUTH_CERT_VERIFY,
                timeout=REQUESTS_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Xfinity Mobile service request failed: {e}")
            return None

        if not response.ok:
            logger.error(f"Xfinity Mobile service request failed with status {response.status_code}")
            return None
        try:
            response_json = response.json()
        except ValueError as e:
            logger.error(f"Xfinity Mobile service response was not valid JSON: {e}")
            return None

        if not isinstance(response_json, dict) or 'errors' in response_json:
            logger.error("Xfinity Mobile service request returned GraphQL errors")
            return None

        response_data = response_json.get('data')
        account = response_data.get('accountByServiceAccountId') if isinstance(response_data, dict) else None
        if not isinstance(account, dict):
            logger.error("Xfinity Mobile service response did not include account details")
            return None

        mobile = account.get('mobile')
        if mobile is None:
            return {'has_service': False, 'number_of_lines': 0, 'pending_activations_count': 0}
        if not isinstance(mobile, dict):
            logger.error("Xfinity Mobile service response returned an invalid mobile value")
            return None

        number_of_lines = mobile.get('numberOfLines', 0)
        pending_activations = mobile.get('pendingActivationsCount', 0)
        if not isinstance(number_of_lines, int) or isinstance(number_of_lines, bool):
            number_of_lines = 0
        if not isinstance(pending_activations, int) or isinstance(pending_activations, bool):
            pending_activations = 0
        return {
            'has_service': number_of_lines > 0,
            'number_of_lines': number_of_lines,
            'pending_activations_count': pending_activations,
        }

    def get_plan_details_data(self, _TOKEN) -> Optional[dict]:
        headers = dict(_GRAPHQL_PLAN_DETAILS_HEADERS)
        headers.update({
            'authorization': f"{_TOKEN['token_type']} {_TOKEN['access_token']}",
            'x-id-token': f"{_TOKEN['id_token']}"
        })
        headers.update(_GRAPHQL_EXTRA_HEADERS)
        data = {
            'operationName': 'AccountServicesWithoutXM',
            'variables': {},
            'query': 'query AccountServicesWithoutXM { accountByServiceAccountId { internet { plan { name downloadSpeed { unit value } uploadSpeed { unit value } } usage { inPaidOverage courtesy { totalAllowableCourtesy usedCourtesy remainingCourtesy } monthlyUsage { policy month year startDate endDate daysRemaining currentUsage { value unit } allowableUsage { value unit } overage overageCharge maximumOverageCharge courtesyCredit } } } } }',
        }

        try:
            response = requests.post(_GRAPHQL_URL, 
                                    headers=headers, 
                                    json=data,
                                    proxies=OAUTH_PROXY,
                                    verify=OAUTH_CERT_VERIFY,
                                    timeout=REQUESTS_TIMEOUT)
            response_json = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GraphQL Internet plan request failed: {e}")
            return None
        except ValueError as e:
            logger.error(f"GraphQL Internet plan response was not valid JSON: {e}")
            return None

        if not response.ok:
            logger.error(f"GraphQL Internet plan request failed with status {response.status_code}")
            return None
        if not isinstance(response_json, dict) or 'errors' in response_json:
            logger.error("GraphQL Internet plan request returned errors or an invalid response")
            return None

        response_data = response_json.get('data')
        account = response_data.get('accountByServiceAccountId') if isinstance(response_data, dict) else None
        if not isinstance(account, dict):
            logger.error("GraphQL Internet plan response did not include account details")
            return None
        if 'internet' not in account:
            logger.error("GraphQL Internet plan response did not include Internet service status")
            return None
        internet = account.get('internet')
        if internet is None:
            return {}
        if not isinstance(internet, dict):
            logger.error("GraphQL Internet plan response returned an invalid internet value")
            return None

        plan = internet.get('plan')
        if plan is None:
            return {'service_available': True, 'planName': '', 'downloadSpeed': -1, 'uploadSpeed': -1}

        plan_details = self.convert_raw_plan_to_website_format(plan)
        if not plan_details:
            return {'service_available': True, 'planName': '', 'downloadSpeed': -1, 'uploadSpeed': -1}
        plan_details['service_available'] = True
        return plan_details
