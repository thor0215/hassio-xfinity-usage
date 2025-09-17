import pytest
import base64
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from xfinity_usage.xfinity_token import XfinityOAuthToken
import uuid

@pytest.fixture
def token_instance():
    # Patch file operations and environment for safe testing
    with patch('xfinity_usage.xfinity_token.read_token_file_data', return_value={}), \
         patch('xfinity_usage.xfinity_token.write_token_file_data'), \
         patch('xfinity_usage.xfinity_token.decrypt_message', return_value='dummy_secret'), \
         patch('xfinity_usage.xfinity_token.encrypt_message', return_value=b'encrypted'), \
         patch('xfinity_usage.xfinity_token.logger'):
        yield XfinityOAuthToken()

def test_generate_code_verifier_and_challenge(token_instance):
    verifier = token_instance.generate_code_verifier()
    assert isinstance(verifier, str)
    assert 43 <= len(verifier) <= 64  # PKCE spec

    challenge = token_instance.generate_code_challenge(verifier)
    assert isinstance(challenge, str)
    # Should be base64-url safe, no '=' padding
    assert '=' not in challenge

def test_generate_state(token_instance):
    state = token_instance.generate_state()
    assert isinstance(state, str)
    assert len(state) == 22
    assert all(c.isalnum() for c in state)

def test_generate_activity_id(token_instance):
    activity_id = token_instance.generate_activity_id()
    # Should be a valid UUID1 string
    uuid_obj = uuid.UUID(activity_id)
    assert uuid_obj.version == 1

def test_is_token_expired_true(token_instance):
    with patch('xfinity_usage.xfinity_token.get_current_unix_epoch', return_value=1000):
        token_instance.OAUTH_TOKEN = {'expires_at': 1200}
        assert token_instance.is_token_expired() is True

def test_is_token_expired_false(token_instance):
    with patch('xfinity_usage.xfinity_token.get_current_unix_epoch', return_value=1000):
        token_instance.OAUTH_TOKEN = {'expires_at': 2000}
        assert token_instance.is_token_expired() is False

def test_read_token_code_file_data_returns_token_when_file_exists(tmp_path, token_instance):
    # Prepare a fake .code.json file with valid JSON content
    code_file = tmp_path / ".code.json"
    data = {"activity_id": "test-activity", "code_verifier": "test-verifier"}
    code_file.write_text(json.dumps(data))
    with patch('os.path.isfile', return_value=True), \
            patch('os.path.getsize', return_value=1), \
            patch('xfinity_usage.xfinity_token._OAUTH_CODE_TOKEN_FILE', str(code_file)):
        result = token_instance.read_token_code_file_data()
        assert result == data

def test_read_token_code_file_data_returns_empty_when_file_missing(token_instance):
    with patch('os.path.isfile', return_value=False), \
            patch('os.path.getsize', return_value=0):
        result = token_instance.read_token_code_file_data()
        assert result == {}

def test_read_token_code_file_data_returns_empty_when_file_empty(tmp_path, token_instance):
    code_file = tmp_path / ".code.json"
    code_file.write_text("")
    with patch('os.path.isfile', return_value=True), \
            patch('os.path.getsize', return_value=0), \
            patch('xfinity_usage.xfinity_token._OAUTH_CODE_TOKEN_FILE', str(code_file)):
        result = token_instance.read_token_code_file_data()
        assert result == {}

def test_read_token_code_file_data_handles_invalid_json(tmp_path, token_instance):
    code_file = tmp_path / ".code.json"
    code_file.write_text("{invalid json}")
    with patch('os.path.isfile', return_value=True), \
            patch('os.path.getsize', return_value=1), \
            patch('xfinity_usage.xfinity_token._OAUTH_CODE_TOKEN_FILE', str(code_file)):
        # Should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            token_instance.read_token_code_file_data()

def test_write_token_code_file_data(tmp_path, token_instance):
    code_file = tmp_path / ".code.json"
    with patch('os.path.exists', return_value=True), \
         patch('xfinity_usage.xfinity_token._OAUTH_CODE_TOKEN_FILE', str(code_file)):
        token_instance.write_token_code_file_data({"foo": "bar"})
        assert json.loads(code_file.read_text()) == {"foo": "bar"}

def test_delete_token_code_file_data(tmp_path, token_instance):
    code_file = tmp_path / ".code.json"
    code_file.write_text("{}")
    with patch('os.path.isfile', return_value=True), \
         patch('os.path.getsize', return_value=1), \
         patch('xfinity_usage.xfinity_token._OAUTH_CODE_TOKEN_FILE', str(code_file)):
        token_instance.delete_token_code_file_data()
        assert not code_file.exists()

def test_handle_requests_exception(token_instance):
    # Just ensure it calls the global handler
    with patch('xfinity_usage.xfinity_token.handle_requests_exception') as mock_handler:
        token_instance.handle_requests_exception(Exception("err"))
        mock_handler.assert_called()

def test_oauth_update_tokens(token_instance):
    # Patch jwt and file writing
    fake_token_response = {
        'id_token': 'header.payload.signature',
        'refresh_token': 'refresh',
        'access_token': 'access',
        'activity_id': 'aid'
    }
    jwt_token = {
        'exp': 1234567890,
        'cust_guid': 'guid',
        'iss': 'xerxeslite-prod',
        'aud': 'xfinity-android-application'
    }
    with patch('xfinity_usage.xfinity_token.jwt.get_unverified_header', return_value={'jku': None, 'alg': None}), \
         patch('xfinity_usage.xfinity_token.jwt.decode', return_value=jwt_token), \
         patch('xfinity_usage.xfinity_token.write_token_file_data'), \
         patch('xfinity_usage.xfinity_token.encrypt_message', return_value=b'encrypted'), \
         patch('xfinity_usage.xfinity_token.logger'):
        result = token_instance.oauth_update_tokens(fake_token_response.copy())
        assert result['expires_at'] == jwt_token['exp']
        assert result['customer_guid'] == jwt_token['cust_guid']
        assert 'encrypted_refresh_token' in result
        assert isinstance(result['encrypted_refresh_token'], str)

