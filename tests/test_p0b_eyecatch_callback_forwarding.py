from __future__ import annotations

import note_eyecatch_persistence as proof


class _Page:
    pass


class _Base:
    NoteDraftError = RuntimeError

    @staticmethod
    def _find_title(page):
        return object()

    @staticmethod
    def _save_draft_and_verify(
        page,
        title,
        manuscript,
        image_required=True,
        on_stable_draft_url=None,
    ):
        if on_stable_draft_url is not None:
            on_stable_draft_url("private-stable-route")
        return "private-stable-route"


def test_creation_persistence_guard_forwards_stable_draft_callback():
    base = _Base
    original = base._save_draft_and_verify
    proof.install_creation_persistence_guard(base)
    try:
        observed: list[str] = []
        result = base._save_draft_and_verify(
            _Page(),
            "title",
            "body",
            image_required=False,
            on_stable_draft_url=observed.append,
        )
        assert result == "private-stable-route"
        assert observed == ["private-stable-route"]
    finally:
        base._save_draft_and_verify = original
