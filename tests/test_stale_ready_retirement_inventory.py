import stale_ready_retirement_audit as audit


def test_ready_inventory_reconstruction_preserves_source_identity():
    page={"id":"abc","properties":{}}
    state={"title":"x","source":"HackerNews","original_url":"https://news.ycombinator.com/item?id=1","primary_url":"https://news.ycombinator.com/item?id=1"}
    item=audit._repo_from_ready(page,state)
    assert item["revalidation_stale_ready"] is True
    assert item["notion_page_id"]=="abc"
    assert item["repo"]["source"]=="HackerNews"
    assert item["repo"]["url"].endswith("id=1")


def test_audit_uses_ready_status_population_not_deep_dive_regen_selector():
    from pathlib import Path
    source=Path("stale_ready_retirement_audit.py").read_text(encoding="utf-8")
    assert "SOURCE_ARTICLE_STATUS" in source
    assert "SOURCE_READY" in source
    assert "get_regen_test_items" not in source
    assert "select_revalidation_items" not in source
