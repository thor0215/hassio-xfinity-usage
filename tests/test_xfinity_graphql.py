import pytest
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


def test_convert_raw_plan_to_website_format(my_graphql):
    raw_plan = MOCK_GRAPHQL_PLAN_RESPONSE_SUCCESS['data']['accountByServiceAccountId']['internet']['plan']
    converted_plan = my_graphql.convert_raw_plan_to_website_format(raw_plan)
    assert converted_plan == {
        'downloadSpeed': raw_plan['downloadSpeed']['value'],
        'uploadSpeed': -1
    }

def test_get_gateway_details_data(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = MOCK_GRAPHQL_GATEWAY_RESPONSE_SUCCESS
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response):
        result = my_graphql.get_gateway_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)
        assert result == MOCK_GRAPHQL_GATEWAY_RESPONSE_SUCCESS['data']['user']['account']['modem']

def test_get_plan_details_data(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = MOCK_GRAPHQL_PLAN_RESPONSE_SUCCESS
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response):
        result = my_graphql.get_plan_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)
        assert result == my_graphql.convert_raw_plan_to_website_format(MOCK_GRAPHQL_PLAN_RESPONSE_SUCCESS['data']['accountByServiceAccountId']['internet']['plan'])

def test_get_usage_details_data(my_graphql):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = MOCK_GRAPHQL_USAGE_RESPONSE_SUCCESS
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_graphql.requests.post", return_value=mock_response):
        result = my_graphql.get_usage_details_data(MOCK_USAGE_ADDON_OAUTH_TOKEN)
        assert result == my_graphql.convert_raw_usage_to_website_format(MOCK_GRAPHQL_USAGE_RESPONSE_SUCCESS['data']['accountByServiceAccountId']['internet']['usage'])