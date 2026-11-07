"""Opt-in API checks for the localhost Studio inspector with a synthetic demo DB."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:2024')
    parser.add_argument('--output', type=Path, default=Path('/tmp/preptiva-studio-smoke.json'))
    arguments = parser.parse_args()
    target = urlsplit(arguments.base_url)
    if target.scheme != 'http' or target.hostname not in ('127.0.0.1','localhost'):
        parser.error('Only the localhost development server is supported.')
    root = Path(__file__).resolve().parents[1]
    values = dotenv_values(root / '.env.studio')
    database = Path(values['DATABASE_URL'].removeprefix('sqlite+aiosqlite:///'))
    if not database.resolve().is_relative_to((root / 'data/studio-demo').resolve()):
        parser.error('Select a synthetic studio-demo database before this check.')
    original = hashlib.sha256(database.read_bytes()).hexdigest()
    output = {'ok':False, 'synthetic':True, 'actual_provider_requests':0, 'graphs':{}}
    with httpx.Client(base_url=arguments.base_url, timeout=30, trust_env=False) as client:
        assert client.get('/ok').status_code == 200
        assistants = client.post('/assistants/search', json={})
        assistants.raise_for_status()
        available = {item['graph_id']: item['assistant_id'] for item in assistants.json()}
        for name, nodes in (('prepare',7),('turn',6),('finalize',8)):
            graph_id = 'preptiva_' + name + '_inspector'
            assistant = available[graph_id]
            diagram = client.get('/assistants/' + assistant + '/graph')
            diagram.raise_for_status()
            assert len(diagram.json()['nodes']) >= nodes
            thread = client.post('/threads', json={'metadata': {'source':'preptiva_synthetic_demo', 'graph_id':graph_id}})
            thread.raise_for_status()
            thread_id = thread.json()['thread_id']
            response = client.post('/threads/' + thread_id + '/runs/wait', json={
                'assistant_id':assistant, 'input':{'session_uuid':'00000000-0000-4000-8000-000000000001'}})
            response.raise_for_status()
            state = response.json()
            if state.get('mode') != 'read_only_inspection':
                raise AssertionError('Inspector failed; check the local Agent Server error type.')
            assert len(state['observed_nodes']) == nodes
            assert all(item['status'] == 'succeeded' for item in state['observed_nodes'])
            output['graphs'][graph_id] = {'observed_nodes':nodes, 'status':'passed', 'thread_id':thread_id}
    output['application_database_unchanged'] = original == hashlib.sha256(database.read_bytes()).hexdigest()
    assert output['application_database_unchanged']
    output['ok'] = True
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output))


if __name__ == '__main__':
    main()
