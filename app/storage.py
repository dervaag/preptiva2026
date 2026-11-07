from pathlib import Path
from app.config import ROOT


def audio_dir(uuid):
    directory = ROOT / 'data/audio' / uuid
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_audio_path(uuid, name):
    if Path(name).name != name or not name.endswith('.mp3'):
        return None
    directory = audio_dir(uuid).resolve()
    path = (directory / name).resolve()
    return path if path.parent == directory and path.is_file() else None
