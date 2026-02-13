import json
import requests

from unittest import mock
import importlib

import xfinity_usage.xfinity_helper as helper

def test_load_key_returns_secret():
    assert helper.load_key() == helper._SECRET

def test_encrypt_decrypt_message_roundtrip():
    message = "test message"
    encrypted = helper.encrypt_message(message)
    assert isinstance(encrypted, bytes)
    decrypted = helper.decrypt_message(encrypted)
    assert decrypted == message

def test_camelTo_snake_case():
    assert helper.camelTo_snake_case("camelCaseString") == "camel_case_string"
    assert helper.camelTo_snake_case("CamelCase") == "camel_case"
    assert helper.camelTo_snake_case("already_snake") == "already_snake"

def test_ordinal():
    assert helper.ordinal(1) == "1st"
    assert helper.ordinal(2) == "2nd"
    assert helper.ordinal(3) == "3rd"
    assert helper.ordinal(4) == "4th"
    assert helper.ordinal(11) == "11th"
    assert helper.ordinal(21) == "21st"
    assert helper.ordinal(112) == "112th"

def test_get_current_unix_epoch():
    t = helper.get_current_unix_epoch()
    assert isinstance(t, float)

def test_is_hassio(monkeypatch):
    monkeypatch.setenv('BASHIO_SUPERVISOR_API', 'api')
    monkeypatch.setenv('BASHIO_SUPERVISOR_TOKEN', 'token')
    import xfinity_usage.xfinity_helper as reload_helper
    importlib.reload(reload_helper)
    assert reload_helper.is_hassio() is True

def test_read_write_delete_token_file_data(tmp_path):
    token_file = tmp_path / "token.json"
    data = {"access_token": "abc"}
    helper.write_token_file_data(data, str(token_file))
    assert token_file.exists()
    read = helper.read_token_file_data(str(token_file))
    assert read == data
    helper.delete_token_file_data(str(token_file))
    assert not token_file.exists()

def test_profile_cleanup(tmp_path, monkeypatch):
    # Create fake profile dir
    profile_dir = tmp_path / "profile1"
    profile_dir.mkdir()
    monkeypatch.setattr(helper, "glob", mock.Mock())
    helper.glob.glob.return_value = [str(profile_dir)]
    monkeypatch.setattr(helper, "Path", mock.Mock())
    helper.Path.return_value.exists.return_value = True
    helper.Path.return_value.is_dir.return_value = True
    monkeypatch.setattr(helper.shutil, "rmtree", mock.Mock())
    helper.profile_cleanup()
    helper.shutil.rmtree.assert_called_with(str(profile_dir))

def test_update_sensor_file(tmp_path, monkeypatch):
    monkeypatch.setattr(helper.os.path, "exists", lambda x: True)
    sensor_backup = tmp_path / ".sensor-backup"
    monkeypatch.setattr(helper, "_SENSOR_BACKUP", str(sensor_backup))
    data = {"foo": "bar"}
    helper.update_sensor_file(data)
    assert sensor_backup.exists()
    with open(sensor_backup) as f:
        assert json.load(f) == data

def test_process_usage_json_limited(monkeypatch):
    monkeypatch.setattr(helper.logger, "info", lambda *a, **k: None)
    monkeypatch.setattr(helper.logger, "debug", lambda *a, **k: None)
    usage = {
        "usageMonths": [{
            "policy": "limited",
            "totalUsage": 100,
            "allowableUsage": 1200,
            "unitOfMeasure": "GB",
            "displayUsage": True
        }],
        "courtesyUsed": 1,
        "courtesyRemaining": 2,
        "courtesyAllowed": 3,
        "courtesyMonths": 4,
        "inPaidOverage": False
    }
    plan = {"downloadSpeed": 100, "uploadSpeed": 10}
    result = helper.process_usage_json(usage, plan)
    assert result["state"] == 100
    assert result["attributes"]["internet_download_speeds_Mbps"] == 100
    assert result["attributes"]["internet_upload_speeds_Mbps"] == 10
    assert result["attributes"]["courtesy_used"] == 1

def test_process_usage_json_unlimited(monkeypatch):
    monkeypatch.setattr(helper.logger, "info", lambda *a, **k: None)
    monkeypatch.setattr(helper.logger, "debug", lambda *a, **k: None)
    usage = {
        "usageMonths": [{
            "policy": "unlimited",
            "totalUsage": 200,
            "unitOfMeasure": "GB",
            "displayUsage": True
        }]
    }
    plan = {}
    result = helper.process_usage_json(usage, plan)
    assert result["state"] == 200
    assert result["attributes"]["internet_download_speeds_Mbps"] == -1

def test_process_usage_json_displayUsage_false(monkeypatch):
    monkeypatch.setattr(helper.logger, "info", lambda *a, **k: None)
    monkeypatch.setattr(helper.logger, "debug", lambda *a, **k: None)
    usage = {
        "usageMonths": [{
            "policy": "unlimited",
            "totalUsage": 0,
            "unitOfMeasure": "GB",
            "displayUsage": False
        }]
    }
    plan = {}
    result = helper.process_usage_json(usage, plan)
    assert result["state"] == 0
    assert result["attributes"]["internet_download_speeds_Mbps"] == -1

def test_process_usage_json_displayUsage_and_total_usage_invalid(monkeypatch):
    monkeypatch.setattr(helper.logger, "info", lambda *a, **k: None)
    monkeypatch.setattr(helper.logger, "debug", lambda *a, **k: None)
    usage = {
        "usageMonths": [{
            "policy": "unlimited",
            "totalUsage": None,
            "unitOfMeasure": "GB",
            "displayUsage": False
        }]
    }
    plan = {}
    result = helper.process_usage_json(usage, plan)
    assert result["state"] == 0
    assert result["attributes"]["internet_download_speeds_Mbps"] == -1

def test_handle_requests_exception(monkeypatch):
    class DummyResponse:
        text = "bad json"
    class DummyException(Exception): pass
    monkeypatch.setattr(helper.logger, "error", mock.Mock())
    # HTTPError
    e = requests.exceptions.HTTPError("http error")
    helper.handle_requests_exception(e)
    # ConnectionError
    e = requests.exceptions.ConnectionError("conn error")
    helper.handle_requests_exception(e)
    # Timeout
    e = requests.exceptions.Timeout("timeout")
    helper.handle_requests_exception(e)
    # JSONDecodeError
    e = json.JSONDecodeError("msg", "doc", 1)
    helper.handle_requests_exception(e, DummyResponse())
    # RequestException
    e = requests.exceptions.RequestException("req error")
    helper.handle_requests_exception(e)
    # Unexpected
    e = DummyException("dummy")
    helper.handle_requests_exception(e)