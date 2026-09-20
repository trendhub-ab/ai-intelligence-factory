import evidence_ledger

class R:
    def raise_for_status(self): pass
    def json(self):
        return {"results":[{"properties":{
            evidence_ledger.P_TECH_PAGE:{"rich_text":[{"plain_text":"tech-1"}]},
            evidence_ledger.P_URL:{"url":"https://netflixtechblog.com/genrec"},
            evidence_ledger.P_RESOLVED:{"url":"https://netflixtechblog.com/genrec"},
            evidence_ledger.P_ROLE:{"rich_text":[{"plain_text":"PRIMARY_SOURCE"}]},
            evidence_ledger.P_ACTIVE:{"checkbox":True}, evidence_ledger.P_ELIGIBLE:{"checkbox":True},
            evidence_ledger.P_AUTHORITY:{"rich_text":[{"plain_text":"PRIMARY_FIRST_PARTY"}]},
            evidence_ledger.P_BINDING:{"rich_text":[{"plain_text":"LEGACY_RESOLVED_PRIMARY"}]},
            evidence_ledger.P_HEALTH:{"select":{"name":"VERIFIED"}},
        }}]}

def test_recover_primary_url_requires_proven_active_primary(monkeypatch):
    monkeypatch.setattr(evidence_ledger,"ENABLE_EVIDENCE_LEDGER",True)
    monkeypatch.setattr(evidence_ledger,"NOTION_EVIDENCE_DATA_SOURCE_ID","ds")
    monkeypatch.setattr(evidence_ledger.requests,"post",lambda *a,**k:R())
    assert evidence_ledger.recover_primary_url("token",tech_page_id="tech-1")=="https://netflixtechblog.com/genrec"

def test_recover_primary_url_fails_closed_without_identity(monkeypatch):
    monkeypatch.setattr(evidence_ledger,"ENABLE_EVIDENCE_LEDGER",True)
    assert evidence_ledger.recover_primary_url("token")==""


def test_diagnose_primary_recovery_reports_rejection_without_content(monkeypatch):
    monkeypatch.setattr(evidence_ledger,"ENABLE_EVIDENCE_LEDGER",True)
    monkeypatch.setattr(evidence_ledger,"NOTION_EVIDENCE_DATA_SOURCE_ID","ds")
    monkeypatch.setattr(evidence_ledger.requests,"post",lambda *a,**k:R())
    audit=evidence_ledger.diagnose_primary_recovery("token",tech_page_id="tech-1")
    assert audit["matched"]==1
    assert audit["accepted"]==1
    assert audit["unique_candidates"]==1
    assert "url" not in audit and "extract" not in audit
