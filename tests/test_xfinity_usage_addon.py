import pytest
from contextlib import ExitStack
from unittest.mock import patch
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
ADDON_MODULE = f'{MODULE_PATH}.xfinity_usage_addon'

# Fixture to mock module-level constants and environment variables
@pytest.fixture(autouse=True)
def mock_module_globals():
    """Fixture to patch global variables defined in the module."""
    with patch.dict('os.environ', {}, clear=True), \
            patch(f'{ADDON_MODULE}._BYPASS', 0), \
            patch(f'{ADDON_MODULE}._POLLING_RATE', 0.0), \
            patch(f'{ADDON_MODULE}._CLEAR_TOKEN', False):
        yield

# Fixtures to patch the various classes and helper functions
@pytest.fixture
def mock_xfinity_token():
    """Fixture to mock the XfinityOAuthToken class and its instance."""
    with patch(f'{ADDON_MODULE}.XfinityOAuthToken') as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.OAUTH_TOKEN = {
            'token_type': 'Bearer',
            'access_token': 'access_123',
            'id_token': 'id_123',
            'refresh_token': 'refresh_123',
        }
        mock_instance.XFINITY_CODE_PLACEHOLDER = "CODE PLACEHOLDER"
        mock_instance.is_token_expired.return_value = False
        mock_instance.CLEAR_TOKEN = False
        mock_instance.OAUTH_CODE_FLOW = False
        yield mock_instance

@pytest.fixture
def mock_my_account():
    """Fixture to mock XfinityMyAccount methods."""
    with patch(f'{ADDON_MODULE}.XfinityMyAccount') as mock_ma_cls:
        mock_instance = mock_ma_cls.return_value
        mock_instance.oauth_refresh_tokens.return_value = {'access_token': 'test_token'}
        mock_instance.get_gateway_details_data.return_value = {'gateway_data': 'mocked'}
        mock_instance.get_plan_details_data.return_value = {
            'tierOfService': 'XI Superfast',
            'downloadSpeed': 800,
            'uploadSpeed': 35,
        }
        mock_instance.get_usage_details_data.return_value = {'usage_data': 'mocked'}
        yield mock_instance

@pytest.fixture
def mock_graphql():
    """Fixture to mock XfinityGraphQL methods."""
    with patch(f'{ADDON_MODULE}.XfinityGraphQL') as mock_gql_cls:
        mock_instance = mock_gql_cls.return_value
        mock_instance.get_gateway_details_data.return_value = {'gateway_data': 'graphql'}
        mock_instance.get_plan_details_data.return_value = {
            'service_available': True,
            'planName': 'XI Superfast',
            'downloadSpeed': 800,
            'uploadSpeed': 35,
        }
        mock_instance.get_usage_details_data.return_value = {'usage_data': 'mocked'}
        mock_instance.get_mobile_usage_details_data.return_value = {}
        mock_instance.get_mobile_service_details_data.return_value = {'has_service': False}
        mock_instance.convert_raw_plan_to_website_format.return_value = {
            'service_available': True,
            'planName': 'XI Superfast',
            'downloadSpeed': 800,
            'uploadSpeed': 35,
        }
        yield mock_instance

@pytest.fixture
def mock_mqtt():
    """Fixture to mock MQTT dependencies."""
    with patch(f'{ADDON_MODULE}.is_mqtt_available', return_value=True), \
         patch(f'{ADDON_MODULE}.XfinityMqtt') as mock_mqtt_cls:
        yield mock_mqtt_cls

# Fixture to patch helper functions, using DEFAULT to expose them
@pytest.fixture
def mock_helper_functions():
    """Fixture to patch various helper functions from xfinity_helper."""
    names = (
        'is_hassio', 'get_addon_options', 'stop_addon', 'restart_addon',
        'update_addon_options', 'clear_token', 'profile_cleanup',
        'update_ha_sensor_on_startup', 'update_ha_sensor', 'update_sensor_file',
        'update_ha_mobile_sensors', 'process_usage_json',
    )
    with ExitStack() as stack:
        mocks = {
            name: stack.enter_context(patch(f'{ADDON_MODULE}.{name}'))
            for name in names
        }
        mocks['get_addon_options'].return_value = {}
        mocks['process_usage_json'].return_value = {'usage_data': 'mocked'}
        yield mocks

# ==============================================================================
# Tests for main()
# ==============================================================================

@patch('builtins.exit', side_effect=SystemExit(exit_code.TOKEN_CODE.value))
@patch(f'{ADDON_MODULE}.is_hassio', return_value=True)
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

@patch('builtins.exit', side_effect=SystemExit(exit_code.TOKEN_CODE.value))
@patch(f'{ADDON_MODULE}.is_hassio', return_value=False)
def test_main_oauth_code_flow_not_hassio(mock_is_hassio, mock_exit, mock_xfinity_token, mock_helper_functions):
    """Test the OAuth code flow branch for a non-Hass.io environment."""
    mock_xfinity_token.OAUTH_CODE_FLOW = True

    with pytest.raises(SystemExit) as excinfo:
        main()

    # Assertions
    assert excinfo.value.code == exit_code.TOKEN_CODE.value
    mock_exit.assert_called_once_with(exit_code.TOKEN_CODE.value)
    mock_helper_functions['stop_addon'].assert_not_called()


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}.is_mqtt_available', return_value=True)
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_successful_run_mqtt(mock_is_mqtt, mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_mqtt, mock_helper_functions):
    """Test a successful run using GraphQL as the preferred data source."""
    events = []
    mock_graphql.get_plan_details_data.side_effect = lambda *_: events.append('service_check') or {
        'service_available': True,
        'planName': 'XI Superfast',
        'downloadSpeed': 800,
        'uploadSpeed': 35,
    }
    mock_graphql.get_gateway_details_data.side_effect = lambda *_: events.append('gateway') or {'gateway_data': 'graphql'}
    mock_graphql.get_usage_details_data.side_effect = lambda *_: events.append('usage') or {'usage_data': 'mocked'}

    with patch(f'{ADDON_MODULE}.logger.info', side_effect=lambda message, *args, **kwargs: events.append(message)):
        main()

    assert events.index('service_check') < events.index("Xfinity Internet service detected")
    assert events.index("Xfinity Internet service detected") < events.index("Internet plan details retrieved")
    assert events.index("Internet plan details retrieved") < events.index('gateway')
    assert events.index("Xfinity Internet service detected") < events.index('usage')
    
    mock_my_account.oauth_refresh_tokens.assert_not_called()
    mock_my_account.get_usage_details_data.assert_not_called()
    mock_my_account.get_plan_details_data.assert_not_called()
    mock_my_account.get_gateway_details_data.assert_not_called()
    mock_graphql.get_plan_details_data.assert_called_once()
    mock_graphql.get_usage_details_data.assert_called_once()
    mock_graphql.get_gateway_details_data.assert_called_once()

    # Assertions for MQTT publishing
    mock_mqtt.return_value.set_mqtt_device_details.assert_called_once()
    mock_mqtt.return_value.set_mqtt_state.assert_called_once()
    mock_mqtt.return_value.publish_mqtt.assert_called_once()
    
    # Assertions for exit
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}.is_mqtt_available', return_value=False)
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_successful_run_graphql_fallback(mock_is_mqtt, mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    """Test REST fallback when GraphQL does not return Internet data."""
    mock_graphql.get_plan_details_data.return_value = None
    mock_graphql.get_usage_details_data.return_value = {}
    mock_graphql.get_gateway_details_data.return_value = {}

    main()

    mock_my_account.oauth_refresh_tokens.assert_called_once()
    mock_my_account.get_plan_details_data.assert_called_once()
    mock_my_account.get_usage_details_data.assert_called_once()
    mock_my_account.get_gateway_details_data.assert_called_once()
    mock_graphql.get_usage_details_data.assert_called_once()
    mock_graphql.get_gateway_details_data.assert_called_once()

    # Assertions for data updates
    mock_helper_functions['update_ha_sensor'].assert_called_once()
    mock_helper_functions['update_sensor_file'].assert_called_once()

    # Assertions for exit
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)

@patch('builtins.exit')
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_uses_rest_only_for_missing_graphql_usage(mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    mock_graphql.get_usage_details_data.return_value = {}

    main()

    mock_my_account.oauth_refresh_tokens.assert_called_once()
    mock_my_account.get_usage_details_data.assert_called_once()
    mock_my_account.get_plan_details_data.assert_not_called()
    mock_my_account.get_gateway_details_data.assert_not_called()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)

@patch('builtins.exit')
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_checks_internet_before_rest_plan_enrichment(mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    events = []
    mock_graphql.get_plan_details_data.return_value = {
        'service_available': True,
        'planName': '',
        'downloadSpeed': -1,
        'uploadSpeed': -1,
    }
    mock_my_account.get_plan_details_data.side_effect = lambda: events.append('rest_plan') or {
        'tierOfService': 'XI Superfast',
        'downloadSpeed': 800,
        'uploadSpeed': 35,
    }

    with patch(f'{ADDON_MODULE}.logger.info', side_effect=lambda message, *args, **kwargs: events.append(message)):
        main()

    assert events.index("Xfinity Internet service detected") < events.index('rest_plan')
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)

@patch('builtins.exit')
@patch(f'{ADDON_MODULE}.is_mqtt_available', return_value=False)
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_updates_mobile_sensors(mock_is_mqtt, mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    mock_xfinity_token.OAUTH_TOKEN.update({
        'token_type': 'Bearer',
        'access_token': 'access_123',
    })
    mobile_sensors = {
        'sensor.xfinity_mobile_usage': {
            'state': 3.5,
            'attributes': {'friendly_name': 'Xfinity Mobile Usage'},
        },
    }
    mock_graphql.get_mobile_usage_details_data.return_value = mobile_sensors
    mock_graphql.get_mobile_service_details_data.return_value = {'has_service': True}

    main()

    mock_graphql.get_mobile_usage_details_data.assert_called_once_with(mock_xfinity_token.OAUTH_TOKEN)
    mock_helper_functions['update_ha_mobile_sensors'].assert_called_once_with(mobile_sensors)


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}.is_mqtt_available', return_value=False)
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_mobile_only_skips_internet_usage(mock_is_mqtt, mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    mock_graphql.get_plan_details_data.return_value = {}
    mock_my_account.get_plan_details_data.return_value = {}
    mock_graphql.convert_raw_plan_to_website_format.return_value = {}
    mock_graphql.get_mobile_service_details_data.return_value = {'has_service': True}
    mobile_sensors = {
        'sensor.xfinity_mobile_usage': {
            'state': 1.5,
            'attributes': {'friendly_name': 'Xfinity Mobile Usage'},
        },
    }
    mock_graphql.get_mobile_usage_details_data.return_value = mobile_sensors

    main()

    mock_my_account.get_usage_details_data.assert_not_called()
    mock_my_account.get_gateway_details_data.assert_not_called()
    mock_my_account.oauth_refresh_tokens.assert_not_called()
    mock_my_account.get_plan_details_data.assert_not_called()
    mock_graphql.get_usage_details_data.assert_not_called()
    mock_graphql.get_gateway_details_data.assert_not_called()
    mock_helper_functions['update_ha_mobile_sensors'].assert_called_once_with(mobile_sensors)


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_disabled_internet_skips_internet_checks(mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    mock_helper_functions['get_addon_options'].return_value = {
        'internet_usage_enabled': False,
        'mobile_usage_enabled': True,
    }

    main()

    mock_graphql.get_plan_details_data.assert_not_called()
    mock_graphql.get_gateway_details_data.assert_not_called()
    mock_graphql.get_usage_details_data.assert_not_called()
    mock_my_account.oauth_refresh_tokens.assert_not_called()
    mock_my_account.get_plan_details_data.assert_not_called()
    mock_my_account.get_gateway_details_data.assert_not_called()
    mock_my_account.get_usage_details_data.assert_not_called()
    mock_graphql.get_mobile_service_details_data.assert_called_once()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_disabled_mobile_skips_mobile_checks(mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    mock_helper_functions['get_addon_options'].return_value = {
        'internet_usage_enabled': True,
        'mobile_usage_enabled': False,
    }

    main()

    mock_graphql.get_plan_details_data.assert_called_once()
    mock_graphql.get_gateway_details_data.assert_called_once()
    mock_graphql.get_usage_details_data.assert_called_once()
    mock_graphql.get_mobile_service_details_data.assert_not_called()
    mock_graphql.get_mobile_usage_details_data.assert_not_called()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_with_no_internet_or_mobile_service(mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    mock_graphql.get_plan_details_data.return_value = {}
    mock_my_account.get_plan_details_data.return_value = {}
    mock_graphql.convert_raw_plan_to_website_format.return_value = {}
    mock_graphql.get_mobile_service_details_data.return_value = {'has_service': False}

    main()

    mock_my_account.get_usage_details_data.assert_not_called()
    mock_my_account.get_gateway_details_data.assert_not_called()
    mock_my_account.oauth_refresh_tokens.assert_not_called()
    mock_graphql.get_usage_details_data.assert_not_called()
    mock_graphql.get_gateway_details_data.assert_not_called()
    mock_graphql.get_mobile_usage_details_data.assert_not_called()
    mock_helper_functions['update_ha_sensor'].assert_not_called()
    mock_helper_functions['update_ha_mobile_sensors'].assert_not_called()


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}.is_mqtt_available', return_value=True)
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_publishes_internet_when_modem_is_unavailable(mock_is_mqtt, mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_mqtt, mock_helper_functions):
    mock_my_account.get_gateway_details_data.return_value = {}
    mock_graphql.get_gateway_details_data.return_value = {}

    main()

    mock_mqtt.return_value.set_mqtt_device_details.assert_called_once_with({})
    mock_mqtt.return_value.publish_mqtt.assert_called_once()
    mock_helper_functions['update_ha_sensor'].assert_not_called()


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_single_run_bypass(mock_exit, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    """Test that the script exits immediately when BYPASS is 0 or POLLING_RATE is 0."""
    main()

    mock_graphql.get_usage_details_data.assert_called_once()
    mock_my_account.get_usage_details_data.assert_not_called()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)


@patch(f'{ADDON_MODULE}.sleep', side_effect=StopIteration)
@patch(f'{ADDON_MODULE}._BYPASS', 1)
@patch(f'{ADDON_MODULE}._POLLING_RATE', 30.0)
def test_main_with_polling_loop(mock_sleep, mock_xfinity_token, mock_my_account, mock_graphql, mock_helper_functions):
    """Test that the main loop sleeps and continues when polling is enabled."""
    with pytest.raises(StopIteration):
        main()

    # Assert that sleep was called with the correct polling rate
    mock_sleep.assert_called_once_with(30.0)
    # Assert that the main processing logic was executed at least once
    mock_graphql.get_usage_details_data.assert_called_once()
    mock_my_account.get_usage_details_data.assert_not_called()


@patch(f'{ADDON_MODULE}.XfinityMyAccount')
@patch(f'{ADDON_MODULE}.XfinityOAuthToken')
def test_main_tenacity_retry(mock_token_cls, mock_my_account_cls, mock_xfinity_token, mock_helper_functions):
    """Test that the tenacity retry decorator handles ConnectionError."""
    mock_token_cls.return_value.OAUTH_CODE_FLOW = False
    mock_token_cls.return_value.OAUTH_TOKEN = {
        'id_token': 'id_123',
        'refresh_token': 'refresh_123',
    }
    mock_my_account_cls.return_value.oauth_refresh_tokens.side_effect = ConnectionError("Mocked ConnectionError")
    
    with patch.object(main.retry, 'sleep'), pytest.raises(ConnectionError):
        main()

    # The mock will be called multiple times by the retry mechanism
    assert mock_my_account_cls.return_value.oauth_refresh_tokens.call_count == 6


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}.clear_token')
@patch(f'{ADDON_MODULE}._CLEAR_TOKEN', True)
def test_main_initial_clear_token_env(mock_clear_token, mock_exit, mock_xfinity_token, mock_helper_functions):
    """Test that `clear_token` is called if _CLEAR_TOKEN is true from environment variable."""
    mock_xfinity_token.OAUTH_TOKEN = {}
    main()

    mock_clear_token.assert_called_once_with(mock_helper_functions['get_addon_options'].return_value)
    mock_exit.assert_not_called()


@patch('builtins.exit')
@patch(f'{ADDON_MODULE}.is_hassio', return_value=True)
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_token_refresh_hassio(mock_is_hassio, mock_exit, mock_xfinity_token, mock_my_account, mock_helper_functions):
    """Test token refresh handling in Hass.io when refresh_token is missing from options."""
    mock_xfinity_token.OAUTH_TOKEN = {'refresh_token': 'new_refresh'}
    mock_helper_functions['get_addon_options'].return_value = {}

    main()

    mock_helper_functions['update_addon_options'].assert_called_once()
    mock_helper_functions['restart_addon'].assert_called_once()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)

@patch('builtins.exit')
@patch(f'{ADDON_MODULE}.is_hassio', return_value=False)
@patch(f'{ADDON_MODULE}._BYPASS', 0)
def test_main_token_refresh_not_hassio(mock_is_hassio, mock_exit, mock_xfinity_token, mock_my_account, mock_helper_functions):
    """Test token refresh handling outside Hass.io."""
    mock_xfinity_token.OAUTH_TOKEN = {'refresh_token': 'new_refresh'}
    main()

    mock_helper_functions['update_addon_options'].assert_not_called()
    mock_helper_functions['restart_addon'].assert_not_called()
    mock_exit.assert_called_once_with(exit_code.SUCCESS.value)
