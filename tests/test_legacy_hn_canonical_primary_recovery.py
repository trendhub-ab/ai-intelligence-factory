import pipeline

class Response:
    def __init__(self,payload,status=200): self._payload=payload; self.status_code=status
    def raise_for_status(self):
        if self.status_code>=400: raise RuntimeError("http")
    def json(self): return self._payload

def test_hn_recovery_uses_exact_item_external_url(monkeypatch):
    monkeypatch.setattr(pipeline.evidence_ledger if hasattr(pipeline,"evidence_ledger") else pipeline, "NOTION_API_KEY", pipeline.NOTION_API_KEY, raising=False)
    monkeypatch.setattr(pipeline.requests,"get",lambda url,timeout=10: Response({"id":123,"type":"story","url":"https://netflixtechblog.com/genrec"}))
    repo={"source":"HackerNews","url":"https://news.ycombinator.com/item?id=123","primaryUrl":"https://news.ycombinator.com/item?id=123","sourceDetails":{"external_url":"https://news.ycombinator.com/item?id=123"}}
    assert pipeline._resolve_hn_story_external_url(repo["url"])=="https://netflixtechblog.com/genrec"

def test_hn_recovery_refuses_self_post_or_noncanonical(monkeypatch):
    monkeypatch.setattr(pipeline.requests,"get",lambda url,timeout=10: Response({"id":123,"type":"story"}))
    assert pipeline._resolve_hn_story_external_url("https://news.ycombinator.com/item?id=123")==""
    assert pipeline._resolve_hn_story_external_url("https://news.ycombinator.com/from?site=example.com")==""
    assert pipeline._resolve_hn_story_external_url("https://evil.example/item?id=123")==""

def test_hn_recovery_refuses_hn_external_url(monkeypatch):
    monkeypatch.setattr(pipeline.requests,"get",lambda url,timeout=10: Response({"id":123,"type":"story","url":"https://news.ycombinator.com/item?id=999"}))
    assert pipeline._resolve_hn_story_external_url("https://news.ycombinator.com/item?id=123")==""
