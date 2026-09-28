from __future__ import annotations

from unittest.mock import patch

import note_ready_sync as ready_sync
import publication_contract as contract


TITLE = "AIへの指示は短いほど賢くなる？「プロンプト最小化」が解き明かすLLMの意外な弱点。"
BODY = f"""# {TITLE}

## どんな内容？
既存のReady本文です。

## なぜ重要？
本文を再生成せずアイキャッチだけ修復するための検証です。
"""


def _block(body: str, caption: str) -> dict:
    return {
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": body}],
            "caption": [{"plain_text": caption}],
        },
    }


def _stale_caption(body: str, *, body_sha: str | None = None, contract_id: str | None = None) -> str:
    return (
        f"{contract.READY_CAPTION_PREFIX}"
        f"contract={contract_id or contract.CONTRACT_ID}"
        "|style=human_narrative"
        f"|policy_sha256={'0' * 64}"
        f"|manuscript_sha256={body_sha or contract.manuscript_sha256(body)}"
    )


def test_visual_repair_accepts_stale_policy_only_when_body_bytes_authenticate():
    block = _block(BODY, _stale_caption(BODY))
    with patch.object(ready_sync, "_block_children", return_value=[block]):
        assert ready_sync._source_current_ready_manuscript("page") == ""
        manuscript, current = ready_sync._source_ready_manuscript_for_visual_repair("page", TITLE)
    assert manuscript == BODY
    assert current is False


def test_visual_repair_rejects_bad_body_sha():
    block = _block(BODY, _stale_caption(BODY, body_sha="f" * 64))
    with patch.object(ready_sync, "_block_children", return_value=[block]):
        manuscript, current = ready_sync._source_ready_manuscript_for_visual_repair("page", TITLE)
    assert manuscript == ""
    assert current is False


def test_visual_repair_rejects_wrong_public_title():
    block = _block(BODY, _stale_caption(BODY))
    with patch.object(ready_sync, "_block_children", return_value=[block]):
        manuscript, current = ready_sync._source_ready_manuscript_for_visual_repair("page", "別のタイトル")
    assert manuscript == ""
    assert current is False


def test_visual_repair_rejects_foreign_ready_contract():
    block = _block(BODY, _stale_caption(BODY, contract_id="foreign-contract"))
    with patch.object(ready_sync, "_block_children", return_value=[block]):
        manuscript, current = ready_sync._source_ready_manuscript_for_visual_repair("page", TITLE)
    assert manuscript == ""
    assert current is False
