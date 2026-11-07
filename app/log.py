import json
import logging
import time
from contextvars import ContextVar

request_var = ContextVar('request_id', default=None)
session_var = ContextVar('session_id', default=None)
logger = logging.getLogger('preptiva')
logging.basicConfig(level=logging.INFO)


def emit(event, **fields):
    logger.info(json.dumps({'ts': time.time(), 'event': event, 'rid': request_var.get(), 'sid': session_var.get(), **fields}))
