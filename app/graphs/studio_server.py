"""Launch local-only Studio inspectors with cloud tracing disabled."""
import argparse
import os
from pathlib import Path
import sys

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=2024)
    arguments = parser.parse_args()
    if sys.version_info < (3, 12) or not 1024 <= arguments.port <= 65535:
        parser.error('Gunakan Python 3.12 dan port 1024–65535.')
    root = Path(__file__).resolve().parents[2]
    if not (root / '.env.studio').is_file():
        parser.error('Jalankan python -m app.graphs.demo --configure-studio terlebih dahulu.')
    environment = os.environ.copy()
    environment.update(LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false',
                       LANGGRAPH_DEV_SERVER_TRACING='false')
    # Forward only the optional Studio key; never copy provider keys to config/logs.
    local = dotenv_values(root / '.env')
    for key in ('LANGSMITH_API_KEY', 'LANGCHAIN_API_KEY'):
        if not environment.get(key) and local.get(key):
            environment[key] = local[key]
    command = Path(sys.executable).parent / 'langgraph'
    if not command.is_file():
        parser.error('Instal requirements-studio.txt dalam virtualenv ini.')
    os.chdir(root)
    os.execve(str(command), [str(command), 'dev', '--config', str(root / 'langgraph.json'),
        '--host', '127.0.0.1', '--port', str(arguments.port), '--no-browser', '--no-reload'], environment)


if __name__ == '__main__':
    main()
