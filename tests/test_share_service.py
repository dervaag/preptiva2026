import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from deploy import kiri_share_service as service


class ShareServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.secret = 'DB_PASSWORD=unchanged\nSECRET_KEY=unchanged\nPREPTIVA_IMAGE=preptiva:tested\n'
        for parent in ('shared', 'share/bootstrap', 'releases/current-test'):
            path = self.root / parent
            path.mkdir(parents=True)
            (path / '.env.kiri').write_text(self.secret + 'PUBLIC_ORIGIN=https://old.runkiri.cloud\n')

    def test_new_url_updates_current_release_and_future_deploys_preserving_secrets(self):
        active = self.root / 'releases/current-test'
        (self.root / 'current').symlink_to(active)
        with patch.object(service, 'compose_up') as compose:
            service.apply_origin(self.root, 'https://new-123.runkiri.cloud')
        compose.assert_called_once_with(active)
        for parent in ('shared', 'share/bootstrap', 'releases/current-test'):
            path = self.root / parent / '.env.kiri'
            self.assertEqual(path.read_text(), self.secret + 'PUBLIC_ORIGIN=https://new-123.runkiri.cloud\n')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_invalid_url_does_not_change_environment_or_restart_application(self):
        path = self.root / 'shared/.env.kiri'
        original = path.read_text()
        with patch.object(service, 'compose_up') as compose:
            for url in ('https://attacker.example', 'http://one.runkiri.cloud',
                        'https://one.runkiri.cloud/path', 'https://*.runkiri.cloud',
                        'https://one.runkiri.cloud\nSECRET_KEY=changed'):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    service.apply_origin(self.root, url)
            compose.assert_not_called()
        self.assertEqual(path.read_text(), original)

    def test_before_first_ci_deploy_uses_bootstrap_outside_workspace(self):
        with patch.object(service, 'compose_up') as compose:
            service.apply_origin(self.root, 'https://new.runkiri.cloud')
        compose.assert_called_once_with(self.root / 'share/bootstrap')


if __name__ == '__main__':
    unittest.main()
