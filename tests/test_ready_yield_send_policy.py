"""Zero-provider checks for the capped fixed-Evidence probe."""
import unittest

from experiments.ready_yield_send_policy import ProbePolicy, ProbeStopped, run_bounded_cases


class ProbePolicyTests(unittest.TestCase):
    def test_bounded_runner_paces_every_provider_attempt_including_feedback(self):
        now = [0.0]
        calls = []
        reservations = []
        def send(case):
            calls.append((case["id"], now[0]))
            return "draft"
        def assess(case, raw):
            return {"id": case["id"], "feedback": {"id": "feedback", "model": case["model"]}
                   if case["id"] == "first" else None}
        results = run_bounded_cases(
            [{"id": "first", "model": "gemini-3.6-flash"},
             {"id": "second", "model": "gemini-3.5-flash"}],
            send=send, assess=assess, clock=lambda: now[0],
            sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
            before_send=lambda case: reservations.append(case["id"]),
        )
        self.assertEqual([c[0] for c in calls], ["first", "feedback", "second"])
        self.assertEqual(reservations, ["first", "feedback", "second"])
        self.assertEqual([c[1] for c in calls], [0, 25, 50])
        self.assertEqual(len(results), 3)

    def test_bounded_runner_never_retries_503_and_stops_after_second(self):
        now = [0.0]
        calls = []
        def send(case):
            calls.append(case["model"])
            error = RuntimeError("503 UNAVAILABLE")
            error.code = 503
            raise error
        results = run_bounded_cases(
            [{"id": str(i), "model": model} for i, model in enumerate(
                ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash"))],
            send=send, assess=lambda case, raw: {}, clock=lambda: now[0],
            sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
        )
        self.assertEqual(calls, ["gemini-3.6-flash", "gemini-3.5-flash"])
        self.assertEqual([r["outcome"] for r in results], ["503", "503"])

    def test_bounded_runner_429_stops_and_records_only_one_attempt(self):
        def send(case):
            error = RuntimeError("429 RESOURCE_EXHAUSTED")
            error.code = 429
            raise error
        results = run_bounded_cases(
            [{"id": "a", "model": "gemini-3.6-flash"},
             {"id": "b", "model": "gemini-3.5-flash"}],
            send=send, assess=lambda case, raw: {}, clock=lambda: 0,
            sleep=lambda seconds: None,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["outcome"], "429")

    def test_failed_shared_reservation_stops_before_provider(self):
        calls = []
        results = run_bounded_cases(
            [{"id": "a", "model": "gemini-3.6-flash"}],
            send=lambda case: calls.append(case), assess=lambda case, raw: {},
            before_send=lambda case: (_ for _ in ()).throw(RuntimeError("reservation unavailable")),
            clock=lambda: 0, sleep=lambda seconds: None,
        )
        self.assertEqual(calls, [])
        self.assertEqual(results[0]["outcome"], "error")

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
