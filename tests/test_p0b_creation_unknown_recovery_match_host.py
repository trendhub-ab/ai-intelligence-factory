from __future__ import annotations

import inspect

import note_delivery_creation_recovery as recovery


def test_recovery_match_keeps_verified_note_host_private():
    source = inspect.getsource(recovery)
    assert '"note_host"' in source
    assert "urlparse(" in source

    safe = recovery.safe_recovery_projection(
        {
            "status": "recovery_candidate_found",
            "read_only": True,
            "zero_gemini_calls": True,
            "draft_mutation": False,
            "public_release": False,
            "match_count": 1,
            "history_candidate_count": 1,
            "editor_route_hash": "abcdef123456",
            "recovered_draft_id": "private-id",
            "note_host": "editor.note.com",
        }
    )
    assert "note_host" not in safe
    assert "recovered_draft_id" not in safe
