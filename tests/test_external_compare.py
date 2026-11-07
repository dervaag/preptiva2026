import unittest
from validation.external_compare import compare_rows


class ExternalComparisonTests(unittest.TestCase):
    def rows(self, humans, ai):
        return [dict(case_id=str(i), participant_id=str(i), target='answer_quality',
                     split='test', human_score=h, ai_score=a)
                for i, (h, a) in enumerate(zip(humans, ai))]

    def test_preserves_ranking_across_different_scales(self):
        report = compare_rows(self.rows([-2, 0, 3], [1, 3, 5]))
        self.assertAlmostEqual(report['spearman_rho'], 1)
        self.assertFalse(report['validated'])

    def test_ties_and_constant_labels(self):
        self.assertAlmostEqual(compare_rows(self.rows([1, 1, 2], [5, 5, 1]))['spearman_rho'], -1)
        self.assertIsNone(compare_rows(self.rows([1, 1, 1], [1, 2, 3]))['spearman_rho'])

    def test_rejects_nonfinite_duplicate_and_calibration(self):
        for field, value in [('human_score', 'nan'), ('case_id', '1'), ('split', 'calibration')]:
            rows = self.rows([1, 2, 3], [1, 2, 3])
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                compare_rows(rows)
