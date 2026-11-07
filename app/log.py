import json
import logging
import time
from contextvars import ContextVar
from pathlib import Path
from traceback import walk_tb

request_var = ContextVar('request_id', default=None)
session_var = ContextVar('session_id', default=None)
question_var = ContextVar('question_id', default=None)
logger = logging.getLogger('preptiva')
logging.basicConfig(level=logging.INFO)
_APP_ROOT = Path(__file__).resolve().parent
_OUTPUT_REASONS = frozenset({'schema_invalid', 'action_invalid', 'reference_required',
    'reference_invalid', 'question_constraints', 'persona_scope', 'multiple_questions'})


def emit(event, **fields):
    logger.info(json.dumps({'ts': time.time(), 'event': event, 'rid': request_var.get(),
        'sid': session_var.get(), 'question_id': question_var.get(), **fields}))


def failure_fields(exc):
    """Trace code locations, never exception text, source lines, or frame locals.

    Pydantic errors and provider exceptions can embed candidate data or credentials
    in their messages. Follow explicit causes for locations without formatting them.
    """
    fields = {'error_type': type(exc).__name__, 'stage': 'answer',
              'reason': 'unexpected_error', 'frames': []}
    current, seen = exc, set()
    while current is not None and id(current) not in seen and len(seen) < 4:
        seen.add(id(current))
        stage = getattr(current, 'stage', None)
        reason = getattr(current, 'reason', None)
        if stage in ('respond', 'adapt_question'):
            fields['stage'] = stage
        if isinstance(reason, str) and reason in _OUTPUT_REASONS:
            fields['reason'] = reason
        for frame, line in walk_tb(current.__traceback__):
            try:
                file = Path(frame.f_code.co_filename).resolve().relative_to(_APP_ROOT)
            except ValueError:
                continue
            fields['frames'].append({'file': 'app/' + file.as_posix(),
                'function': frame.f_code.co_name, 'line': line})
        current = current.__cause__
    fields['frames'] = fields['frames'][-12:]
    return fields
