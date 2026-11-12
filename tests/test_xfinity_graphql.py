import hashlib
import json
import pytest
import requests
from unittest.mock import patch, MagicMock
from xfinity_usage.xfinity_graphql import XfinityGraphQL
from const import *

@pytest.fixture
def my_graphql():
    graphql = XfinityGraphQL()
    return graphql

def test_convert_raw_usage_to_website_format(my_graphql):
    raw_plan = MOCK_GRAPHQL_USAGE_RESPONSE_SUCCESS['data']['accountByServiceAccountId']['internet']['usage']
    converted_plan = my_graphql.convert_raw_usage_to_website_format(raw_plan)
    assert converted_plan == {
        'usageMonths' : [
            {'startDate': '09/01/2025', 'endDate': '09/30/2025', 'totalUsage': 353, 'allowableUsage': 1230, 'unitOfMeasure': 'GB', 'policy': 'limited'},
        ]
    }

def test_convert_raw_usage_converts_mb_and_preserves_fractional_gb(my_graphql):
    converted = my_graphql.convert_raw_usage_to_website_format({
        'monthlyUsage': [{
            'policy': 'limited',
            'startDate': '2025-10-01',
            'endDate': '2025-10-31',
            'currentUsage': {'value': 512, 'unit': 'MB'},
            'allowableUsage': {'value': 1, 'unit': 'TB'},
        }],
    })

    assert converted['usageMonths'][0]['totalUsage'] == 0.51
    assert converted['usageMonths'][0]['allowableUsage'] == 1000


def test_convert_raw_plan_to_website_format(my_graphql):
    raw_plan = MOCK_GRAPHQL_PLAN_RESPONSE_SUCCESS['data']['accountByServiceAccountId']['internet']['plan']
    converted_plan = my_graphql.convert_raw_plan_to_website_format(raw_plan)
    assert converted_plan == {
        'service_available': True,
        'planName': 'XI Superfast',
        'downloadSpeed': 800,
        'uploadSpeed': 35,
    }

def test_convert_raw_plan_to_website_format_normalizes_speed_units(my_graphql):
    converted_plan = my_graphql.convert_raw_plan_to_website_format({
        'name': 'Gigabit',
        'downloadSpeed': {'value': 1.2, 'unit': 'Gbps'},
        'uploadSpeed': None,
    })

    assert converted_plan['downloadSpeed'] == 1200
    assert converted_plan['uploadSpeed'] == -1

def test_get_gateway_details_data(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = MOCK_GRAPHQL_GATEWAY_RESPONSE_SUCCESS
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response) as mock_post:
        result = my_graphql.get_gateway_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)
        assert result == MOCK_GRAPHQL_GATEWAY_RESPONSE_SUCCESS['data']['user']['account']['modem']
        assert mock_post.call_args.kwargs['headers']['x-apollo-operation-id'] == '3a71cb1fb63295ee5a4a74a73e889b88320a63237f420afcc9cc86f73cc909c1'

def test_get_gateway_details_data_uses_router_when_modem_is_missing(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        'data': {'user': {'account': {'modem': None, 'router': {'model': 'xFi Gateway'}}}}
    }

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response):
        assert my_graphql.get_gateway_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN) == {'model': 'xFi Gateway'}

def test_get_plan_details_data(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = MOCK_GRAPHQL_PLAN_RESPONSE_SUCCESS
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response) as mock_post:
        result = my_graphql.get_plan_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)
        assert result == my_graphql.convert_raw_plan_to_website_format(MOCK_GRAPHQL_PLAN_RESPONSE_SUCCESS['data']['accountByServiceAccountId']['internet']['plan'])
        assert mock_post.call_args.kwargs['headers']['x-apollo-operation-id'] == '6bc115e8e4f48df95aad92c07c8536d76a779ae17dc1d786b3ffab014eab3804'
        assert mock_post.call_args.kwargs['headers']['user-agent'] == 'Digital Home / Google Pixel 11 Pro / Android 16'
        assert mock_post.call_args.kwargs['headers']['client-detail'] == 'MOBILE;Google;Pixel 11 Pro;Android 16;v6.14.0'

def test_get_plan_details_data_detects_internet_without_plan(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        'data': {'accountByServiceAccountId': {'internet': {'plan': None}}}
    }

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response):
        result = my_graphql.get_plan_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)

    assert result == {
        'service_available': True,
        'planName': '',
        'downloadSpeed': -1,
        'uploadSpeed': -1,
    }

def test_get_plan_details_data_returns_none_when_service_check_fails(my_graphql):
    with patch(
        "xfinity_usage.xfinity_graphql.requests.post",
        side_effect=requests.exceptions.ConnectionError("offline"),
    ):
        assert my_graphql.get_plan_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN) is None

def test_get_usage_details_data(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = MOCK_GRAPHQL_USAGE_RESPONSE_SUCCESS
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response) as mock_post:
        result = my_graphql.get_usage_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)
        assert result == my_graphql.convert_raw_usage_to_website_format(MOCK_GRAPHQL_USAGE_RESPONSE_SUCCESS['data']['accountByServiceAccountId']['internet']['usage'])
        request_data = mock_post.call_args.kwargs['json']
        assert request_data['query'].startswith('query InternetDataUsage {')
        assert 'courtesy { totalAllowableCourtesy usedCourtesy remainingCourtesy }' in request_data['query']
        assert mock_post.call_args.kwargs['headers']['x-apollo-operation-id'] == '61994c6016ac8c0ebcca875084919e5e01cb3b116a86aaf9646e597c3a1fbd06'

def test_get_usage_details_data_returns_empty_for_no_usage(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.content = b"{}"
    mock_response.json.return_value = {
        'data': {'accountByServiceAccountId': {'internet': {'usage': {'monthlyUsage': []}}}}
    }

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response):
        assert my_graphql.get_usage_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN) == {}

def test_get_usage_details_data_returns_empty_after_bounded_http_retries(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 503

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response) as mock_post, \
            patch("xfinity_usage.xfinity_graphql.sleep"):
        assert my_graphql.get_usage_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN) == {}

    assert mock_post.call_count == 2

def test_get_usage_details_data_returns_empty_on_request_error(my_graphql):
    with patch(
        "xfinity_usage.xfinity_graphql.requests.post",
        side_effect=requests.exceptions.ConnectionError("offline"),
    ) as mock_post:
        assert my_graphql.get_usage_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN) == {}

    mock_post.assert_called_once()

def test_get_usage_details_data_returns_empty_on_invalid_json(my_graphql):
    mock_response = MagicMock()
    mock_response.json.side_effect = ValueError("invalid JSON")

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response) as mock_post:
        assert my_graphql.get_usage_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN) == {}

    mock_post.assert_called_once()

def test_convert_raw_mobile_usage_to_website_format(my_graphql):
    raw_usage = {
        'data': {
            'accountByServiceAccountId': {
                'mobile': {
                    'currentCycle': {'endDate': '2025-11-30', 'daysLeft': 12},
                    'plans': [
                        {
                            'type': 'UnlimitedPlan',
                            'lines': [
                                {'key': 'line-one', 'nickname': 'Primary', 'currentUsage': {'value': 2.5, 'unit': 'GB'}},
                                {'key': 'line-two', 'nickname': 'Tablet', 'currentUsage': {'value': 512, 'unit': 'MB'}},
                            ],
                        },
                        {
                            'type': 'ByTheGigSharedPlan',
                            'subgroup': 'SHARED',
                            'currentUsage': {'value': 1, 'unit': 'TB'},
                            'dataLimit': {'value': 10, 'unit': 'GB'},
                            'lines': [
                                {'key': 'line-three', 'nickname': 'Shared', 'currentUsage': {'value': 100, 'unit': 'MB'}},
                            ],
                        },
                    ],
                },
            },
        },
    }

    result = my_graphql.convert_raw_mobile_usage_to_website_format(raw_usage)
    line_one_id = hashlib.sha256(b'line-one').hexdigest()[:12]
    line_two_id = hashlib.sha256(b'line-two').hexdigest()[:12]
    line_three_id = hashlib.sha256(b'line-three').hexdigest()[:12]

    assert result[f'sensor.xfinity_mobile_line_{line_one_id}']['state'] == 2.5
    assert result[f'sensor.xfinity_mobile_line_{line_two_id}']['state'] == 0.51
    assert result[f'sensor.xfinity_mobile_line_{line_one_id}']['attributes']['cycle_end_date'] == '2025-11-30'
    assert result[f'sensor.xfinity_mobile_line_{line_three_id}']['attributes']['plan_subgroup'] == 'SHARED'
    assert result['sensor.xfinity_mobile_usage']['state'] == 1003.01
    assert result['sensor.xfinity_mobile_usage']['attributes']['line_count'] == 3
    assert result['sensor.xfinity_mobile_usage']['attributes']['mobile_plans'][1]['data_limit_gb'] == 10

def test_create_mobile_diagnostic_export_rounds_usage_and_removes_identifiers(my_graphql):
    raw_usage = {
        'data': {
            'accountByServiceAccountId': {
                'mobile': {
                    '__typename': 'Mobile',
                    'numberOfLines': 1,
                    'accountSegment': 'PRIVATE_SEGMENT',
                    'currentCycle': {'endDate': '2030-01-31', 'daysLeft': 9},
                    'plans': [{
                        '__typename': 'ByTheGigSharedPlan',
                        'type': 'ByTheGigSharedPlan',
                        'subgroup': 'SHARED',
                        'currentUsage': {'value': 1.2345, 'unit': 'TB'},
                        'dataLimit': {'value': 10, 'unit': 'GB'},
                        'lines': [{
                            '__typename': 'Line',
                            'id': 'PRIVATE_LINE_ID',
                            'key': 'PRIVATE_LINE_KEY',
                            'nickname': 'PRIVATE_NAME',
                            'phoneNumber': '+15555550123',
                            'status': 'ACTIVE',
                            'activationStatus': 'ACTIVATED',
                            'currentUsage': {'value': 123.456, 'unit': 'MB'},
                            'primaryDevice': {
                                '__typename': 'Device',
                                'id': 'PRIVATE_DEVICE_ID',
                                'key': 'PRIVATE_DEVICE_KEY',
                                'make': 'PRIVATE_DEVICE_MAKE',
                                'model': 'PRIVATE_DEVICE_MODEL',
                                'type': 'PHONE',
                                'image': {'url': 'PRIVATE_DEVICE_URL'},
                            },
                            'pairedLines': [{'id': 'PRIVATE_PAIRED_LINE_ID'}],
                        }],
                    }],
                },
            },
        },
    }

    report = my_graphql.create_mobile_diagnostic_export(raw_usage)
    serialized_report = json.dumps(report)
    line_report = report['plans'][0]['lines'][0]

    assert report['mobile_present'] is True
    assert report['number_of_lines'] == 1
    assert report['current_cycle_fields_present'] == ['endDate', 'daysLeft']
    assert report['plans'][0]['current_usage'] == {
        'value': 1.23,
        'unit': 'TB',
        'value_present': True,
        'unit_present': True,
    }
    assert line_report['current_usage']['value'] == 123.46
    assert line_report['current_usage']['unit'] == 'MB'
    assert line_report['primary_device_fields_present'] == [
        '__typename', 'id', 'key', 'make', 'model', 'type', 'image',
    ]
    for private_value in (
        'PRIVATE_SEGMENT', 'PRIVATE_LINE_ID', 'PRIVATE_LINE_KEY', 'PRIVATE_NAME',
        '+15555550123', 'PRIVATE_DEVICE_ID', 'PRIVATE_DEVICE_KEY',
        'PRIVATE_DEVICE_MAKE', 'PRIVATE_DEVICE_MODEL', 'PRIVATE_DEVICE_URL',
        'PRIVATE_PAIRED_LINE_ID', '2030-01-31',
    ):
        assert private_value not in serialized_report


def test_create_internet_diagnostic_export_rounds_usage_and_removes_dates(my_graphql):
    raw_usage = {
        'data': {
            'accountByServiceAccountId': {
                'internet': {
                    'plan': {'name': 'PRIVATE_PLAN_NAME'},
                    'usage': {
                        'inPaidOverage': False,
                        'courtesy': {
                            'totalAllowableCourtesy': 10,
                            'usedCourtesy': 2,
                            'remainingCourtesy': 8,
                        },
                        'monthlyUsage': [{
                            'policy': 'limited',
                            'month': 11,
                            'year': 2030,
                            'startDate': '2030-11-01',
                            'endDate': '2030-11-30',
                            'daysRemaining': 5,
                            'currentUsage': {'value': 123.456, 'unit': 'GB'},
                            'allowableUsage': {'value': 1.234, 'unit': 'TB'},
                            'overage': False,
                            'overageCharge': 25,
                            'maximumOverageCharge': 100,
                            'courtesyCredit': False,
                        }],
                    },
                },
            },
        },
    }

    report = my_graphql.create_internet_diagnostic_export(raw_usage)
    serialized_report = json.dumps(report)
    month_report = report['months'][0]

    assert report['internet_present'] is True
    assert report['monthly_usage_count'] == 1
    assert month_report['current_usage']['value'] == 123.46
    assert month_report['allowable_usage']['value'] == 1.23
    assert month_report['fields_present'] == [
        'policy', 'month', 'year', 'startDate', 'endDate', 'daysRemaining',
        'currentUsage', 'allowableUsage', 'overage', 'overageCharge',
        'maximumOverageCharge', 'courtesyCredit',
    ]
    for private_value in (
        'PRIVATE_PLAN_NAME', '2030-11-01', '2030-11-30', '2030', '25',
    ):
        assert private_value not in serialized_report


def test_get_internet_and_mobile_usage_combine_sanitized_diagnostics(my_graphql):
    internet_response = MagicMock()
    internet_response.ok = True
    internet_response.json.return_value = MOCK_GRAPHQL_USAGE_RESPONSE_SUCCESS
    mobile_response = MagicMock()
    mobile_response.ok = True
    mobile_response.json.return_value = {
        'data': {
            'accountByServiceAccountId': {
                'mobile': {
                    'plans': [{
                        'type': 'UnlimitedPlan',
                        'lines': [{
                            'id': 'PRIVATE_LINE_ID',
                            'key': 'PRIVATE_LINE_KEY',
                            'nickname': 'PRIVATE_NAME',
                            'currentUsage': {'value': 1.234, 'unit': 'GB'},
                        }],
                    }],
                },
            },
        },
    }
    my_graphql.diagnostics_enabled = True

    with patch(
        "xfinity_usage.xfinity_graphql.requests.post",
        side_effect=[internet_response, mobile_response],
    ), patch("xfinity_usage.xfinity_graphql.write_mobile_diagnostics") as write_diagnostics:
        my_graphql.get_usage_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)
        my_graphql.get_mobile_usage_details_data(
            MOCK_USAGE_ADDON_OAUTH_TOKEN,
            diagnostics_enabled=True,
        )

    assert write_diagnostics.call_count == 2
    diagnostic_json = json.dumps(write_diagnostics.call_args.args[0])
    assert 'internet' in write_diagnostics.call_args.args[0]
    assert 'mobile' in write_diagnostics.call_args.args[0]
    assert 'PRIVATE_LINE_ID' not in diagnostic_json
    assert 'PRIVATE_LINE_KEY' not in diagnostic_json
    assert 'PRIVATE_NAME' not in diagnostic_json


def test_convert_raw_mobile_usage_to_website_format_keeps_zero_usage(my_graphql):
    raw_usage = {
        'data': {
            'accountByServiceAccountId': {
                'mobile': {
                    'plans': [{
                        'lines': [
                            {'key': 'line-zero', 'nickname': 'Zero', 'currentUsage': {'value': 0, 'unit': 'GB'}},
                        ],
                    }],
                },
            },
        },
    }

    result = my_graphql.convert_raw_mobile_usage_to_website_format(raw_usage)

    assert result['sensor.xfinity_mobile_usage']['state'] == 0
    assert len(result) == 2

def test_convert_raw_mobile_usage_handles_malformed_cycle_and_multiple_plans(my_graphql):
    raw_usage = {
        'data': {
            'accountByServiceAccountId': {
                'mobile': {
                    'currentCycle': [],
                    'plans': [
                        {'lines': [{'key': 'line-one', 'currentUsage': {'value': 1, 'unit': 'GB'}}]},
                        {'lines': [{'key': 'line-two', 'currentUsage': {'value': 2, 'unit': 'GB'}}]},
                    ],
                },
            },
        },
    }

    result = my_graphql.convert_raw_mobile_usage_to_website_format(raw_usage)

    assert result['sensor.xfinity_mobile_usage']['state'] == 3
    line_sensors = [sensor for entity_id, sensor in result.items() if entity_id != 'sensor.xfinity_mobile_usage']
    assert [sensor['attributes']['line_name'] for sensor in line_sensors] == ['Line 1', 'Line 2']

def test_get_mobile_usage_details_data(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        'data': {
            'accountByServiceAccountId': {
                'mobile': {
                    'plans': [{
                        'lines': [
                            {'key': 'line-one', 'nickname': 'Primary', 'currentUsage': {'value': 1.25, 'unit': 'GB'}},
                        ],
                    }],
                },
            },
        },
    }

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response) as mock_post:
        result = my_graphql.get_mobile_usage_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)

    assert result['sensor.xfinity_mobile_usage']['state'] == 1.25
    request_data = mock_post.call_args.kwargs['json']
    assert request_data['operationName'] == 'XMAccountSummary'
    assert request_data['variables'] == {}
    assert mock_post.call_args.kwargs['headers']['x-apollo-operation-name'] == 'XMAccountSummary'
    assert mock_post.call_args.kwargs['headers']['x-id-token'] == MOCK_USAGE_ADDON_OAUTH_TOKEN['id_token']
    assert 'dataLimit' in request_data['query']

def test_get_mobile_service_details_data_detects_lines(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        'data': {
            'accountByServiceAccountId': {
                'mobile': {
                    'numberOfLines': 2,
                    'pendingActivationsCount': 1,
                    'hasUnlinkedLines': False,
                    'plans': [],
                },
            },
        },
    }

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response) as mock_post:
        result = my_graphql.get_mobile_service_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)

    assert result == {
        'has_service': True,
        'number_of_lines': 2,
        'pending_activations_count': 1,
    }
    assert mock_post.call_args.kwargs['headers']['x-apollo-operation-name'] == 'XMService'
    assert mock_post.call_args.kwargs['headers']['x-apollo-operation-id'] == '6658062ef8a21b956b40bcce04ff922c84553d459754ff7b9a68c2c16ce9a2a5'

def test_get_mobile_service_details_data_detects_no_service(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        'data': {'accountByServiceAccountId': {'mobile': None}}
    }

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response):
        result = my_graphql.get_mobile_service_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)

    assert result['has_service'] is False

def test_get_mobile_service_details_data_requires_active_lines(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        'data': {
            'accountByServiceAccountId': {
                'mobile': {
                    'hasUnlinkedLines': True,
                    'numberOfLines': 0,
                    'pendingActivationsCount': 1,
                    'plans': [],
                },
            },
        },
    }

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response):
        result = my_graphql.get_mobile_service_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)

    assert result == {
        'has_service': False,
        'number_of_lines': 0,
        'pending_activations_count': 1,
    }