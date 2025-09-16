import pytest
from unittest.mock import patch, MagicMock
from xfinity_usage.xfinity_my_account import XfinityMyAccount
from const import *

@pytest.fixture
def my_account():
    account = XfinityMyAccount()
    account.OAUTH_TOKEN = {'token_type': 'Bearer', 'access_token': 'test-CVQQARgCIoABA77dtV5gqFecrjFkx0FrP-nHh_I74m03qe5RJlIt269PG8uMnQNH1vAkfwgWaNufD3h1bNZBYv243DhXe0WL73JmfWw9B-9xqpE78IhE3o8f9JYHFxAh2G3fVrcUOdayTChOOPTGBDfWj-Yn5l52QBtuUJj62MyjdY3PxKUXrhUqEKFDR1O9tkhdY3qSpxONcPAyUQoodXJuOmNpbWE6b2F1dGg6djI6YWNjZXNzLXRva2VuOmVuY3J5cHQ6MRIldXJuOmNpbWE6b2F1dGg6djI6YWNjZXNzLXRva2VuOnNpZ246MTrQBWWBGerYY8gwcEDpBUA-hmutjHVOEKRi8IKBHZAuzTAo1MISeNuvLovmTLnIebfThJ8Ovu60bmT9wOQYQpvfTATiomBKwQZyvRL67zQf5SDfpSvncyUPZtjVLocc7qO_gPtP0obI0D6HuWLR4PYLVkYDU2_dBsZ8avrAk4oM5t9hu1kY5UD_riFu3QApoDTi6xO5CTBPmC7cmdc1To7yosvb96qOuShDMiDBvOK_oQdY8CcZiqdCCr7DVCKrzBRQwyKb-BFRybNb88TsLHUs2rpw-VKoPCDpGd0b4YI2RM-nK_wTxlwlciqqTbCyIaIA6L2OqKsxkrQZO8vqPY-LDFaz0ZlzCL-8n3t3Pj8Llmm-Vf35Q0kbRpYWvDXnXseuSmj5MEBk_w5ZoBvIbN_uWYzZzG8uD6Wf2eikD5xxSn4UX6AUe7VGbygFWGMLD0aXlPYV_t5S719P0g9Qn6iMD7AnGZKTQnVvY1xkSvsDrz1qcCbYBfbnfNHmwb1HcwFx5fDa8gCwZtiNn4tahguyYXbwUB0IXoHebxOHyA28NFL0WNYQ3UxTsEtEgpWaNuM-NN_agIyCu6QCGA9wbhnB-_EaUOI41jaiPCOmRo1bBisX1kUgbgF8_OssDfZ1eq_d3LJJmr8BYjq9_LmMKUENWJZw2LY2WCLJrAMPONNNp9j3FSP4SKMZF8ixARluSbxhcQ3uUn4jozkpYbSPNtdOc2bgDiTCk2cS8Ojrc6f086szb_D5MzZ4bChLdpXBN8P73UZSkzYHXXj_f7Rqsb9gnl2S0LeyNTVkR74Wn3OIrj1UGYp00co6Ndaov3SujrK9EGGV9bIsJjQ-JjDZeZGrJBs3RoIRqiBonOywF7VY6hoc94NWru_pEZG0npEHFlyHdnQgcHfm47xaJoQZZGZOeQ17NscdDDyeZNBh72auQVr_Q0TW1Fnc2Fl69ax8crulMA**'}
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
