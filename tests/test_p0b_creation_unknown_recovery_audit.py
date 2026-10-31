from __future__ import annotations

import importlib
import importlib.util
import inspect
import tempfile
from pathlib import Path

import pytest

from note_delivery_ledger import DeliveryState, SQLiteDeliveryLedger, build_delivery_snapshot
from note_document_contract import Document, Paragraph, Text


def _module():
    spec = importlib.util.find_spec("note_delivery_creation_recovery")
    assert spec is not None, "note_delivery_creation_recovery must exist before ambiguous draft recovery can run"
    return importlib.import_module("note_delivery_creation_recovery")


def _snapshot(sync_id: str = "a" * 32, note_target: str = "trendhub_biz"):
    return build_delivery_snapshot(
        sync_id=sync_id,
        queue_page_id="queue-page",
        title="Private recovery target",
        manuscript_sha256="1" * 64,
        publication_policy_sha256="2" * 64,
        document=Document((Paragraph((Text("canonical body"),)),)),
        transform_versions=(("run222", "note-presentation-integrity-v1"),),
        eyecatch_sha256="3" * 64,
        eyecatch_asset_id="asset-id",
        note_target=note_target,
        ready_provenance="ready-waiting-current-publication-v1:test",
    )


def test_safe_projection_excludes_private_identity_and_unpublished_content():
    recovery = _module()
    full = {
        "status": "recovery_candidate_found",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "match_count": 1,
        "history_candidate_count": 7,
        "editor_route_hash": "abcdef123456",
        "recovered_draft_id": "private-draft-id",
        "sync_id": "a" * 32,
        "draft_url": "https://note.com/notes/private-draft-id/edit",
        "title": "secret unpublished title",
        "manuscript": "secret unpublished body",
    }
    safe = recovery.safe_recovery_projection(full)
    assert safe == {
        "status": "recovery_candidate_found",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "match_count": 1,
        "history_candidate_count": 7,
        "editor_route_hash": "abcdef123456",
        "rejection_counts": {bucket: 0 for bucket in recovery.REJECTION_BUCKETS},
        "inspection_stage_counts": {stage: 0 for stage in recovery.INSPECTION_STAGES},
        "title_failure_counts": {code: 0 for code in recovery.TITLE_FAILURE_CODES},
        "title_dom_signal_counts": {code: 0 for code in recovery.TITLE_DOM_SIGNAL_CODES},
        "title_context_signal_counts": {code: 0 for code in recovery.TITLE_CONTEXT_CODES},
    }
    for forbidden in ("recovered_draft_id", "sync_id", "draft_url", "title", "manuscript"):
        assert forbidden not in safe


def test_recovery_requires_existing_creation_unknown_without_draft_identity():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
        ledger.initialize()
        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        ambiguous = ledger.record_blocked(
            decision.record.operation_key,
            state=DeliveryState.CREATION_UNKNOWN,
            category="creation_result_ambiguous",
            expected_version=decision.record.state_version,
        )

        loaded = recovery.require_creation_unknown_record(
            ledger,
            sync_id="a" * 32,
            note_target="trendhub_biz",
        )
        assert loaded.record_id == ambiguous.record_id
        assert loaded.state == DeliveryState.CREATION_UNKNOWN
        assert loaded.draft_id is None


def test_recovery_rejects_missing_or_non_ambiguous_delivery():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
        ledger.initialize()
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_creation_unknown_record(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub_biz",
            )

        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_creation_unknown_record(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub_biz",
            )
        assert decision.record.state == DeliveryState.CREATE_INTENT_RECORDED


def test_recovery_candidate_selection_is_exactly_one_or_fail_closed():
    recovery = _module()
    one = recovery.require_unique_recovery_match([
        {"draft_id": "opaque-1", "editor_route_hash": "hash-1"}
    ])
    assert one["draft_id"] == "opaque-1"

    for matches in ([], [{"draft_id": "a"}, {"draft_id": "b"}]):
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_unique_recovery_match(matches)


def test_recovery_module_is_read_only_and_reuses_current_contract_verification():
    recovery = _module()
    source = inspect.getsource(recovery)
    assert "run194_note_current_contract" in source
    assert "run291_note_private_draft_audit" in source
    assert "_recent_private_edit_urls" in source
    forbidden = (
        "_create_browser_draft(",
        "_mark_draft_created(",
        "record_draft_created(",
        "record_verified(",
        "record_queue_confirmed(",
        "patch_and_readback_draft_binding(",
        ".click(",
        ".fill(",
        "keyboard.press",
        "keyboard.insert_text",
        "page.screenshot(",
        "requests.post(",
    )
    for token in forbidden:
        assert token not in source


def test_recovery_requires_immutable_snapshot_and_lossless_canonical_dom_evidence():
    recovery = _module()
    source = inspect.getsource(recovery)

    # The ambiguous attempt itself, not merely the current mutable queue projection,
    # remains the authority for which revision may be recovered.
    assert "delivery_runtime.prepare_delivery(" in source
    assert ".snapshot != record.snapshot" in source

    # A title/prefix/length heuristic is insufficient to recover external identity.
    # Candidate body must survive the same semantic DOM -> canonical document path as P0-A
    # and hash exactly to the immutable snapshot recorded before the ambiguous create.
    assert "snapshot_note_body(" in source
    assert "document_from_note_snapshot(" in source
    assert "NOTE_LIST_ITEM_PARAGRAPH_WRAPPER" in source
    assert "NOTE_BLOCKQUOTE_FIGURE_WRAPPER" in source
    assert "canonical_document_sha256(" in source
    assert "record.snapshot.canonical_document_sha256" in source


def test_non_unique_readonly_audit_reports_counts_without_authorizing_recovery(monkeypatch):
    import types
    recovery = _module()
    monkeypatch.setattr(recovery, "SQLiteDeliveryLedger", lambda _: object())
    monkeypatch.setattr(recovery, "require_creation_unknown_record", lambda *a, **kw: object())
    monkeypatch.setattr(
        recovery, "_expected_prepared_delivery",
        lambda _: types.SimpleNamespace(article={"title": "private", "manuscript": "body"}),
    )

    for matches, expected in (
        ([], "recovery_no_verified_match"),
        ([{"draft_id": "opaque-one"}, {"draft_id": "opaque-two"}],
         "recovery_multiple_verified_matches"),
    ):
        monkeypatch.setattr(
            recovery, "_discover_verified_matches",
            lambda article, record, matches=matches: (
                matches, 6,
                {"different_title": 6 - len(matches)},
                {"title_read": 1},
                {"title_selector_unavailable": 1},
                {"ready_complete": 1, "editables_missing": 1},
                {"http_2xx": 1, "route_same_identity": 1, "js_responding": 1},
            ),
        )
        result = recovery.run(
            confirm=recovery.CONFIRM_TOKEN, sync_id="a" * 32,
            note_target="trendhub_biz", ledger_path="/unused/read-only/ledger",
        )
        assert result["status"] == expected
        assert result["match_count"] == len(matches)
        assert result["history_candidate_count"] == 6
        assert result["rejection_counts"]["different_title"] == 6 - len(matches)
        assert result["inspection_stage_counts"]["title_read"] == 1
        assert result["title_failure_counts"]["title_selector_unavailable"] == 1
        assert result["title_dom_signal_counts"]["ready_complete"] == 1
        assert result["title_dom_signal_counts"]["editables_missing"] == 1
        assert result["title_context_signal_counts"]["route_same_identity"] == 1
        assert result["read_only"] is True
        assert result["draft_mutation"] is False
        assert result["public_release"] is False
        assert "recovered_draft_id" not in result


def test_cli_writes_safe_blocked_result_then_returns_failure(tmp_path, monkeypatch, capsys):
    import json
    import sys
    recovery = _module()
    blocked = {
        "status": "recovery_no_verified_match",
        "read_only": True, "zero_gemini_calls": True,
        "draft_mutation": False, "public_release": False,
        "match_count": 0, "history_candidate_count": 9,
        "editor_route_hash": "",
        "rejection_counts": {"different_title": 9},
    }
    monkeypatch.setattr(recovery, "run", lambda **kwargs: dict(blocked))
    target = tmp_path / "read-only-result.json"
    monkeypatch.setattr(sys, "argv", ["audit", "--result-file", str(target)])
    with pytest.raises(recovery.CreationRecoveryAuditError):
        recovery.main()
    assert json.loads(target.read_text(encoding="utf-8")) == blocked
    output = capsys.readouterr().out
    assert '"match_count": 0' in output
    assert '"history_candidate_count": 9' in output
    assert "draft_id" not in output


def test_rejection_diagnostics_are_fixed_bucket_counts_without_private_identity():
    recovery = _module()
    unsafe = {
        "status": "recovery_no_verified_match",
        "rejection_counts": {
            "different_title": 16,
            "logged_out": 2,
            "inspection_error": 6,
            "candidate_private_url": "https://note.com/notes/secret/edit",
            "secret_manuscript": "private text",
        },
        "recovered_draft_id": "secret",
    }
    safe = recovery.safe_recovery_projection(unsafe)
    assert safe["rejection_counts"] == {
        "logged_out": 2, "non_editor": 0, "different_title": 16,
        "content_or_eyecatch": 0, "canonical_hash": 0,
        "inspection_error": 6,
    }
    assert "candidate_private_url" not in str(safe)
    assert "secret_manuscript" not in str(safe)
    assert "recovered_draft_id" not in str(safe)


def test_failed_recovery_still_requires_exact_one_verified_match():
    recovery = _module()
    assert "recovery_no_verified_match" in inspect.getsource(recovery.run)
    assert "recovery_multiple_verified_matches" in inspect.getsource(recovery.run)
    assert "len(matches) != 1" in inspect.getsource(recovery.run)


def test_inspection_stage_projection_is_fixed_and_never_leaks_raw_browser_data():
    recovery = _module()
    safe = recovery.safe_recovery_projection({
        "status": "recovery_no_verified_match",
        "inspection_stage_counts": {
            "title_read": 5, "navigation": 1,
            "private_editor_url": "https://note.com/notes/secret/edit",
            "raw_browser_error": "Private title is secret",
        },
    })
    assert safe["inspection_stage_counts"]["title_read"] == 5
    assert safe["inspection_stage_counts"]["navigation"] == 1
    assert set(safe["inspection_stage_counts"]) == set(recovery.INSPECTION_STAGES)
    assert "private_editor_url" not in str(safe)
    assert "raw_browser_error" not in str(safe)
    assert "secret" not in str(safe).lower()


def test_readonly_title_fallback_uses_existing_explicit_finder_without_navigation(monkeypatch):
    recovery = _module()
    field = object()

    class Page:
        url = "https://editor.note.com/notes/existing/edit"

        def __init__(self):
            self.waits = []

        def wait_for_timeout(self, milliseconds):
            self.waits.append(milliseconds)

        def goto(self, *args, **kwargs):
            raise AssertionError("read-only recovery must never navigate to create a draft")

    def old_finder(_):
        raise recovery.draft_audit.note_base.NoteDraftError("legacy title selector absent")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", lambda _: field)
    page = Page()
    assert recovery._read_only_title_field(page, old_finder) is field
    assert page.waits == []


def test_readonly_title_prefers_original_finder_and_does_not_use_fallback(monkeypatch):
    recovery = _module()
    field = object()

    class Page:
        url = "https://note.com/notes/existing/edit"

    def fallback(_):
        raise AssertionError("fallback should not run when canonical finder succeeds")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", fallback)
    assert recovery._read_only_title_field(Page(), lambda _: field) is field


def test_readonly_title_absence_stays_blocked_without_guessing_or_writes(monkeypatch):
    recovery = _module()

    class Page:
        url = "https://note.com/notes/existing/edit"

        def __init__(self):
            self.waits = []

        def wait_for_timeout(self, milliseconds):
            self.waits.append(milliseconds)

    def old_finder(_):
        raise recovery.draft_audit.note_base.NoteDraftError("missing")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", lambda _: None)
    page = Page()
    with pytest.raises(recovery.TitleReadInspectionError) as exc:
        recovery._read_only_title_field(page, old_finder)
    assert exc.value.code == "title_selector_unavailable"
    assert page.waits == [450, 450, 450]


def test_readonly_title_fallback_requires_existing_editor_route(monkeypatch):
    recovery = _module()

    class Page:
        url = "https://note.com/"

    def forbidden(_):
        raise AssertionError("must not inspect title on a non-editor route")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", forbidden)
    with pytest.raises(recovery.CreationRecoveryAuditError):
        recovery._read_only_title_field(Page(), forbidden)


def test_readonly_finder_scoped_across_title_body_and_canonical_checks():
    recovery = _module()
    source = inspect.getsource(recovery._discover_verified_matches)
    assert 'patch.object(draft_audit.note_base, "_find_title", read_only_title_finder)' in source
    assert source.index('patch.object(draft_audit.note_base, "_find_title"') < source.index('draft_audit._title_value(page)')
    assert source.index('patch.object(draft_audit.note_base, "_find_title"') < source.index('draft_audit._audit_current_page(')
    assert source.index('patch.object(draft_audit.note_base, "_find_title"') < source.index('_current_canonical_sha256(page)')
    assert "record.snapshot.canonical_document_sha256" in source
    assert "len(matches)" not in inspect.getsource(recovery._read_only_title_field)

def test_title_failure_safe_projection_drops_untrusted_browser_details():
    recovery = _module()
    result = recovery.safe_recovery_projection({
        "title_failure_counts": {
            "title_selector_unavailable": 2,
            "title_selector_exception": 1,
            "title_value_unreadable": 3,
            "title_retry_interrupted": 0,
            "title_other": 0,
            "raw_page_url": "https://note.com/notes/private-identity/edit",
            "exception_text": "private manuscript and title",
        }
    })
    assert result["title_failure_counts"] == {
        "title_selector_unavailable": 2,
        "title_selector_exception": 1,
        "title_retry_interrupted": 0,
        "title_value_unreadable": 3,
        "title_other": 0,
    }
    assert "private-identity" not in str(result)
    assert "manuscript" not in str(result)
    assert set(result["title_failure_counts"]) == set(recovery.TITLE_FAILURE_CODES)


def test_title_fallback_failed_explicit_selector_is_fixed_code_only(monkeypatch):
    recovery = _module()

    class Page:
        url = "https://note.com/notes/existing/edit"
        def wait_for_timeout(self, milliseconds):
            assert milliseconds == 450

    def legacy(_):
        raise RuntimeError("secret URL https://note.com/notes/private-id/edit")

    def broken_explicit(_):
        raise ValueError("secret unpublished title")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", broken_explicit)
    with pytest.raises(recovery.TitleReadInspectionError) as exc:
        recovery._read_only_title_field(Page(), legacy)
    assert exc.value.code == "title_selector_exception"
    assert "secret" not in str(exc.value)
    assert "private-id" not in str(exc.value)
    assert recovery._title_failure_code(exc.value) == "title_selector_exception"


def test_title_fallback_retry_interrupted_is_coded_without_exception_text(monkeypatch):
    recovery = _module()

    class Page:
        url = "https://editor.note.com/notes/existing/edit"
        def wait_for_timeout(self, milliseconds):
            raise RuntimeError("candidate editor private path")

    def legacy(_):
        raise RuntimeError("private title")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", lambda _: None)
    with pytest.raises(recovery.TitleReadInspectionError) as exc:
        recovery._read_only_title_field(Page(), legacy)
    assert exc.value.code == "title_retry_interrupted"
    assert "private" not in str(exc.value)


def test_title_failure_code_never_propagates_raw_exception():
    recovery = _module()
    assert recovery._title_failure_code(
        recovery.draft_audit.PrivateDraftAuditError("secret unpublished title")
    ) == "title_value_unreadable"
    assert recovery._title_failure_code(RuntimeError("https://note.com/notes/hidden/edit")) == "title_other"
    assert recovery._title_failure_code(
        recovery.TitleReadInspectionError("title_selector_unavailable")
    ) == "title_selector_unavailable"
    with pytest.raises(ValueError):
        recovery.TitleReadInspectionError("raw_private_browser_error")


def test_title_failure_audit_counts_are_independent_of_safety_state():
    recovery = _module()
    source = inspect.getsource(recovery._discover_verified_matches)
    assert 'if stage == "title_read":' in source
    assert 'title_failures[_title_failure_code(exc)] += 1' in source
    assert "counts[\"inspection_error\"] += 1" in source
    assert "record.snapshot.canonical_document_sha256" in source
    assert "context.close()" in source


def test_title_dom_probe_reads_only_fixed_presence_signals_without_page_content():
    recovery = _module()
    class Locator:
        def __init__(self, count):
            self.value = count
        def count(self):
            return self.value

    class Page:
        url = "https://editor.note.com/notes/private-test-id/edit"
        def evaluate(self, expression):
            assert expression == "document.readyState"
            return "complete"
        def locator(self, selector):
            assert selector in {
                "body",
                "input, textarea",
                '[contenteditable="true"], [contenteditable="plaintext-only"]',
                '[role="textbox"]',
                '[role="progressbar"], [aria-busy="true"]',
            }
            return Locator({
                "body": 1,
                "input, textarea": 0,
                '[contenteditable="true"], [contenteditable="plaintext-only"]': 0,
                '[role="textbox"]': 0,
                '[role="progressbar"], [aria-busy="true"]': 1,
            }[selector])
        def content(self):
            raise AssertionError("raw DOM/HTML must never be read")
        def screenshot(self, *args, **kwargs):
            raise AssertionError("screenshots are forbidden")
        def goto(self, *args, **kwargs):
            raise AssertionError("navigation is forbidden")

    signals = recovery._safe_title_dom_signals(Page())
    assert signals == (
        "ready_complete", "body_present", "inputs_missing",
        "editables_missing", "textboxes_missing", "busy_present",
    )
    assert set(signals).issubset(set(recovery.TITLE_DOM_SIGNAL_CODES))
    assert "private-test-id" not in str(signals)


def test_title_dom_probe_fails_closed_to_unknown_when_js_or_locator_fails():
    recovery = _module()
    class Page:
        url = "https://note.com/notes/private/edit"
        def evaluate(self, expression):
            raise RuntimeError("private title text 123")
        def locator(self, selector):
            raise RuntimeError("https://note.com/notes/private/edit")
    signals = recovery._safe_title_dom_signals(Page())
    assert signals == (
        "ready_unknown", "body_unknown", "inputs_unknown",
        "editables_unknown", "textboxes_unknown", "busy_unknown",
    )
    assert "private" not in str(signals)


def test_title_dom_probe_never_interprets_raw_browser_values_as_output():
    recovery = _module()
    class Locator:
        def count(self):
            return 0
    class Page:
        url = "https://note.com/notes/private/edit"
        def evaluate(self, expression):
            return "secret manuscript from browser"
        def locator(self, selector):
            return Locator()
    signals = recovery._safe_title_dom_signals(Page())
    assert signals[0] == "ready_unknown"
    assert all(signal.endswith("_missing") for signal in signals[1:])
    assert "secret" not in str(signals)


def test_title_dom_projection_drops_private_keys_and_arbitrary_page_data():
    recovery = _module()
    result = recovery.safe_recovery_projection({
        "title_dom_signal_counts": {
            "ready_complete": 2,
            "editables_missing": 2,
            "busy_present": 1,
            "draft_url": "https://note.com/notes/private-draft/edit",
            "raw_html": "private manuscript",
        },
    })
    assert result["title_dom_signal_counts"]["ready_complete"] == 2
    assert result["title_dom_signal_counts"]["editables_missing"] == 2
    assert result["title_dom_signal_counts"]["busy_present"] == 1
    assert set(result["title_dom_signal_counts"]) == set(recovery.TITLE_DOM_SIGNAL_CODES)
    assert "private-draft" not in str(result)
    assert "private manuscript" not in str(result)


def test_title_dom_probe_only_follows_existing_selector_unavailable_failure():
    recovery = _module()
    source = inspect.getsource(recovery._discover_verified_matches)
    assert 'stage == "title_read"' in source
    assert 'exc.code == "title_selector_unavailable"' in source
    assert "_safe_title_dom_signals(page)" in source
    assert 'counts["inspection_error"] += 1' in source
    assert "record.snapshot.canonical_document_sha256" in source
    forbidden = (".click(", ".fill(", "page.content(", "page.screenshot(", "requests.post(")
    function_source = inspect.getsource(recovery._safe_title_dom_signals)
    assert all(token not in function_source for token in forbidden)


def test_title_context_probe_distinguishes_http_route_browser_and_login_markers(monkeypatch):
    recovery = _module()
    class Response:
        status = 200
    class Page:
        url = "https://editor.note.com/notes/secret1/edit"
        def is_closed(self):
            return False
        def evaluate(self, expression):
            assert expression == "1"
            return 1
        def content(self):
            raise AssertionError("must not read raw HTML")
        def screenshot(self, *args, **kwargs):
            raise AssertionError("must not capture screenshots")
        def goto(self, *args, **kwargs):
            raise AssertionError("must not navigate")
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda p: False)
    signals = recovery._safe_title_context_signals(
        Page(), "https://note.com/notes/secret1/edit/", Response()
    )
    assert signals == (
        "http_2xx", "route_same_identity", "browser_open",
        "js_responding", "login_markers_absent",
    )
    assert set(signals).issubset(set(recovery.TITLE_CONTEXT_CODES))
    assert "secret1" not in str(signals)


def test_title_context_probe_classifies_another_editor_identity_and_client_http(monkeypatch):
    recovery = _module()
    class Response:
        status = 404
    class Page:
        url = "https://editor.note.com/notes/different/edit"
        def is_closed(self): return False
        def evaluate(self, expression): return 1
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda p: True)
    signals = recovery._safe_title_context_signals(
        Page(), "https://editor.note.com/notes/expected/edit", Response()
    )
    assert signals == (
        "http_4xx", "route_other_identity", "browser_open",
        "js_responding", "login_markers_present",
    )


def test_title_context_probe_unknowns_do_not_leak_browser_exception_content(monkeypatch):
    recovery = _module()
    class Response:
        @property
        def status(self):
            raise RuntimeError("secret HTTP response body")
    class Page:
        url = "https://note.com/notes/secret/edit"
        def is_closed(self):
            raise RuntimeError("secret screenshot text")
        def evaluate(self, expression):
            raise RuntimeError("secret user manuscript")
    def login(_):
        raise RuntimeError("session token secret")
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", login)
    signals = recovery._safe_title_context_signals(
        Page(), "https://note.com/notes/secret/edit", Response()
    )
    assert signals == (
        "http_unknown", "route_same_identity", "browser_unknown",
        "js_unavailable", "login_markers_unknown",
    )
    assert "secret" not in str(signals)
    assert "token" not in str(signals)


def test_title_context_probe_closed_page_and_invalid_routes_are_fail_closed(monkeypatch):
    recovery = _module()
    class Page:
        url = "https://editor.note.com/notes/secret/edit?malformed=1"
        def is_closed(self): return True
        def evaluate(self, expression):
            raise AssertionError("no JS required on closed page")
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda _: False)
    signals = recovery._safe_title_context_signals(
        Page(), "https://note.com/notes/secret/edit", None
    )
    assert signals == (
        "http_unknown", "route_unverified", "browser_closed",
        "js_unavailable", "login_markers_absent",
    )


def test_title_context_projection_allowlist_disallows_private_keys_and_error_text():
    recovery = _module()
    projection = recovery.safe_recovery_projection({
        "title_context_signal_counts": {
            "http_4xx": 1, "route_unverified": 1,
            "js_unavailable": 1,
            "raw_draft_url": "https://note.com/notes/private/edit",
            "response_body": "secret unpublished manuscript",
            "exception_detail": "private token",
        }
    })
    counts = projection["title_context_signal_counts"]
    assert set(counts) == set(recovery.TITLE_CONTEXT_CODES)
    assert counts["http_4xx"] == 1
    assert counts["route_unverified"] == 1
    assert counts["js_unavailable"] == 1
    assert "private" not in str(projection)
    assert "manuscript" not in str(projection)


def test_title_context_probe_only_inspects_title_selector_unavailable_without_mutation():
    recovery = _module()
    code = inspect.getsource(recovery._discover_verified_matches)
    assert 'exc.code == "title_selector_unavailable"' in code
    assert "_safe_title_context_signals(page, candidate, response)" in code
    assert "record.snapshot.canonical_document_sha256" in code
    assert 'counts["inspection_error"] += 1' in code
    diagnostic = inspect.getsource(recovery._safe_title_context_signals)
    for forbidden in (".click(", ".fill(", ".goto(", ".content(", ".screenshot(", "requests.post("):
        assert forbidden not in diagnostic
