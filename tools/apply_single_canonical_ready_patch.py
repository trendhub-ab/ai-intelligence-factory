from pathlib import Path

path = Path("pipeline.py")
text = path.read_text(encoding="utf-8")

old = '''def _notion_code_caption(block: dict) -> str:
    code = block.get("code") or {}
    parts = []
    for item in code.get("caption") or []:
        parts.append(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
    return "".join(parts)


def _notion_page_manuscript_blocks(page_id: str, headers: dict) -> list[dict]:
'''
new = '''def _notion_code_caption(block: dict) -> str:
    code = block.get("code") or {}
    parts = []
    for item in code.get("caption") or []:
        parts.append(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
    return "".join(parts)


def _notion_code_body(block: dict) -> str:
    code = block.get("code") or {}
    return "".join(
        item.get("plain_text") or ((item.get("text") or {}).get("content")) or ""
        for item in code.get("rich_text") or []
    )


def _notion_page_manuscript_blocks(page_id: str, headers: dict) -> list[dict]:
'''
assert text.count(old) == 1, "caption insertion anchor changed"
text = text.replace(old, new, 1)

old = '''def _notion_review_manuscript_block_ids(page_id: str, headers: dict) -> list[str]:
    return [
        block.get("id") for block in _notion_page_manuscript_blocks(page_id, headers)
        if block.get("id") and _notion_code_caption(block) == MANUSCRIPT_CAPTION_REVIEW
    ]


def _rollback_notion_manuscript_children(block_ids: list[str], repo_name: str, headers: dict) -> None:
'''
new = '''def _notion_review_manuscript_block_ids(page_id: str, headers: dict) -> list[str]:
    return [
        block.get("id") for block in _notion_page_manuscript_blocks(page_id, headers)
        if block.get("id") and _notion_code_caption(block) == MANUSCRIPT_CAPTION_REVIEW
    ]


def _notion_ready_block_matches_expected(block: dict, expected_body: str) -> bool:
    body = _notion_code_body(block)
    if body != str(expected_body or ""):
        return False
    caption = _notion_code_caption(block)
    if caption == MANUSCRIPT_CAPTION_REVIEW:
        return False

    # run194 installs the current content-addressed publication contract in production.
    # Once installed, legacy/captionless blocks may be historical inputs but can never be
    # the surviving canonical Ready block.
    if globals().get("CURRENT_PUBLICATION_CONTRACT"):
        try:
            import publication_contract as _publication_contract
            return _publication_contract.is_exact_current_ready_block(body, caption, expected_body)
        except Exception as exc:
            logger.error(f"[NOTION READY CONTRACT CHECK FAILED] {exc}")
            return False
    return True


def _ensure_single_canonical_manuscript_before_ready(
    page_id: str, repo_name: str, expected_body: str, headers: dict,
) -> bool:
    """Fail closed unless exactly one expected manuscript survives before Ready commit.

    The expected body must already exist. Only then may stale Review, legacy captionless,
    stale Ready, or duplicate exact-current blocks be archived. Any archive/readback failure
    prevents Ready. The surviving block is re-read after cleanup; ordering alone never chooses
    between different manuscript bodies.
    """
    try:
        blocks = _notion_page_manuscript_blocks(page_id, headers)
    except Exception as exc:
        logger.error(
            f"[NOTION READY CANONICAL READ FAILED] {repo_name} -> "
            f"Ready前のmanuscript確認不能: {exc}"
        )
        return False

    candidates = [
        block for block in blocks
        if _notion_ready_block_matches_expected(block, expected_body)
    ]
    if not candidates:
        logger.error(
            f"[NOTION READY CANONICAL MISSING] {repo_name} -> "
            "今回生成した正本manuscriptを確認できないためReadyを拒否"
        )
        return False

    # Multiple candidates are byte-identical and carry the exact same current contract.
    # Keep the first stable block and archive every other manuscript block.
    canonical = candidates[0]
    canonical_id = str(canonical.get("id") or "").strip()
    if not canonical_id:
        logger.error(f"[NOTION READY CANONICAL ID MISSING] {repo_name}")
        return False

    for block in blocks:
        block_id = str(block.get("id") or "").strip()
        if block is canonical:
            continue
        if not block_id:
            logger.error(f"[NOTION READY STALE ID MISSING] {repo_name}")
            return False
        try:
            res = requests.delete(
                f"https://api.notion.com/v1/blocks/{block_id}",
                headers=headers, timeout=10,
            )
        except Exception as exc:
            logger.error(
                f"[NOTION READY STALE ARCHIVE EXCEPTION] {repo_name} block={block_id}: {exc}"
            )
            return False
        if res.status_code != 200:
            logger.error(
                f"[NOTION READY STALE ARCHIVE ERROR] {repo_name} block={block_id} -> {res.text}"
            )
            return False

    try:
        remaining = _notion_page_manuscript_blocks(page_id, headers)
    except Exception as exc:
        logger.error(
            f"[NOTION READY CANONICAL VERIFY FAILED] {repo_name} -> cleanup後の再読込失敗: {exc}"
        )
        return False

    if len(remaining) != 1:
        logger.error(
            f"[NOTION READY CANONICAL COUNT FAILED] {repo_name} -> "
            f"cleanup後manuscript_count={len(remaining)}"
        )
        return False
    final = remaining[0]
    if str(final.get("id") or "").strip() != canonical_id:
        logger.error(f"[NOTION READY CANONICAL ID CHANGED] {repo_name}")
        return False
    if not _notion_ready_block_matches_expected(final, expected_body):
        logger.error(f"[NOTION READY CANONICAL BODY FAILED] {repo_name}")
        return False
    return True


def _rollback_notion_manuscript_children(block_ids: list[str], repo_name: str, headers: dict) -> None:
'''
assert text.count(old) == 1, "single-canonical helper insertion anchor changed"
text = text.replace(old, new, 1)

old = '''    # Phase 2: children保存成功（またはスキップ）後にのみ、
    # properties（Deep Dive / Readyへのcommit）を行う。
    properties = build_notion_properties(
'''
new = '''    # Readyへ進む前に、今回生成した正本が実在し、それ以外の旧Review / 旧Ready /
    # captionless legacy / duplicate exact-current がすべて整理されたことを再読込で確認する。
    # cleanup途中で失敗した場合は正本を残してPending Retryへ回す。propertiesは触らない。
    if not _ensure_single_canonical_manuscript_before_ready(
        page_id, repo_name, clean_manuscript, headers,
    ):
        _mark_pending_retry_or_escalate(
            page_id, repo_name,
            "Notion single-canonical manuscript verification failed before Ready commit",
        )
        return False

    # ここまで来た正本は次回Retryの安全な復元点。以後properties commitが失敗しても
    # canonical manuscript自体はrollbackしない（旧稿は既にarchive済みのため）。
    appended_block_ids = []

    # Phase 2: single-canonical確認成功後にのみ、properties（Deep Dive / Ready）をcommitする。
    properties = build_notion_properties(
'''
assert text.count(old) == 1, "pre-Ready insertion anchor changed"
text = text.replace(old, new, 1)

old = '''        logger.info(f"[NOTION READY COMMITTED] {repo_name} -> Deep Diveへアップグレード完了")
        # Ready commit後の旧Review原稿整理はbest-effort。ここでread不能でも、
        # 既に成功したReady commitをPending Retryへ巻き戻さない。
        try:
            review_block_ids = _notion_review_manuscript_block_ids(page_id, headers)
        except Exception as cleanup_exc:
            logger.warning(
                f"[NOTION REVIEW CLEANUP SKIPPED] {repo_name} -> "
                f"旧Review manuscript確認不能: {cleanup_exc}"
            )
            review_block_ids = []
        if review_block_ids:
            _rollback_notion_manuscript_children(review_block_ids, repo_name, headers)
        return True
'''
new = '''        logger.info(f"[NOTION READY COMMITTED] {repo_name} -> Deep Diveへアップグレード完了")
        # stale manuscript cleanupはReady commit前にstrictに完了・再検証済み。
        return True
'''
assert text.count(old) == 1, "post-Ready cleanup replacement anchor changed"
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("patched pipeline.py with strict single-canonical Ready persistence")
