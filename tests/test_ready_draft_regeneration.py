from __future__ import annotations

import inspect
import os
import types
import unittest
from unittest.mock import patch

import ready_draft_regeneration as target


SYNC_ID = "3f5479ffdca98166b121fb8e0dabe23d"
DEST_PAGE_ID = "3f6479ff-dca9-8152-92f7-c04a5b5d99ce"
DRAFT_ID = "nb6fe64a05293"
OLD_TITLE = "Old public title"
NEW_TITLE = "New public title"


class _Budget:
    def __init__(self, budget=8):
        self.budget = budget
        self.used = 0


class ReadyDraftRegenerationTests(unittest.TestCase):
    def _rich(self, value: str):
        return {"rich_text": [{"plain_text": value}]}

    def _title(self, value: str):
        return {"title": [{"plain_text": value}]}

    def _select(self, value: str):
        return {"select": {"name": value}}

    def _destination_row(
        self,
        *,
        posting="投稿準備中",
        quality="Ready",
        draft_id=DRAFT_ID,
        published_url="",
        published_date="",
        title=OLD_TITLE,
    ):
        return {
            "id": DEST_PAGE_ID,
            "properties": {
                "同期ID": self._rich(SYNC_ID),
                "記事タイトル": self._title(title),
                "投稿状態": self._select(posting),
                "品質状態": self._select(quality),
                "note下書きID": self._rich(draft_id),
                "note公開URL": {"url": published_url or None},
                "投稿日": {"date": ({"start": published_date} if published_date else None)},
            },
        }

    def _pipeline(self):
        pipeline = types.SimpleNamespace()
        pipeline.ARTICLE_STATUS_READY = "Ready"
        pipeline.CONTENT_STATUS_DEEP_DIVE = "Deep Dive"
        pipeline.DEEP_DIVE_MODEL_BUDGET = _Budget()
        pipeline.logger = types.SimpleNamespace(warning=lambda *a, **k: None, info=lambda *a, **k: None)
        pipeline.legal_safety_gate = lambda repo: (True, "safe")
        pipeline.get_regen_test_items = lambda limit, query: [
            {
                "notion_page_id": SYNC_ID,
                "repo": {"nameWithOwner": "source candidate", "source": "ArXiv"},
                "screening_score": 82,
                "screening_reason": "high-value exact target",
            }
        ]
        return pipeline

    def _approved_env(self):
        return {
            "READY_DRAFT_REGENERATION_CONFIRM": target.CONFIRM_TOKEN,
            "READY_DRAFT_REGENERATION_SYNC_ID": SYNC_ID,
        }

    def test_sync_id_is_strict_exact_32_hex(self):
        self.assertEqual(target._normalize_sync_id(SYNC_ID), SYNC_ID)
        for bad in ("", "3f54", SYNC_ID + "00", SYNC_ID + "-", "g" * 32):
            with self.subTest(bad=bad), self.assertRaises(target.ReadyDraftRegenerationError):
                target._normalize_sync_id(bad)

    def test_destination_preflight_requires_existing_unpublished_preparing_draft(self):
        with patch.object(target.ready_sync, "_query_db", return_value=[self._destination_row()]):
            state = target.destination_preflight(SYNC_ID)
        self.assertEqual(state["sync_id"], SYNC_ID)
        self.assertEqual(state["destination_page_id"], DEST_PAGE_ID)
        self.assertEqual(state["note_draft_id"], DRAFT_ID)
        self.assertEqual(state["title"], OLD_TITLE)

        blocked = (
            self._destination_row(posting="投稿済み"),
            self._destination_row(quality="Ready取消"),
            self._destination_row(draft_id=""),
            self._destination_row(published_url="https://note.com/example/n/x"),
            self._destination_row(published_date="2026-10-12"),
        )
        for row in blocked:
            with self.subTest(row=row["properties"]), patch.object(target.ready_sync, "_query_db", return_value=[row]):
                with self.assertRaises(target.ReadyDraftRegenerationError):
                    target.destination_preflight(SYNC_ID)

    def test_draft_route_identity_uses_stored_note_draft_id_not_title(self):
        good = f"https://note.com/notes/{DRAFT_ID}/edit"
        editor_good = f"https://editor.note.com/notes/{DRAFT_ID}/edit?foo=1"
        wrong = "https://note.com/notes/notherdraft123/edit"
        self.assertEqual(target._draft_id_from_edit_url(good), DRAFT_ID)
        self.assertEqual(target._draft_id_from_edit_url(editor_good), DRAFT_ID)
        self.assertEqual(target._draft_id_from_edit_url(wrong), "notherdraft123")
        self.assertEqual(target._draft_id_from_edit_url("https://note.com/new"), "")
        self.assertTrue(target._same_exact_draft_route(good, editor_good, DRAFT_ID))
        self.assertFalse(target._same_exact_draft_route(good, wrong, DRAFT_ID))

    def test_regeneration_persists_only_exact_ready_target_and_reconciles_same_queue_row(self):
        pipeline = self._pipeline()
        calls = []
        pipeline.generate_intelligence_report = lambda repo, **kwargs: calls.append((repo, kwargs)) or (
            "# New public title\n\ncurrent manuscript",
            "accepted",
        )

        before = {
            "sync_id": SYNC_ID,
            "destination_page_id": DEST_PAGE_ID,
            "note_draft_id": DRAFT_ID,
            "title": OLD_TITLE,
            "posting_state": "投稿準備中",
            "quality_state": "Ready",
        }
        after = {**before, "title": NEW_TITLE}
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            target, "destination_preflight", side_effect=[before, after]
        ), patch.object(
            target.article_revalidation, "_read_current_statuses", return_value=("Ready", "Deep Dive")
        ), patch.object(
            target.article_revalidation, "_cap_validation_budget", return_value=8
        ), patch.object(
            target.ready_sync, "sync_note_ready_db", return_value={"source_ready": 1}
        ) as sync:
            result = target.run_ready_regeneration(pipeline, SYNC_ID)

        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["sync_id"], SYNC_ID)
        self.assertEqual(result["note_draft_id"], DRAFT_ID)
        self.assertEqual(len(calls), 1)
        kwargs = calls[0][1]
        self.assertEqual(kwargs["notion_page_id"], SYNC_ID)
        self.assertTrue(kwargs["persist_results"])
        self.assertEqual(kwargs["candidate_origin"], "manual_ready_draft_regeneration")
        sync.assert_called_once_with(target_sync_id=SYNC_ID)

    def test_regeneration_refuses_non_ready_or_rejected_without_note_mutation(self):
        pipeline = self._pipeline()
        pipeline.generate_intelligence_report = lambda *a, **k: self.fail("must not generate non-Ready target")
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            target, "destination_preflight", return_value={
                "sync_id": SYNC_ID,
                "destination_page_id": DEST_PAGE_ID,
                "note_draft_id": DRAFT_ID,
                "title": OLD_TITLE,
                "posting_state": "投稿準備中",
                "quality_state": "Ready",
            }
        ), patch.object(
            target.article_revalidation, "_read_current_statuses", return_value=("Needs Editorial Review", "Deep Dive")
        ):
            with self.assertRaisesRegex(target.ReadyDraftRegenerationError, "source is not Ready"):
                target.run_ready_regeneration(pipeline, SYNC_ID)

        pipeline = self._pipeline()
        pipeline.generate_intelligence_report = lambda *a, **k: ("draft", "rejected")
        with patch.dict(os.environ, self._approved_env(), clear=True), patch.object(
            target, "destination_preflight", return_value={
                "sync_id": SYNC_ID,
                "destination_page_id": DEST_PAGE_ID,
                "note_draft_id": DRAFT_ID,
                "title": OLD_TITLE,
                "posting_state": "投稿準備中",
                "quality_state": "Ready",
            }
        ), patch.object(
            target.article_revalidation, "_read_current_statuses", return_value=("Ready", "Deep Dive")
        ), patch.object(
            target.article_revalidation, "_cap_validation_budget", return_value=8
        ), patch.object(target.ready_sync, "sync_note_ready_db", return_value={"source_ready": 0}) as sync:
            with self.assertRaisesRegex(target.ReadyDraftRegenerationError, "did not pass"):
                target.run_ready_regeneration(pipeline, SYNC_ID)
        sync.assert_called_once_with(target_sync_id=SYNC_ID)

    def test_existing_cover_replacement_requires_media_change_proof(self):
        source = inspect.getsource(target.apply_current_article_to_existing_draft)
        self.assertIn("media_changed=", source)
        self.assertIn("_cover_changed", source)

    def test_workflow_is_exact_manual_existing_draft_only(self):
        from pathlib import Path

        text = Path(".github/workflows/ready-draft-regenerate-once.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch", text)
        self.assertIn("sync_id", text)
        self.assertIn("RUN_ONCE", text)
        self.assertIn("READY_DRAFT_REGENERATION_CONFIRM", text)
        self.assertIn("ready_draft_regeneration.py", text)
        self.assertNotIn("note-create-draft.yml", text)
        self.assertNotIn("/new", text)
        self.assertNotIn("publish", text.lower())


if __name__ == "__main__":
    unittest.main()
