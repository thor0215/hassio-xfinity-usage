import os
import sys
import tempfile
import logging
import importlib
import types
import pytest
import colorlog
import base64

@pytest.fixture(autouse=True)
def cleanup_logger_handlers():
    # Remove handlers after each test to avoid duplicate logs
    yield
    import xfinity_usage.xfinity_logger as xfinity_logger
    logger = xfinity_logger.logger
    logger.handlers = []

def test_logger_default_level(monkeypatch):
    monkeypatch.delenv('LOG_LEVEL', raising=False)
    importlib.reload(sys.modules.get('xfinity_usage.xfinity_logger') or importlib.import_module('xfinity_usage.xfinity_logger'))
    import xfinity_usage.xfinity_logger as xfinity_logger
    assert xfinity_logger.logger.level == logging.INFO

def test_logger_debug_level(monkeypatch):
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    importlib.reload(sys.modules.get('xfinity_usage.xfinity_logger') or importlib.import_module('xfinity_usage.xfinity_logger'))
    import xfinity_usage.xfinity_logger as xfinity_logger
    assert xfinity_logger.logger.level == logging.DEBUG

def test_debug_file_handler_mode(monkeypatch, tmp_path):
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    debug_log = tmp_path / "debug.log"
    monkeypatch.setattr('xfinity_usage.xfinity_logger._DEBUG_LOGGER_FILE', str(debug_log))
    sys.modules.pop('xfinity_usage.xfinity_logger', None)
    import xfinity_usage.xfinity_logger as xfinity_logger
    file_handlers = [h for h in xfinity_logger.logger.handlers if isinstance(h, logging.FileHandler)]
    assert file_handlers[0].mode == 'w', "Debug file handler should use write mode"

def test_no_debug_file_handler_for_info(monkeypatch):
    monkeypatch.setenv('LOG_LEVEL', 'INFO')
    sys.modules.pop('xfinity_usage.xfinity_logger', None)
    import xfinity_usage.xfinity_logger as xfinity_logger
    file_handlers = [h for h in xfinity_logger.logger.handlers if isinstance(h, logging.FileHandler)]
    assert not file_handlers, "No file handlers should be attached for INFO level"

