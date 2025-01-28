import base64
import colorlog
import logging
from xfinity_globals import *

_LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
_DEBUG_LOGGER_FILE = '/config/xfinity.log'


color_log_handler = colorlog.StreamHandler()
color_log_handler.setFormatter(colorlog.ColoredFormatter(
    '%(asctime)s.%(msecs)03d %(levelname)s: %(log_color)s%(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    reset=True,
    log_colors={
        'DEBUG':    '',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red'
    },
    secondary_log_colors={}))

# logger = logging.getLogger(__name__)
logger = colorlog.getLogger(__name__)
logger.addHandler(color_log_handler)
logger.setLevel(_LOG_LEVEL)
debug_formatter = logging.Formatter(fmt='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')

if _LOG_LEVEL == 'DEBUG':
    file_handler = logging.FileHandler(_DEBUG_LOGGER_FILE,mode='w')
    file_handler.setFormatter(debug_formatter)
    logger.addHandler(file_handler) 
    
    for name, value in sorted(os.environ.items()):
        if name == 'XFINITY_PASSWORD':
            value = base64.b64encode(base64.b64encode(value.encode()).decode().strip('=').encode()).decode().strip('=')
        logger.debug(f"{name}: {value}")
