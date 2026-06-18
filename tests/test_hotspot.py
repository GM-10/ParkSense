import unittest
from src.hotspot import calculate_intervention_impact

class TestHotspot(unittest.TestCase):
    def test_calculate_intervention_impact(self):
        # Base case
        self.assertEqual(calculate_intervention_impact(100, 0), 100)
        # Efficiency case
        self.assertAlmostEqual(calculate_intervention_impact(100, 10, 0.05), 100 / (1 + 0.5))

if __name__ == '__main__':
    unittest.main()
