import inspect

import run388_zero_model_full_gate_preflight as r388


def test_exact_six_non_reader_targets_are_pinned():
    assert len(r388.TARGETS) == 6
    assert len({t.page_id for t in r388.TARGETS}) == 6
    assert sum(t.kind == "official_source_migration" for t in r388.TARGETS) == 5
    assert sum(t.kind == "surface_clean_but_unproven" for t in r388.TARGETS) == 1


def test_five_migrated_rows_still_require_deterministic_surface_revalidation():
    migrated = [t for t in r388.TARGETS if t.kind == "official_source_migration"]
    assert len(migrated) == 5
    assert all(t.source_migrated and t.primary_evidence_rechecked for t in migrated)
    assert all(r388.classify(t) == "DETERMINISTIC_SURFACE_REVALIDATION_REQUIRED" for t in migrated)


def test_semantic_router_is_not_promoted_by_clean_surface_alone():
    semantic = next(t for t in r388.TARGETS if t.kind == "surface_clean_but_unproven")
    assert semantic.deterministic_surface_proven is True
    assert r388.classify(semantic) == "FULL_FACT_EVIDENCE_GATE_REQUIRED"


def test_preflight_has_no_model_or_write_dependency():
    source = inspect.getsource(r388)
    forbidden = (
        "call_gemini", "client.models", "generate_content", "api.notion.com", "requests.patch",
        "requests.post", "note_ready_sync", "publish",
    )
    assert all(token not in source for token in forbidden)
    assert all(r388.classify(t) != "FULL_GATE_PROVEN" for t in r388.TARGETS)
