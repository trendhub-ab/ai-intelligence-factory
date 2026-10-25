"""Provider-free isolation and provenance tests: not editorial score/Fact-Gate proof."""
import pytest

from tests.v3_writer_independent_prototype import (
    EvidencePacket,
    SourceFact,
    build_writer_prompt,
    packet_fingerprint,
    validate_packet,
)


def fixture_packet():
    return EvidencePacket(
        topic="Transformerの計算量を柔軟に変える手法",
        primary_url="https://arxiv.org/abs/2610.20588v1",
        source_urls=("https://arxiv.org/abs/2610.20588v1",),
        facts=(
            SourceFact(
                fact_id="E1",
                statement="学習済みモデルの内部ユニットを順位付けする",
                source_url="https://arxiv.org/abs/2610.20588v1",
            ),
            SourceFact(
                fact_id="E2",
                statement="計算量50%削減時の精度低下0.8%",
                source_url="https://arxiv.org/abs/2610.20588v1",
                qualifier="報告された評価条件内",
            ),
        ),
    )


def test_brief_is_single_article_evidence_only():
    brief = build_writer_prompt(fixture_packet())
    assert "17歳" in brief
    assert "中性的" in brief
    assert "E1" in brief and "E2" in brief
    assert "報告された評価条件内" in brief
    assert "Markdown完成記事だけ" in brief
    for unwanted in ("MANAGEMENT DATA", "Decision Score", "Ready", "Publication Gate", "Notion", "Fact-Safe Review"):
        assert unwanted not in brief


def test_provenance_is_stable_and_sensitivity_is_explicit():
    packet = fixture_packet()
    assert packet_fingerprint(packet) == packet_fingerprint(packet)
    modified = EvidencePacket(
        packet.topic,
        packet.primary_url,
        packet.source_urls,
        packet.facts[:-1],
    )
    assert packet_fingerprint(modified) != packet_fingerprint(packet)


@pytest.mark.parametrize("packet", [
    EvidencePacket("", "https://a.example/p", ("https://a.example/p",), (SourceFact("1", "x", "https://a.example/p"),)),
    EvidencePacket("t", "https://a.example/p", ("https://a.example/p",), ()),
    EvidencePacket("t", "https://absent.example/p", ("https://a.example/p",), (SourceFact("1", "x", "https://a.example/p"),)),
    EvidencePacket("t", "http://a.example/p", ("http://a.example/p",), (SourceFact("1", "x", "http://a.example/p"),)),
    EvidencePacket("t", "https://a.example/p", ("https://a.example/p",), (SourceFact("1", "x", "https://other.example/p"),)),
    EvidencePacket("t", "https://a.example/p", ("https://a.example/p",), (SourceFact("1", "x", "https://a.example/p"), SourceFact("1", "y", "https://a.example/p"))),
])
def test_incomplete_or_unauthorized_fact_pack_fails_closed(packet):
    with pytest.raises(ValueError):
        validate_packet(packet)


def test_signature_has_no_management_or_api_parameters():
    import inspect
    assert tuple(inspect.signature(build_writer_prompt).parameters) == ("packet",)
    source = inspect.getsource(build_writer_prompt)
    assert "genai" not in source
    assert "requests." not in source
    assert "publish" not in source
