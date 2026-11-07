from hashlib import sha256

from app.config import ROOT


def asset_url(path: str) -> str:
    version = sha256((ROOT / 'app/static' / path).read_bytes()).hexdigest()[:12]
    return f'/static/{path}?v={version}'
