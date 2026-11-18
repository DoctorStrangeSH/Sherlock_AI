import unittest

from simulate_reply_flow import run_simulation


class ReplyFlowIntegrationTests(unittest.TestCase):
    def test_complete_local_approval_flow(self):
        confirmed = run_simulation()
        self.assertEqual(confirmed.recipient_id, 200)
        self.assertIn("семи", confirmed.reply)


if __name__ == "__main__":
    unittest.main()
