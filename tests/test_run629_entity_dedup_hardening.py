from pathlib import Path

import candidate_identity as ci
import decision_intelligence_run255_core as di


def test_unbound_evidence_cannot_hijack_arxiv_entity():
    repo = {
        "source": "ArXiv",
        "nameWithOwner": "Paper",
        "url": "https://arxiv.org/abs/2608.12345",
        "primaryUrl": "https://arxiv.org/abs/2608.12345",
    }
    source_info = {
        "primary_url": "https://arxiv.org/abs/2608.12345",
        "evidence_documents": [{
            "url": "https://github.com/other/tool",
            "decision_eligible": False,
            "entity_binding": "UNBOUND",
        }],
    }
    resolved = di.resolve_canonical_entity_id(repo, source_info)
    assert resolved.entity_id == "arxiv:2608.12345"
    assert resolved.status == "RESOLVED"


def test_only_explicitly_bound_evidence_may_contribute_identity_alias():
    repo = {
        "source": "HackerNews",
        "nameWithOwner": "Tool launch",
        "url": "https://news.ycombinator.com/item?id=1",
    }
    source_info = {
        "evidence_documents": [{
            "url": "https://github.com/acme/tool",
            "decision_eligible": True,
            "entity_binding": "IDENTITY_ANCHOR",
        }],
    }
    resolved = di.resolve_canonical_entity_id(repo, source_info)
    assert resolved.entity_id == "github:acme/tool"
    assert resolved.status == "RESOLVED"


def test_github_global_navigation_never_becomes_technology_entity():
    for url in (
        "https://github.com/collections/machine-learning",
        "https://github.com/enterprise/ai",
        "https://github.com/solutions/ai",
    ):
        resolved = di.resolve_canonical_entity_id({
            "source": "HackerNews",
            "nameWithOwner": "GitHub page",
            "url": url,
            "primaryUrl": url,
        })
        assert resolved.status == "AMBIGUOUS"
        assert resolved.entity_id.startswith("legacy:")


def test_official_vendor_revision_is_content_event_identity_not_base_evidence_identity():
    row = {
        "source": "OfficialVendor",
        "url": "https://vendor.example/releases?aif_revision=abcdef1234567890",
        "primaryUrl": "https://vendor.example/releases",
        "sourceDetails": {
            "official_release_url": "https://vendor.example/releases",
            "candidate_revision": "abcdef1234567890",
        },
    }
    assert ci.candidate_identity_urls(row) == {
        "https://vendor.example/releases?aif_revision=abcdef1234567890"
    }


def test_external_review_uses_same_writer_lock_as_daily_and_bootstrap():
    workflow = Path(".github/workflows/external-review-import.yml").read_text(encoding="utf-8")
    assert "group: ai-intelligence-gemini-budget" in workflow
    assert "group: ai-intelligence-external-review-import" not in workflow
