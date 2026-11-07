import json
from pathlib import Path
import tempfile
import unittest

from validation.mohler import normalize, prepare


class MohlerTests(unittest.TestCase):
    def row(self, exercise=1):
        return dict(id=f'E{exercise:02}.Q01.A00', question='Question', instructor_answer='Reference',
                    student_answer='Answer', score_grader_1=4, score_grader_2=2, score_avg=3)

    def test_preserves_raw_scores_and_normalizes_exam_scale_correctly(self):
        row = self.row()
        self.assertEqual(normalize(row)['human_score_0_5'], 3)
        row = self.row(11)
        row.update(score_grader_1=8, score_grader_2=4)
        result = normalize(row)
        self.assertEqual(result['original_grader_scores'], [8, 4])
        self.assertEqual(result['original_scale_max'], 10)
        self.assertEqual(result['human_score_0_5'], 3)

    def test_flags_inconsistent_average_and_rejects_nonfinite_scores(self):
        self.assertFalse(normalize({**self.row(), 'score_avg': 4})['average_matches_normalized_graders'])
        for change in ({'score_avg': 9}, {'score_grader_1': float('nan')}, {'id': 'unknown'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalize({**self.row(), **change})

    def test_preparation_is_blind_and_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases = [{**normalize({**self.row(), 'id': f'E01.Q01.A{i:02}'}), 'source_split': 'open_ended'} for i in range(4)]
            dataset = root / 'dataset.json'
            dataset.write_text(json.dumps({'source': 'test-fixture', 'revision': 'fixture', 'cases': cases}))
            prepare(dataset, root / 'a', 3)
            cases.reverse()
            dataset.write_text(json.dumps({'source': 'test-fixture', 'revision': 'fixture', 'cases': cases}))
            prepare(dataset, root / 'b', 3)
            a = json.loads((root / 'a/inputs.json').read_text())
            b = json.loads((root / 'b/inputs.json').read_text())
            self.assertEqual(a, b)
            self.assertNotIn('human_score', json.dumps(a))
            for case in a['cases']:
                self.assertEqual(set(case), {'id', 'question_id', 'question', 'instructor_answer', 'student_answer'})
            self.assertEqual(len(json.loads((root / 'a/labels.json').read_text())['cases']), 3)
            with self.assertRaises(ValueError):
                prepare(dataset, root / 'a', 3)
