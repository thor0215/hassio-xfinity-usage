import base64
import colorlog
import logging
from xfinity_globals import *

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
logger.setLevel(LOG_LEVEL)
debug_formatter = logging.Formatter(fmt='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')

if LOG_LEVEL == 'DEBUG':
    file_handler = logging.FileHandler(DEBUG_LOGGER_FILE,mode='w')
    file_handler.setFormatter(debug_formatter)
    logger.addHandler(file_handler) 
    
    if DEBUG_SUPPORT:
        debug_support_logger = logging.getLogger(__name__ + '.file_logger')
        debug_support_logger.addHandler(file_handler)
        debug_support_logger.propagate = False

    for name, value in sorted(os.environ.items()):
        if name == 'XFINITY_PASSWORD':
            value = base64.b64encode(base64.b64encode(value.encode()).decode().strip('=').encode()).decode().strip('=')
        logger.debug(f"{name}: {value}")
