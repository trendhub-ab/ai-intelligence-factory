import unittest
from unittest.mock import MagicMock, call, patch

import requests

import note_ready_sync as sync


class Run625NotionTransientRetryTests(unittest.TestCase):
    def test_request_retries_read_timeout_then_returns_success(self):
        success = MagicMock(status_code=200)
        with patch.object(
            sync.requests,
            "request",
            side_effect=[requests.ReadTimeout("notion read timeout"), success],
        ) as request, patch.object(sync.time, "sleep") as sleep:
            result = sync._request("GET", "https://api.notion.com/v1/blocks/page/children")

        self.assertIs(result, success)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_request_retries_connection_error_then_returns_success(self):
        success = MagicMock(status_code=200)
        with patch.object(
            sync.requests,
            "request",
            side_effect=[requests.ConnectionError("connection reset"), success],
        ) as request, patch.object(sync.time, "sleep") as sleep:
            result = sync._request("GET", "https://api.notion.com/v1/blocks/page/children")

        self.assertIs(result, success)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_request_retries_read_only_query_post_after_timeout(self):
        success = MagicMock(status_code=200)
        with patch.object(
            sync.requests,
            "request",
            side_effect=[requests.ReadTimeout("query timeout"), success],
        ) as request, patch.object(sync.time, "sleep") as sleep:
            result = sync._request(
                "POST",
                "https://api.notion.com/v1/data_sources/source/query",
                json={"page_size": 100},
            )

        self.assertIs(result, success)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_request_reraises_transient_exception_after_bounded_attempts(self):
        failure = requests.ReadTimeout("persistent timeout")
        with patch.object(sync.requests, "request", side_effect=failure) as request, \
             patch.object(sync.time, "sleep") as sleep:
            with self.assertRaises(requests.ReadTimeout):
                sync._request("GET", "https://api.notion.com/v1/blocks/page/children")

        self.assertEqual(request.call_count, 5)
        self.assertEqual(sleep.call_args_list, [call(1), call(2), call(3), call(4)])

    def test_request_does_not_retry_non_idempotent_page_create_after_timeout(self):
        failure = requests.ReadTimeout("response lost after create")
        with patch.object(sync.requests, "request", side_effect=failure) as request, \
             patch.object(sync.time, "sleep") as sleep:
            with self.assertRaises(requests.ReadTimeout):
                sync._request("POST", "https://api.notion.com/v1/pages", json={"properties": {}})

        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
