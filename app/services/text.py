import re
import unicodedata
from io import BytesIO
from fastapi import HTTPException
from pypdf import PdfReader


def clean_text(text):
    text = unicodedata.normalize('NFC', text.replace('\r\n', '\n').replace('\r', '\n'))
    text = text.replace('\u00a0', ' ')
    text = ''.join(c for c in text if c in '\n\t' or unicodedata.category(c) not in ('Cc', 'Cf'))
    text = text.replace('\u00ad', '')
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n'))).strip()


def validate_text(text, kind):
    text = clean_text(text)
    minimum, maximum = (200, 60000) if kind == 'CV' else (5, 40000)
    if len(text) > maximum:
        raise HTTPException(413, f'{kind} maksimal {maximum:,} karakter.')
    length = len(text) if kind == 'CV' else len(text.split())
    if length < minimum:
        unit = 'karakter' if kind == 'CV' else 'kata'
        raise HTTPException(422, f'{kind} minimal {minimum} {unit} setelah dibersihkan.')
    return text


def extract_pdf(content):
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, 'PDF maksimal 5 MB.')
    if not content.startswith(b'%PDF-'):
        raise HTTPException(422, 'File harus berupa PDF yang valid.')
    try:
        reader = PdfReader(BytesIO(content))
        if len(reader.pages) > 30:
            raise HTTPException(422, 'PDF maksimal 30 halaman.')
        pages = [clean_text(page.extract_text() or '').splitlines() for page in reader.pages]
        margins = {}
        for lines in pages:
            for line in set(lines[:2] + lines[-2:]):
                if len(line) < 100:
                    margins[line] = margins.get(line, 0) + 1
        seen = set()
        cleaned = []
        for lines in pages:
            output = []
            for i, line in enumerate(lines):
                margin = i < 2 or i >= len(lines) - 2
                if margin and re.fullmatch(r'(?:page|halaman)\s*\d+(?:\s*(?:of|dari|/)\s*\d+)?', line, re.I):
                    continue
                if margin and margins.get(line, 0) >= 3:
                    if line in seen:
                        continue
                    seen.add(line)
                output.append(line)
            cleaned.append('\n'.join(output))
        return validate_text('\n\n'.join(cleaned), 'CV')
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, 'PDF tidak dapat dibaca. Unggah PDF berteks yang dapat dibuka.') from exc


def chunks(text, limit):
    parts = []
    while len(text) > limit:
        cut = max(text.rfind('\n\n', 0, limit + 1), text.rfind('\n', 0, limit + 1))
        if cut < limit // 2:
            cut = text.rfind(' ', 0, limit + 1)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts
