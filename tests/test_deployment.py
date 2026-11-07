"""Deployment safety checks without Docker, GitHub credentials or AI calls."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from deploy import auto_kiri as deployment


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.source = base / 'source'
        self.root = base / 'target'
        self.source.mkdir()
        self.root.mkdir()
        for name in ('Dockerfile', 'requirements.txt', '.dockerignore', 'compose.kiri.yaml',
                     'app/main.py', 'docs/README.md', 'deploy/kiri.sh', 'deploy/configure_kiri.py'):
            file = self.source / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('test input')
        for name in deployment.SECRET_FILES:
            (self.source / name).write_text('ORIGINAL=credential\n')
        deployment.initialize(self.source, self.root)
        self.sha = 'a' * 40

    def test_init_preserves_existing_database_credentials(self):
        (self.source / '.env.kiri').write_text('CHANGED=password\n')
        deployment.initialize(self.source, self.root)
        secret = self.root / 'shared/.env.kiri'
        self.assertEqual(secret.read_text(), 'ORIGINAL=credential\n')
        self.assertEqual(secret.stat().st_mode & 0o777, 0o600)

    def test_release_excludes_user_files_and_keeps_unique_image(self):
        for name in ('rnd-tekna.pem', 'artifacts/report', 'data/dev.db', 'app/.env.private', 'app/test.key'):
            file = self.source / name
            file.parent.mkdir(exist_ok=True)
            file.write_text('must not copy')
        first = deployment.stage(self.source, self.root, self.sha)
        second = deployment.stage(self.source, self.root, self.sha)
        for name in ('rnd-tekna.pem', 'artifacts', 'data', 'app/.env.private', 'app/test.key'):
            self.assertFalse((first / name).exists())
        self.assertNotEqual(first, second)
        self.assertIn('ORIGINAL=credential', (first / '.env.kiri').read_text())
        self.assertIn('PREPTIVA_IMAGE=preptiva:' + first.name, (first / '.env.kiri').read_text())
        self.assertNotIn('PREPTIVA_IMAGE', (self.root / 'shared/.env.kiri').read_text())
        self.assertEqual((first / '.env').stat().st_mode & 0o777, 0o600)

    def test_source_symlinks_are_rejected(self):
        (self.source / 'app/linked').symlink_to(self.source / '.env')
        with self.assertRaises(RuntimeError):
            deployment.stage(self.source, self.root, self.sha)

    def test_failed_health_restores_previous_release_without_changing_pointer(self):
        previous = deployment.stage(self.source, self.root, self.sha)
        candidate = deployment.stage(self.source, self.root, 'b' * 40)
        (self.root / 'current').symlink_to(previous)
        failure = subprocess.CalledProcessError(1, ['docker'])
        with patch.object(deployment, 'compose', side_effect=[failure, None]) as compose:
            with self.assertRaises(subprocess.CalledProcessError):
                deployment.activate(self.root, candidate)
        self.assertEqual([call.args[0] for call in compose.call_args_list], [candidate, previous])
        self.assertEqual(deployment.current_release(self.root), previous)

    def test_success_changes_current_only_after_healthy(self):
        candidate = deployment.stage(self.source, self.root, self.sha)
        with patch.object(deployment, 'compose') as compose:
            deployment.activate(self.root, candidate)
        self.assertEqual(deployment.current_release(self.root), candidate)
        self.assertIn('--wait', compose.call_args.args)
        self.assertIn('--no-build', compose.call_args.args)

    def test_build_failure_does_not_touch_running_release(self):
        previous = deployment.stage(self.source, self.root, self.sha)
        (self.root / 'current').symlink_to(previous)
        with patch.object(deployment, 'run', return_value=self.sha), \
             patch.object(deployment, 'latest_main', return_value=True), \
             patch.object(deployment, 'compose', side_effect=[None, subprocess.CalledProcessError(1, ['docker'])]), \
             patch.object(deployment, 'activate') as activate:
            with self.assertRaises(subprocess.CalledProcessError):
                deployment.deploy(self.source, self.root, self.sha)
            activate.assert_not_called()
        self.assertEqual(deployment.current_release(self.root), previous)

    def test_main_change_during_build_skips_activation(self):
        with patch.object(deployment, 'run', return_value=self.sha), \
             patch.object(deployment, 'latest_main', side_effect=[True, False]), \
             patch.object(deployment, 'compose'), \
             patch.object(deployment, 'activate') as activate:
            deployment.deploy(self.source, self.root, self.sha)
            activate.assert_not_called()

    def test_github_main_check_rejects_pr_and_outdated_commit(self):
        environment = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': deployment.REPOSITORY,
                       'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'pull_request',
                       'GH_TOKEN': 'test-token'}
        with patch.dict(os.environ, environment):
            with self.assertRaises(RuntimeError):
                deployment.latest_main(self.sha)
            os.environ['GITHUB_EVENT_NAME'] = 'push'
            response = MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps({'object': {'sha': 'b' * 40}})
            with patch('urllib.request.urlopen', return_value=response):
                self.assertFalse(deployment.latest_main(self.sha))

    def test_compose_always_uses_same_kiri_project_and_does_not_delete_volumes(self):
        with patch.object(deployment, 'run') as run:
            deployment.compose(self.root, 'up', '-d', '--wait')
        command = run.call_args.args[0]
        self.assertEqual(command[1:6], ['--context', 'kiri', 'compose', '--project-name', 'preptiva'])
        self.assertNotIn('down', command)


if __name__ == '__main__':
    unittest.main()
