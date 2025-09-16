import pytest
from unittest.mock import patch, MagicMock
from xfinity_usage.xfinity_my_account import XfinityMyAccount
from const import *

@pytest.fixture
def my_account():
    account = XfinityMyAccount()
    account.OAUTH_TOKEN = MOCK_MY_ACCOUNT_OAUTH_TOKEN
    return account

@patch("xfinity_usage.xfinity_my_account._EXTRA_HEADERS", MOCK_EXTRA_HEADERS)
@patch("xfinity_usage.xfinity_my_account.OAUTH_PROXY", MOCK_OAUTH_PROXY)
@patch("xfinity_usage.xfinity_my_account.OAUTH_CERT_VERIFY", MOCK_OAUTH_CERT_VERIFY)
@patch("xfinity_usage.xfinity_my_account.REQUESTS_TIMEOUT", MOCK_REQUESTS_TIMEOUT)
@patch("xfinity_usage.xfinity_my_account._USAGE_URL", MOCK_USAGE_URL)

def test_get_usage_details_data_success(my_account):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = MOCK_USAGE_RESPONSE_SUCCESS
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        result = my_account.get_usage_details_data()
        assert result == MOCK_USAGE_RESPONSE_SUCCESS
        assert my_account.usage_details == MOCK_USAGE_RESPONSE_SUCCESS

def test_get_usage_details_data_retry_and_fail(my_account):
    # Simulate two failed attempts (no usageMonths), then a successful one
    mock_response_fail = MagicMock()
    mock_response_fail.ok = True
    mock_response_fail.json.return_value = {"usageMonths": []}
    mock_response_fail.status_code = 200
    mock_response_fail.content = b"{}"

    mock_response_success = MagicMock()
    mock_response_success.ok = True
    mock_response_success.json.return_value = MOCK_USAGE_RESPONSE_SUCCESS
    mock_response_success.status_code = 200
    mock_response_success.content = b"{}"

    #with patch("xfinity_usage.xfinity_my_account.requests.get", side_effect=[mock_response_fail, mock_response_fail, mock_response_success]):
    with patch("xfinity_usage.xfinity_my_account.requests.get", side_effect=[mock_response_fail, mock_response_fail, mock_response_success]):
        with patch("xfinity_usage.xfinity_my_account.sleep"):
            result = my_account.get_usage_details_data()
            assert result == MOCK_USAGE_RESPONSE_SUCCESS
            #assert my_account.usage_details == MOCK_USAGE_RESPONSE_SUCCESS

def test_get_usage_details_data_404_unlimited_plan(my_account):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.json.return_value = {"message": "Plan does not support the usage meter feature."}
    mock_response.status_code = 404
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        result = my_account.get_usage_details_data()
        assert result == {}

def test_get_usage_details_data_exception_handling(my_account):
    # Simulate requests.get raising an exception
    with patch("xfinity_usage.xfinity_my_account.requests.get", side_effect=Exception("Network error")):
        with patch.object(my_account, "handle_requests_exception") as mock_handle:
            my_account.get_usage_details_data()
            assert mock_handle.called

def test_get_plan_details_data_success(my_account):
    mock_plan_response = {
        "tier": [
            {"name": "Performance Pro", "speed": "200Mbps"}
        ]
    }
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = MOCK_PLAN_RESPONSE_SUCCESS
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        result = my_account.get_plan_details_data()
        assert result == MOCK_PLAN_RESPONSE_SUCCESS["tier"]
        assert my_account.plan_details == MOCK_PLAN_RESPONSE_SUCCESS["tier"]

def test_get_plan_details_data_no_tier(my_account):
    mock_plan_response = {
        "notier": []
    }
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = mock_plan_response
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        with patch("xfinity_usage.xfinity_my_account.logger") as mock_logger:
            result = my_account.get_plan_details_data()
            assert result == {}
            assert my_account.plan_details == {}
            assert mock_logger.error.called

def test_get_plan_details_data_empty_tier(my_account):
    mock_plan_response = {
        "tier": []
    }
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = mock_plan_response
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        with patch("xfinity_usage.xfinity_my_account.logger") as mock_logger:
            result = my_account.get_plan_details_data()
            assert result == {}
            assert my_account.plan_details == {}
            assert mock_logger.error.called

def test_get_plan_details_data_not_ok(my_account):
    mock_plan_response = {
        "tier": [
            {"name": "Performance Pro", "speed": "200Mbps"}
        ]
    }
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.json.return_value = mock_plan_response
    mock_response.status_code = 500
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        with patch("xfinity_usage.xfinity_my_account.logger") as mock_logger:
            result = my_account.get_plan_details_data()
            assert result == {}
            assert my_account.plan_details == {}
            assert mock_logger.error.called

def test_get_plan_details_data_exception_handling(my_account):
    with patch("xfinity_usage.xfinity_my_account.requests.get", side_effect=Exception("Network error")):
        with patch.object(my_account, "handle_requests_exception") as mock_handle:
            my_account.get_plan_details_data()
            assert mock_handle.called

def test_get_gateway_details_data_success(my_account):
    mock_response_json = MOCK_GATEWAY_RESPONSE_SUCCESS
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = mock_response_json
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        with patch("xfinity_usage.xfinity_my_account.logger") as mock_logger:
            result = my_account.get_gateway_details_data()
            assert result["mac"] == "44:A5:6E:B9:E3:60"
            assert result["macAddress"] == "44:A5:6E:B9:E3:60"
            assert my_account.gateway_details == result
            assert mock_logger.info.called

def test_get_gateway_details_data_no_devices(my_account):
    mock_response_json = {"devices": []}
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = mock_response_json
    mock_response.status_code = 200
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        with patch("xfinity_usage.xfinity_my_account.logger") as mock_logger:
            result = my_account.get_gateway_details_data()
            assert result == {}
            assert my_account.gateway_details == {}
            assert mock_logger.error.called

def test_get_gateway_details_data_not_ok(my_account):
    mock_response_json = {"devices": [{"mac": "AA:BB:CC:DD:EE:FF"}]}
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.json.return_value = mock_response_json
    mock_response.status_code = 500
    mock_response.content = b"{}"

    with patch("xfinity_usage.xfinity_my_account.requests.get", return_value=mock_response):
        with patch("xfinity_usage.xfinity_my_account.logger") as mock_logger:
            result = my_account.get_gateway_details_data()
            assert result == {}
            assert my_account.gateway_details == {}
            assert mock_logger.error.called

def test_get_gateway_details_data_exception_handling(my_account):
    with patch("xfinity_usage.xfinity_my_account.requests.get", side_effect=Exception("Network error")):
        with patch.object(my_account, "handle_requests_exception") as mock_handle:
            my_account.get_gateway_details_data()
            assert mock_handle.called



