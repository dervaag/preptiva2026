import copy
import unittest

from validation.audit import audit
from validation.kit import starter


class ValidationAuditTests(unittest.TestCase):
    def test_unrated_pilot_never_produces_accuracy_or_validation_claim(self):
        report = audit(starter('engineering-manager'))
        self.assertFalse(report['validated'])
        self.assertEqual(report['status'], 'pending_human_evidence')
        self.assertIsNone(report['comparison'])
        self.assertEqual(report['human_evidence']['rating_entries'], 0)
        self.assertEqual(report['ai_evidence']['run_entries'], 0)
        self.assertEqual(report['technical_checks']['anchor_count'], 25)
        self.assertEqual(report['technical_checks']['source_mapping_issues'], [])
        self.assertEqual(report['coverage']['test'], 15)
        self.assertEqual(report['coverage']['calibration'], 5)

    def test_altered_snapshot_is_rejected(self):
        dataset = starter('engineering-manager')
        dataset['assessment']['weights']['technical'] += 1
        with self.assertRaises(ValueError):
            audit(dataset)

    def test_status_flags_alone_cannot_create_comparison(self):
        dataset = copy.deepcopy(starter('engineering-manager'))
        dataset['validated'] = True
        dataset['job_reviewed_by_human'] = True
        report = audit(dataset)
        self.assertFalse(report['validated'])
        self.assertIsNone(report['comparison'])
        self.assertTrue(report['pending_requirements'])
