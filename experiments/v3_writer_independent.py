"""Provider-free V3 Independent Creative Writer *input* contract.

This module is deliberately NOT connected to Production, Gemini, Notion or note.
It builds a minimal evidence-scoped writer prompt; it does not generate, review,
score, persist, publish or certify any article.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SourceFact:
    fact_id: str
    statement: str
    source_url: str
    qualifier: str = ""


@dataclass(frozen=True)
class EvidencePacket:
    topic: str
    primary_url: str
    source_urls: tuple[str, ...]
    facts: tuple[SourceFact, ...]


def _valid_https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def validate_packet(packet: EvidencePacket) -> None:
    if not isinstance(packet, EvidencePacket):
        raise ValueError("Typed EvidencePacket required")
    if not packet.topic.strip() or not packet.source_urls or not packet.facts:
        raise ValueError("Incomplete evidence packet")
    if len(set(packet.source_urls)) != len(packet.source_urls):
        raise ValueError("Duplicate source URLs")
    if not all(_valid_https_url(url) for url in packet.source_urls):
        raise ValueError("Only absolute HTTPS evidence sources allowed")
    if packet.primary_url not in packet.source_urls:
        raise ValueError("Primary source must belong to evidence sources")
    fact_ids: set[str] = set()
    for fact in packet.facts:
        if not isinstance(fact, SourceFact):
            raise ValueError("Typed SourceFact required")
        if not fact.fact_id.strip() or not fact.statement.strip():
            raise ValueError("Blank fact ID or evidence statement")
        if fact.fact_id in fact_ids:
            raise ValueError("Duplicate fact IDs")
        if fact.source_url not in packet.source_urls:
            raise ValueError("Unlisted source for fact")
        fact_ids.add(fact.fact_id)


def packet_fingerprint(packet: EvidencePacket) -> str:
    """Stable input-provenance digest; not a truthfulness or source-verification claim."""
    validate_packet(packet)
    payload = {
        "topic": packet.topic,
        "primary_url": packet.primary_url,
        "source_urls": list(packet.source_urls),
        "facts": [
            {
                "fact_id": fact.fact_id,
                "statement": fact.statement,
                "source_url": fact.source_url,
                "qualifier": fact.qualifier,
            }
            for fact in packet.facts
        ],
    }
    serial = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


def build_writer_prompt(packet: EvidencePacket) -> str:
    """One plain article request, no management metadata or 5-stage JSON requirement."""
    validate_packet(packet)
    facts = "\n".join(
        f"- [{f.fact_id}] {f.statement}"
        + (f"（条件・留保：{f.qualifier}）" if f.qualifier else "")
        + f" 出典: {f.source_url}"
        for f in packet.facts
    )
    return (
        "あなたはAIニュースを面白く伝える日本語の書き手。\n"
        "AIにワクワクする17歳のような素朴な好奇心を持つ。ただし年齢・性別を演じない。\n"
        "会話のように自然で中性的な日本語で、根拠から読者が発見にたどり着く記事を書く。\n"
        "最初に『何が不思議か』を見つけ、具体的な事実から理由や違いを掘り下げる。\n"
        "驚いたと宣言するだけの文章、架空の体験、事実の創作、硬い報告書調を避ける。\n"
        "与えた根拠にない仕組み・因果・性能は事実として補わない。分からない点は分からないと書く。\n"
        "出力は読者向けのMarkdown完成記事だけ。編集メモや審査結果は書かない。\n\n"
        f"テーマ: {packet.topic}\n"
        f"一次情報: {packet.primary_url}\n"
        "確認済み資料の事実（括弧内の条件・留保を保持すること）:\n"
        f"{facts}\n"
    )
