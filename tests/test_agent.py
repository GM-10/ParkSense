import unittest
from src.agent import get_agent

class TestAgent(unittest.TestCase):
    def test_agent_confidence_score_present(self):
        chain = get_agent()
        # This will fail/error because confidence_score is not passed or in the prompt yet
        response = chain.invoke("Give me an enforcement brief for Upparpet")
        self.assertIn("Confidence Score:", response)

if __name__ == '__main__':
    unittest.main()
