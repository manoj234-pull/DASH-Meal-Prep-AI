import unittest
from scripts.metrics import selection_metrics
class MetricsTests(unittest.TestCase):
    def test_known_mixed_predictions(self):
        m=selection_metrics([({'A'},{'A','B'}),({'B'},set()),(set(),set())],['A','B'])
        self.assertAlmostEqual(m['accuracy'],1/3)
        self.assertEqual(m['micro_average']['precision'],0.5)
        self.assertEqual(m['micro_average']['recall'],0.5)
        self.assertEqual(m['micro_average']['f1'],0.5)
        self.assertEqual(m['weighted_average']['support'],2)
        self.assertEqual(m['macro_average']['f1'],0.5)
    def test_unknown_metric_is_not_perfect(self):
        m=selection_metrics([],['A'])
        self.assertIsNone(m['accuracy'])
        self.assertIsNone(m['weighted_average']['f1'])

class EvaluationCoverageTests(unittest.TestCase):
    def test_failed_valid_queries_remain_in_denominator(self):
        from unittest.mock import patch
        from scripts.evaluate import evaluate
        # Pure metrics check: a failed valid query predicts an empty set, not exclusion.
        m=selection_metrics([({'A'},set()),({'A'},{'A'})],['A'])
        self.assertEqual(m['evaluated_queries'],2)
        self.assertEqual(m['accuracy'],0.5)
        self.assertAlmostEqual(m['micro_average']['recall'],0.5)
