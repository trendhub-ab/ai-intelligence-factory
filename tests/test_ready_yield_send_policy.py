"""Zero-provider checks for the capped fixed-Evidence probe."""
import unittest

from experiments.ready_yield_send_policy import ProbePolicy, ProbeStopped


class ProbePolicyTests(unittest.TestCase):
    def test_four_attempt_cap_includes_errors_and_feedback(self):
        policy = ProbePolicy()
        for now in (0, 25, 50, 75):
            policy.reserve("gemini-3.6-flash", now)
            policy.record("success")
        with self.assertRaises(ProbeStopped):
            policy.reserve("gemini-3.5-flash", 100)

    def test_rolling_model_limit_and_project_spacing(self):
        policy = ProbePolicy()
        policy.reserve("gemini-3.6-flash", 0)
        with self.assertRaises(ProbeStopped):
            policy.reserve("gemini-3.5-flash", 24.9)
        policy = ProbePolicy(project_spacing=0)
        policy.reserve("gemini-3.6-flash", 0)
        policy.record("success")
        policy.reserve("gemini-3.6-flash", 1)
        policy.record("success")
        policy.reserve("gemini-3.6-flash", 2)
        policy.record("success")
        with self.assertRaises(ProbeStopped):
            policy.reserve("gemini-3.6-flash", 3)

    def test_429_stops_all_models(self):
        policy = ProbePolicy()
        policy.reserve("gemini-3.6-flash", 0)
        policy.record("429")
        with self.assertRaises(ProbeStopped):
            policy.reserve("gemini-3.5-flash", 100)

    def test_first_503_stops_model_second_consecutive_stops_experiment(self):
        policy = ProbePolicy()
        policy.reserve("gemini-3.6-flash", 0)
        policy.record("503")
        with self.assertRaises(ProbeStopped):
            policy.reserve("gemini-3.6-flash", 100)
        policy.reserve("gemini-3.5-flash", 100)
        policy.record("503")
        with self.assertRaises(ProbeStopped):
            policy.reserve("gemini-3.7-flash", 200)

    def test_success_resets_consecutive_503s(self):
        policy = ProbePolicy()
        policy.reserve("gemini-3.6-flash", 0)
        policy.record("503")
        policy.reserve("gemini-3.5-flash", 25)
        policy.record("success")
        policy.reserve("gemini-3.5-flash", 50)
        policy.record("503")
        policy.reserve("gemini-3.7-flash", 75)


if __name__ == "__main__":
    unittest.main()
