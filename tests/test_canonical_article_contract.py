import importlib
import importlib.util
import inspect


def _load():
    spec = importlib.util.find_spec("canonical_article_contract")
    assert spec is not None, "canonical_article_contract module must exist"
    return importlib.import_module("canonical_article_contract")


LEGACY_QUOTAS = (
    "原則2〜3個",
    "4個目",
    "最大3項目",
    "2段落続いたら",
    "3つ以上連打",
)


def test_writer_contract_contains_canonical_dimensions_and_priority():
    cac = _load()
    text = cac.canonical_writer_contract()
    for token in (
        cac.CANONICAL_ARTICLE_CONTRACT_MARKER,
        "Reader Question",
        "Why Now",
        "Central Conclusion",
        "Discovery",
        "Capability Boundary",
        "Reader Decision",
        "Evidence Integrity",
        "記事を全部説明するな",
        "固定見出しや固定順序にしない",
    ):
        assert token in text


def test_writer_contract_preserves_fact_evidence_and_rejects_invented_specificity():
    cac = _load()
    text = cac.canonical_writer_contract()
    assert "Evidence、重要数値、条件、反証、対象範囲を落とさない" in text
    assert "架空の経験・感情・因果・会話・多数派認識を作らない" in text
    assert "専門語の固定個数制限は設けない" in text


def test_deconflict_removes_legacy_numeric_quotas_before_contract():
    cac = _load()
    legacy = "\n".join(
        [
            "この無料ARTICLEで読者が本当に覚える専門概念を内部で原則2〜3個に絞る。4個目がないとDecisionを誤解する場合だけ4個まで許す。",
            "手順・機能・注意点の列挙はそれぞれ最大3項目まで。",
            "記事全体の温度を1〜2個の口語句で済ませず、硬い説明が2段落続いたら次の段落では、追加説明を足さず、既存文を「読者の判断／具体場面／平易な一言」のどれかへ置き換えて人間の言葉へ戻す。",
            "短文を3つ以上連打して広告コピーのように煽らない。",
        ]
    )
    out = cac.ensure_writer_contract("SOURCE BOUNDARY\nEvidence-to-Decision\n" + legacy)
    for token in LEGACY_QUOTAS:
        assert token not in out
    assert out.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
    assert "SOURCE BOUNDARY" in out
    assert "Evidence-to-Decision" in out


def test_writer_and_final_check_are_idempotent():
    cac = _load()
    once = cac.ensure_final_reader_check(cac.ensure_writer_contract("BASE"))
    twice = cac.ensure_final_reader_check(cac.ensure_writer_contract(once))
    assert once == twice
    assert once.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
    assert once.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER) == 1


def test_reader_repair_keeps_fact_fixed_and_allows_reordering():
    cac = _load()
    text = cac.canonical_reader_repair_contract()
    assert "Reader Repair｜Factを固定した読者導線修正" in text
    assert "Decision/Score/Action" in text
    assert "段落・見出しを再編" in text
    assert "新しい数値、製品名、API名、比較対象、使用経験、感情、因果、保証表現を追加しない" in text
    assert "通らなければReadyにしない" in text


def test_canonical_module_has_no_provider_or_network_dependency():
    cac = _load()
    src = inspect.getsource(cac)
    for forbidden in (
        "_generate_via_chat(",
        "genai.Client(",
        "requests.",
        "httpx.",
        "NOTION_",
    ):
        assert forbidden not in src
