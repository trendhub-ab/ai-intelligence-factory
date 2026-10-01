import unittest
from unittest import mock

import member_notion_read_healthcheck as health


class MemberNotionReadHealthcheckTests(unittest.TestCase):
    def test_healthy_when_canonical_data_source_is_readable(self):
        response = mock.Mock(status_code=200)
        response.elapsed.total_seconds.return_value = 0.42
        with mock.patch.object(health.requests, "get", return_value=response) as get:
            result = health.check_health()

        self.assertEqual("healthy", result["status"])
        self.assertEqual(200, result["http_status"])
        self.assertEqual("GET", result["method"])
        self.assertFalse(result["writes"])
        self.assertEqual(0, result["gemini_calls"])
        get.assert_called_once()

    def test_unhealthy_on_server_error_without_write_or_retry_storm(self):
        response = mock.Mock(status_code=500)
        response.elapsed.total_seconds.return_value = 0.31
        with mock.patch.object(health.requests, "get", return_value=response) as get:
            result = health.check_health()

        self.assertEqual("unhealthy", result["status"])
        self.assertEqual(500, result["http_status"])
        self.assertEqual(1, get.call_count)
        self.assertFalse(result["writes"])


if __name__ == "__main__":
    unittest.main()
