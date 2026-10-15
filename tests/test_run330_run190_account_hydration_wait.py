from __future__ import annotations

import unittest
from unittest import mock

import run190_note_persistent_cloud as run190


class _FakeCreatorField:
    def __init__(self, owner: "_FakeCreatorSet", *, value: str, wait_error: Exception | None = None) -> None:
        self.owner = owner
        self.value = value
        self.wait_error = wait_error
        self.wait_calls: list[tuple[str, int]] = []

    def wait_for(self, *, state: str, timeout: int) -> None:
        self.wait_calls.append((state, timeout))
        if self.wait_error is not None:
            raise self.wait_error
        self.owner.ready = True

    def is_visible(self, *, timeout: int) -> bool:
        return self.owner.ready

    def input_value(self, *, timeout: int | None = None) -> str:
        return self.value


class _FakeCreatorSet:
    def __init__(
        self,
        *,
        count_after_wait: int = 1,
        value: str = run190.EXPECTED_CREATOR_NAME,
        wait_error: Exception | None = None,
    ) -> None:
        self.ready = False
        self.count_after_wait = count_after_wait
        self.first = _FakeCreatorField(self, value=value, wait_error=wait_error)

    def count(self) -> int:
        return self.count_after_wait if self.ready else 0


class _FakePage:
    def __init__(self, creators: _FakeCreatorSet) -> None:
        self.creators = creators
        self.url = "https://note.com/"
        self.goto_calls: list[tuple[str, str, int]] = []
        self.wait_timeouts: list[int] = []
        self.locator_calls: list[str] = []

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))
        self.url = url

    def wait_for_timeout(self, milliseconds: int) -> None:
        self.wait_timeouts.append(milliseconds)

    def locator(self, selector: str) -> _FakeCreatorSet:
        self.locator_calls.append(selector)
        if selector != run190.CREATOR_NAME_SELECTOR:
            raise AssertionError(f"unexpected selector: {selector}")
        return self.creators


class Run330AccountHydrationWaitTests(unittest.TestCase):
    def _run(self, creators: _FakeCreatorSet) -> _FakePage:
        page = _FakePage(creators)
        with (
            mock.patch.object(run190.base, "_looks_logged_out", return_value=False),
            mock.patch.object(run190, "_settings_page_has_expected_profile_link", return_value=True),
        ):
            run190._assert_expected_note_account(page)
        return page

    def test_waits_for_exact_creator_control_before_cardinality_check(self) -> None:
        creators = _FakeCreatorSet(count_after_wait=1)

        page = self._run(creators)

        self.assertEqual(page.locator_calls, [run190.CREATOR_NAME_SELECTOR])
        self.assertEqual(creators.first.wait_calls, [("visible", 5000)])
        self.assertTrue(creators.ready)
        self.assertEqual(creators.count(), 1)

    def test_wait_timeout_preserves_fail_closed_inspection_error(self) -> None:
        creators = _FakeCreatorSet(wait_error=TimeoutError("hydration did not complete"))

        with self.assertRaisesRegex(
            run190.base.NoteDraftError,
            "expected note creator identity could not be inspected",
        ):
            self._run(creators)

        self.assertEqual(creators.first.wait_calls, [("visible", 5000)])

    def test_duplicate_exact_creator_controls_still_fail_closed(self) -> None:
        creators = _FakeCreatorSet(count_after_wait=2)

        with self.assertRaisesRegex(
            run190.base.NoteDraftError,
            "expected note creator identity could not be proven",
        ):
            self._run(creators)

        self.assertEqual(creators.first.wait_calls, [("visible", 5000)])

    def test_wrong_creator_still_fails_closed_after_readiness(self) -> None:
        creators = _FakeCreatorSet(count_after_wait=1, value="unexpected creator")

        with self.assertRaisesRegex(
            run190.base.NoteDraftError,
            "persistent note session belongs to an unexpected creator account",
        ):
            self._run(creators)

        self.assertEqual(creators.first.wait_calls, [("visible", 5000)])


if __name__ == "__main__":
    unittest.main()
