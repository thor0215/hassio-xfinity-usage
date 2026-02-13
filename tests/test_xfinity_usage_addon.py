import pytest
import sys
from unittest.mock import MagicMock, patch, DEFAULT
from requests import ConnectionError
from xfinity_usage.xfinity_helper import *
from xfinity_usage.xfinity_token import XfinityOAuthToken
from xfinity_usage.xfinity_graphql import XfinityGraphQL
from xfinity_usage.xfinity_my_account import XfinityMyAccount

# Assume the main function and constants are in a file named `xfinity_usage_addon.py`
from xfinity_usage.xfinity_usage_addon import main, exit_code

# The target for patching depends on where the object is imported.
# In this case, most objects are imported into `xfinity_usage_addon`.
MODULE_PATH = 'xfinity_usage'

# Fixture to mock module-level constants and environment variables
@pytest.fixture(autouse=True)
def mock_module_globals():
    """Fixture to patch global variables defined in the module."""
    with patch.dict('os.environ', {}, clear=True), \
         patch(f'{MODULE_PATH}.xfinity_usage_addon._BYPASS', 0), \
         patch(f'{MODULE_PATH}.xfinity_usage_addon._POLLING_RATE', 0.0), \
         patch(f'{MODULE_PATH}.xfinity_usage_addon._CLEAR_TOKEN', False):
        yield

# Fixtures to patch the various classes and helper functions
@pytest.fixture
def mock_xfinity_token():
    """Fixture to mock the XfinityOAuthToken class and its instance."""
    with patch(XfinityOAuthToken) as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.OAUTH_TOKEN = {'refresh_token': 'refresh_123'}
        mock_instance.XFINITY_CODE_PLACEHOLDER = "CODE PLACEHOLDER"
        mock_instance.is_token_expired.return_value = False
        mock_instance.CLEAR_TOKEN = False
        mock_instance.OAUTH_CODE_FLOW = False
        yield mock_instance

@pytest.fixture
def mock_my_account():
    """Fixture to mock XfinityMyAccount methods."""
    with patch(f'{MODULE_PATH}.xfinity_my_account.XfinityMyAccount') as mock_ma_cls:
        mock_instance = mock_ma_cls.return_value
        mock_instance.oauth_refresh_tokens.return_value = {'access_token': 'test_token'}
        mock_instance.get_gateway_details_data.return_value = {'gateway_data': 'mocked'}
        mock_instance.get_plan_details_data.return_value = {'plan_data': 'mocked'}
        mock_instance.get_usage_details_data.return_value = {'usage_data': 'mocked'}
        yield mock_instance

@pytest.fixture
def mock_graphql():
    """Fixture to mock XfinityGraphQL methods."""
    with patch(f'{MODULE_PATH}.xfinity_graphql.XfinityGraphQL') as mock_gql_cls:
        mock_instance = mock_gql_cls.return_value
        mock_instance.get_gateway_details_data.return_value = {}
        mock_instance.get_plan_details_data.return_value = {}
        mock_instance.get_usage_details_data.return_value = {'usage_data': 'mocked'}
        yield mock_instance

@pytest.fixture
def mock_mqtt():
    """Fixture to mock MQTT dependencies."""
    with patch(f'{MODULE_PATH}.xfinity_mqtt.is_mqtt_available', return_value=True), \
         patch(f'{MODULE_PATH}.xfinity_mqtt.XfinityMqtt') as mock_mqtt_cls:
        yield mock_mqtt_cls

# Fixture to patch helper functions, using DEFAULT to expose them
@pytest.fixture
def mock_helper_functions():
    """Fixture to patch various helper functions from xfinity_helper."""
    with patch(is_hassio), \
         patch(f'{MODULE_PATH}.xfinity_helper.get_addon_options'), \
         patch(f'{MODULE_PATH}.xfinity_helper.stop_addon'), \
         patch(f'{MODULE_PATH}.xfinity_helper.restart_addon'), \
         patch(f'{MODULE_PATH}.xfinity_helper.update_addon_options'), \
         patch(f'{MODULE_PATH}.xfinity_helper.clear_token'), \
         patch(f'{MODULE_PATH}.xfinity_helper.profile_cleanup'), \
         patch(f'{MODULE_PATH}.xfinity_helper.update_ha_sensor_on_startup'), \
         patch(f'{MODULE_PATH}.xfinity_helper.update_ha_sensor'), \
         patch(f'{MODULE_PATH}.xfinity_helper.update_sensor_file'), \
         patch(f'{MODULE_PATH}.xfinity_helper.process_usage_json', return_value={'usage_data': 'mocked'}):
        yield {
            'is_hassio': is_hassio, 'get_addon_options': get_addon_options,
            'stop_addon': stop_addon, 'restart_addon': restart_addon,
            'update_addon_options': update_addon_options, 'clear_token': clear_token,
            'profile_cleanup': profile_cleanup, 'update_ha_sensor': update_ha_sensor,
            'update_sensor_file': update_sensor_file, 'process_usage_json': process_usage_json
        }

# ==============================================================================
# Tests for main()
# ==============================================================================

@patch('sys.exit')
@patch('xfinity_usage.xfinity_helper.is_hassio', return_value=True)
def test_main_oauth_code_flow_hassio(mock_is_hassio, mock_exit, mock_xfinity_token, mock_helper_functions):
    """Test the OAuth code flow branch for a Hass.io environment."""
    mock_xfinity_token.OAUTH_CODE_FLOW = True
    mock_helper_functions['get_addon_options'].return_value = {}

    with pytest.raises(SystemExit) as excinfo:
        main()

    # Assert the exit code is what we expect
    assert excinfo.value.code == exit_code.TOKEN_CODE.value
    
    # Assertions
    mock_helper_functions['get_addon_options'].assert_called_once()
    mock_options = mock_helper_functions['get_addon_options'].return_value
    assert mock_options['xfinity_code'] == mock_xfinity_token.XFINITY_CODE_PLACEHOLDER
    mock_helper_functions['update_addon_options'].assert_called_once_with(mock_options)
    mock_helper_functions['stop_addon'].assert_called_once()
    mock_exit.assert_called_once_with(exit_code.TOKEN_CODE.value)

@patch('sys.exit')
@patch(f'{MODULE_PATH}.is_hassio', return_value=False)
def test_main_oauth_code_flow_not_hassio(mock_is_hassio, mock_exit, mock_xfinity_token, mock_helper_functions):
    """Test the OAuth code flow branch for a non-Hass.io environment."""
    mock_xfinity_token.OAUTH_CODE_FLOW = True

    main()

    # Assertions
    mock_exit.assert_called_once_with(exit_code.TOKEN_CODE.value)
    mock_helper_functions['stop_addon'].assert_not_called()


@patch('sys.exit')
@patch(f'{MODULE_PATH}.is_mqtt_available', return_value=True)
@patch(f'{MODULE_PATH}._BYPASS', 0)
def test_main_successful_run_mqtt(mock_is_mqtt, mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_mqtt, mock_helper_functions):
    """Test a successful run with MQTT enabled and using MyAccount APIs."""
    main()
    
    # Assertions for MyAccount path
    mock_my_account.oauth_refresh_tokens.assert_called_once()
    mock_my_account.get_usage_details_data.assert_called_once()
    mock_my_account.get_plan_details_data.assert_called_once()
    mock_my_account.get_gateway_details_data.assert_called_once()
    mock_graphql.get_usage_details_data.assert_not_called()

    # Assertions for MQTT publishing
    mock_mqtt.return_value.set_mqtt_device_details.assert_called_once()
    mock_mqtt.return_value.set_mqtt_state.assert_called_once()
    mock_mqtt.return_value.publish_mqtt.assert_called_once()
    
    # Assertions for exit
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)


@patch('sys.exit')
@patch(f'{MODULE_PATH}.is_mqtt_available', return_value=False)
@patch(f'{MODULE_PATH}._BYPASS', 0)
def test_main_successful_run_graphql_fallback(mock_is_mqtt, mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    """Test a successful run using the GraphQL fallback path."""
    # Simulate MyAccount failing to return data
    mock_my_account.get_usage_details_data.return_value = None
    mock_my_account.get_plan_details_data.return_value = None

    main()

    # Assertions for GraphQL fallback
    mock_my_account.get_usage_details_data.assert_called_once()
    mock_graphql.get_usage_details_data.assert_called_once()

    # Assertions for data updates
    mock_helper_functions['update_ha_sensor'].assert_called_once()
    mock_helper_functions['update_sensor_file'].assert_called_once()

    # Assertions for exit
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)


@patch('sys.exit')
@patch(f'{MODULE_PATH}._BYPASS', 0)
def test_main_single_run_bypass(mock_exit, mock_xfinity_token, mock_my_account, mock_helper_functions):
    """Test that the script exits immediately when BYPASS is 0 or POLLING_RATE is 0."""
    main()

    mock_my_account.get_usage_details_data.assert_called_once()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)


@patch(f'{MODULE_PATH}.sleep', side_effect=[None, StopIteration])
@patch(f'{MODULE_PATH}._BYPASS', 1)
@patch(f'{MODULE_PATH}._POLLING_RATE', 30.0)
def test_main_with_polling_loop(mock_sleep, mock_xfinity_token, mock_my_account, mock_helper_functions):
    """Test that the main loop sleeps and continues when polling is enabled."""
    with pytest.raises(StopIteration):
        main()

    # Assert that sleep was called with the correct polling rate
    mock_sleep.assert_called_once_with(30.0)
    # Assert that the main processing logic was executed at least once
    mock_my_account.get_usage_details_data.assert_called_once()


@patch(f'{MODULE_PATH}.XfinityMyAccount')
@patch(f'{MODULE_PATH}.XfinityOAuthToken')
def test_main_tenacity_retry(mock_token_cls, mock_my_account_cls, mock_helper_functions):
    """Test that the tenacity retry decorator handles ConnectionError."""
    mock_my_account_cls.return_value.oauth_refresh_tokens.side_effect = ConnectionError("Mocked ConnectionError")
    
    with pytest.raises(ConnectionError):
        main()

    # The mock will be called multiple times by the retry mechanism
    assert mock_my_account_cls.return_value.oauth_refresh_tokens.call_count == 6


@patch('sys.exit')
@patch(f'{MODULE_PATH}.clear_token')
@patch(f'{MODULE_PATH}._CLEAR_TOKEN', True)
def test_main_initial_clear_token_env(mock_clear_token, mock_exit, mock_xfinity_token, mock_helper_functions):
    """Test that `clear_token` is called if _CLEAR_TOKEN is true from environment variable."""
    mock_xfinity_token.OAUTH_TOKEN = {}
    main()

    mock_clear_token.assert_called_once_with(mock_helper_functions['get_addon_options'].return_value)
    mock_exit.assert_not_called()


@patch('sys.exit')
@patch(f'{MODULE_PATH}.is_hassio', return_value=True)
@patch(f'{MODULE_PATH}._BYPASS', 0)
def test_main_token_refresh_hassio(mock_is_hassio, mock_exit, mock_xfinity_token, mock_helper_functions):
    """Test token refresh handling in Hass.io when refresh_token is missing from options."""
    mock_xfinity_token.OAUTH_TOKEN = {'refresh_token': 'new_refresh'}
    mock_helper_functions['get_addon_options'].return_value = {}

    main()

    mock_helper_functions['update_addon_options'].assert_called_once()
    mock_helper_functions['restart_addon'].assert_called_once()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)

@patch('sys.exit')
@patch(f'{MODULE_PATH}.is_hassio', return_value=False)
@patch(f'{MODULE_PATH}._BYPASS', 0)
def test_main_token_refresh_not_hassio(mock_is_hassio, mock_exit, mock_xfinity_token, mock_helper_functions):
    """Test token refresh handling outside Hass.io."""
    mock_xfinity_token.OAUTH_TOKEN = {'refresh_token': 'new_refresh'}
    main()

    mock_helper_functions['update_addon_options'].assert_not_called()
    mock_helper_functions['restart_addon'].assert_not_called()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)
