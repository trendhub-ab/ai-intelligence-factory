from unittest.mock import patch

import ready_note_cover_apply as target


SYNC_ID = "3f8479ffdca98146b90ddf1fc42c40ef"
TITLE = "対象記事タイトル"
DRAFT_ID = "nabc123"


def test_destination_private_row_preserves_stable_draft_identity():
    page = {
        "id": "destination-page",
        "properties": {
            "同期ID": {"rich_text": [{"plain_text": SYNC_ID}]},
            "投稿状態": {"select": {"name": "投稿準備中"}},
            "品質状態": {"select": {"name": "Ready"}},
            "記事タイトル": {"title": [{"plain_text": TITLE}]},
            "投稿日": {"date": None},
            "note公開URL": {"url": None},
            "note下書きID": {"rich_text": [{"plain_text": DRAFT_ID}]},
        },
    }
    with patch.object(target.ready_sync, "_query_db", return_value=[page]):
        result = target._destination_private_row(SYNC_ID)

    assert result["draft_id"] == DRAFT_ID
