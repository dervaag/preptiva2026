"""Language policy for generated results; transcripts keep their original language."""


def feedback_language(session):
    config = (session.script or {}).get('settings', {})
    value = config.get('feedback_language', config.get('language', 'id'))
    return value if value in ('id', 'en') else 'id'


def validate_review(value):
    if not isinstance(value, dict) or not isinstance(value.get('summary'), str) or not value['summary'].strip():
        raise ValueError('Missing final summary.')
    texts = [value['summary']]
    for key in ('strengths', 'improvements'):
        if not isinstance(value.get(key), list) or any(not isinstance(v, str) for v in value[key]):
            raise ValueError('Invalid feedback list.')
        texts.extend(value[key])
    if not isinstance(value.get('study_recommendations'), list):
        raise ValueError('Missing study recommendations.')
    for item in value['study_recommendations']:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in ('topic', 'reason', 'action')):
            raise ValueError('Invalid recommendation.')
        texts.extend(item[k] for k in ('topic', 'reason', 'action'))
    if any(any(mark in text for mark in ('?', '？', '؟')) for text in texts):
        raise ValueError('Final feedback must give statements and actions, not questions.')


def validate_answer_feedback(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid assessment object.')
    feedback = value.get('feedback', {})
    if not isinstance(feedback, dict):
        raise ValueError('Invalid answer feedback.')
    texts = []
    for key in ('strengths', 'improvements'):
        entries = feedback.get(key, [])
        if not isinstance(entries, list) or any(not isinstance(text, str) for text in entries):
            raise ValueError('Invalid answer feedback list.')
        texts.extend(entries)
    tip = feedback.get('better_answer_tip', '')
    if not isinstance(tip, str):
        raise ValueError('Invalid practice tip.')
    texts.append(tip)
    if any(any(mark in text for mark in ('?', '？', '؟')) for text in texts):
        raise ValueError('Use direct practice advice, not a new interview question.')
