"""Run348: zero-API adversarial editorial lab.

Generate a large deterministic Japanese mutation corpus and exercise existing pure
signals without Gemini, Notion, network access, persistence, or pipeline import.
This is diagnostic infrastructure: it does not weaken Production gates.  It exposes
false-positive / false-negative pressure so later fixes can be narrow and proven.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from editorial_naturalness import ai_style_composite_signals
from fact_validation_signals import _numeric_condition_compatible, _normalize_numeric_evidence_text
from reader_experience_signals import reader_experience_signals

OK = "OK"
BORDERLINE = "BORDERLINE"
FAIL = "FAIL"
FAMILIES = ("fact", "reader_value", "human_appeal", "score_narrative")

DISPLAY_VARIANTS = [
    {"intro": "導入", "conclusion": "結論", "why": "なぜ重要なのか", "what": "何が変わるのか",
     "key": "ポイント", "decision": "私ならどうする", "final": "まとめ"},
]


@dataclass(frozen=True)
class AdversarialCase:
    case_id: str
    family: str
    expected: str
    text: str
    evidence: str = ""
    score: int | None = None
    narrative: str = ""
    tags: tuple[str, ...] = ()


def _id(family: str, expected: str, index: int, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"{family}-{expected.lower()}-{index:05d}-{digest}"


def _opening_excerpt(body: str, limit: int = 700) -> str:
    prose = re.sub(r"^#{1,6}\s+.*$", "", body or "", flags=re.MULTILINE)
    return re.sub(r"\s+", " ", prose).strip()[:limit]


def _fact_cases() -> Iterable[AdversarialCase]:
    subjects = ("推論速度", "処理時間", "メモリ使用量", "料金", "精度")
    values = ("20%", "30%", "40%", "2倍", "3倍")
    cohorts = ("A100環境", "H100環境", "検証セットA", "一部ユーザー", "ベータ参加者")
    idx = 0
    for subject in subjects:
        for value in values:
            for cohort in cohorts:
                evidence = f"公式資料では、{cohort}において{subject}が最大{value}改善した。"
                variants = (
                    (OK, f"{cohort}では、{subject}が最大{value}改善した。", ("scope_preserved", "max_preserved")),
                    (BORDERLINE, f"条件によっては、{subject}が最大{value}改善する。", ("scope_softened", "max_preserved")),
                    (FAIL, f"{subject}が{value}改善した。", ("scope_dropped", "max_dropped")),
                    (FAIL, f"すべての環境で{subject}が{value}改善した。", ("universalized", "scope_dropped")),
                    (FAIL, f"平均で{subject}が{value}改善した。", ("max_to_average",)),
                )
                for expected, text, tags in variants:
                    idx += 1
                    yield AdversarialCase(_id("fact", expected, idx, text, evidence), "fact", expected, text, evidence, tags=tags)

    lifecycle = (
        ("プレビュー提供を開始", "正式提供を開始", "preview_to_ga"),
        ("一部プランで無料", "無料で利用できる", "conditional_free_to_free"),
        ("旧モデルAのみ終了", "旧モデルをすべて終了", "partial_to_total_retirement"),
        ("最大100件", "常に100件", "maximum_to_guarantee"),
    )
    for source, bad, tag in lifecycle:
        for noun in ("新API", "推論機能", "エージェント機能", "モデルX", "SDK"):
            evidence = f"公式更新: {noun}は{source}。"
            for expected, phrase in ((OK, source), (FAIL, bad)):
                idx += 1
                text = f"{noun}は{phrase}。"
                yield AdversarialCase(_id("fact", expected, idx, text, evidence), "fact", expected, text, evidence, tags=(tag,))


def _reader_article(*, heading: str, opening: str, body: str, close: str) -> str:
    return f"# テスト記事\n\n{opening}\n\n## {heading}\n\n{body}\n\n## 判断するときに見るもの\n\n{close}"


def _reader_cases() -> Iterable[AdversarialCase]:
    topics = ("AIエージェント", "新しい推論モデル", "コード生成", "検索API", "音声モデル")
    jargon_sets = (
        "orchestration runtime context window inference throughput latency",
        "agentic workflow tool calling sandbox checkpoint telemetry",
        "vector embedding reranking retrieval pipeline benchmark",
    )
    natural_openings = (
        "仕事で毎日使う道具が、ある日急に賢くなったら何が変わるでしょうか。今回はそこから考えます。",
        "スマホの地図が道順だけでなく次の行動まで手伝う。そんな変化に近い話です。",
        "難しそうな名前ですが、使う側から見ると『待ち時間と手間が減るか』が中心です。",
    )
    idx = 0
    for topic in topics:
        for jargon in jargon_sets:
            for opening in natural_openings:
                controls = (
                    (OK, topic, opening, f"{topic}を簡単に言えば、複数の作業を順番に扱うための仕組みです。たとえば会議の準備を一つずつ片付ける感覚に近いです。", "私なら、まず小さな作業で試し、時間が本当に減るかを比べます。", ("plain_bridge",)),
                    (BORDERLINE, "何が変わるのか", opening, f"{topic}では {jargon} が重要です。ただし、導入判断では実際の待ち時間も確認します。", "小さく試して比較します。", ("jargon_some_bridge",)),
                    (FAIL, "なぜ重要なのか", f"{topic}が発表されました。", f"{jargon}. {jargon}. {jargon}. これらの技術要素を理解する必要があります。", "今後の動向を見ていきます。", ("jargon_dense", "announcement_only", "generic_heading")),
                )
                for expected, heading, op, body, close, tags in controls:
                    idx += 1
                    text = _reader_article(heading=heading, opening=op, body=body, close=close)
                    yield AdversarialCase(_id("reader_value", expected, idx, text), "reader_value", expected, text, tags=tags)

    # Rhythm mutations: visually plausible but increasingly mechanical.
    for n in range(1, 41):
        normal = "。".join(["実際の仕事では条件が違います", "小さく試せば差を比べられます", "結果を見て次を決めます"]) + "。"
        burst = "速い。便利。重要。" * (1 + n % 4)
        expected = FAIL if n % 3 == 0 else OK
        body = burst if expected == FAIL else normal
        idx += 1
        text = _reader_article(heading="導入前に比べたい3つの条件", opening=natural_openings[n % len(natural_openings)], body=body, close="私なら計測してから広げます。")
        yield AdversarialCase(_id("reader_value", expected, idx, text), "reader_value", expected, text, tags=("rhythm",))


def _human_cases() -> Iterable[AdversarialCase]:
    topics = ("モデル更新", "API変更", "エージェント", "推論速度", "コード生成", "検索機能")
    glue = ("ここで重要なのは", "注目すべきは", "ポイントは", "つまり", "言い換えると")
    idx = 0
    for topic in topics:
        for phrase in glue:
            natural = (
                f"# {topic}をどう見るか\n\n{topic}の変更点を確認します。\n\n## 使う側に何が起きるか\n\n"
                f"仕様そのものより、今の作業が何分短くなるかを測る方が判断しやすいです。{phrase}、数字を自分の環境で確かめることです。\n\n"
                "## 私ならどうするか\n\nまず小さく試し、差が出なければ見送ります。"
            )
            idx += 1
            yield AdversarialCase(_id("human_appeal", OK, idx, natural), "human_appeal", OK, natural, tags=("single_glue_control",))

            mechanical = (
                f"# {topic}\n\n{phrase}、変化です。つまり重要です。\n\n## なぜ重要なのか\n\n"
                "ここで重要なのは価値という点です。注目すべきは効果という点です。ポイントは判断という点です。\n\n"
                "## ポイント\n\nAではありません。Bなのです。Cではありません。Dなのです。\n\n"
                "## まとめ\n\n第一に確認します。第二に評価します。第三に判断します。確かめてみてはいかがでしょうか。"
            )
            idx += 1
            yield AdversarialCase(_id("human_appeal", FAIL, idx, mechanical), "human_appeal", FAIL, mechanical, tags=("formulaic_composite",))

    # Near-boundary repetitions: one or two familiar transitions should not alone fail.
    for repeats in range(1, 7):
        text = "# 実務で見るポイント\n\n" + "\n\n".join(
            [f"## 条件{i+1}\n\nつまり、条件{i+1}は自社データで確認します。" for i in range(repeats)]
        ) + "\n\n## 私ならどうするか\n\n結果が出るまでは限定運用にします。"
        expected = OK if repeats <= 2 else (BORDERLINE if repeats <= 4 else FAIL)
        idx += 1
        yield AdversarialCase(_id("human_appeal", expected, idx, text), "human_appeal", expected, text, tags=(f"glue_repeat_{repeats}",))


def _score_band(score: int) -> str:
    if score >= 90: return "exceptional"
    if score >= 80: return "strong"
    if score >= 70: return "promising"
    if score >= 60: return "watch"
    return "reject"


def _narrative_band(text: str) -> str:
    low = text.casefold()
    if any(x in low for x in ("最優先", "非常に強い", "今すぐ試す", "exceptional")): return "exceptional"
    if any(x in low for x in ("有力", "強い候補", "優先して試す", "strong")): return "strong"
    if any(x in low for x in ("有望", "試す価値", "promising")): return "promising"
    if any(x in low for x in ("監視", "条件付き", "様子を見る", "watch")): return "watch"
    return "reject"


def _score_cases() -> Iterable[AdversarialCase]:
    narratives = {
        "exceptional": "最優先で試す価値がある非常に強い候補です。",
        "strong": "有力です。優先して試す候補にします。",
        "promising": "有望で、限定的に試す価値があります。",
        "watch": "条件付きで監視し、今は様子を見ます。",
        "reject": "現時点では採用せず、候補から外します。",
    }
    scores = tuple(range(55, 101))
    idx = 0
    bands = tuple(narratives)
    for score in scores:
        true_band = _score_band(score)
        for band in bands:
            expected = OK if band == true_band else FAIL
            # Adjacent band at an exact boundary is explicitly borderline.
            if score in {59, 60, 69, 70, 79, 80, 89, 90} and band != true_band:
                ordered = ["reject", "watch", "promising", "strong", "exceptional"]
                if abs(ordered.index(band) - ordered.index(true_band)) == 1:
                    expected = BORDERLINE
            idx += 1
            narrative = narratives[band]
            yield AdversarialCase(_id("score_narrative", expected, idx, str(score), narrative), "score_narrative", expected, "", score=score, narrative=narrative, tags=(true_band, band))


def build_corpus(min_cases: int = 10_000) -> list[AdversarialCase]:
    seeds = list(_fact_cases()) + list(_reader_cases()) + list(_human_cases()) + list(_score_cases())
    if not seeds:
        return []
    cases = list(seeds)
    # Deterministic orthographic/punctuation mutations multiply the semantic controls
    # without asking a model.  Meaning and expected label are intentionally preserved.
    transforms = (
        lambda s: s,
        lambda s: s.replace("。", "。\n"),
        lambda s: s.replace("、", "，"),
        lambda s: re.sub(r"\s+", " ", s),
        lambda s: s.replace("最大", "最大で"),
        lambda s: s.replace("では、", "では"),
        lambda s: s.replace("私なら", "自分なら"),
    )
    round_no = 1
    while len(cases) < min_cases:
        for seed in seeds:
            transform = transforms[(len(cases) + round_no) % len(transforms)]
            text = transform(seed.text)
            evidence = transforms[(len(cases) + round_no + 2) % len(transforms)](seed.evidence)
            mutated = AdversarialCase(
                _id(seed.family, seed.expected, len(cases) + 1, text, evidence, str(round_no)),
                seed.family, seed.expected, text, evidence, seed.score, seed.narrative,
                seed.tags + (f"orthographic_round_{round_no}",),
            )
            cases.append(mutated)
            if len(cases) >= min_cases:
                break
        round_no += 1
    return cases[:min_cases]


def _detect_fact(case: AdversarialCase) -> str:
    text, evidence = case.text, case.evidence
    # Current Production primitive: numeric value presence + nearby condition compatibility.
    normalized_claim = _normalize_numeric_evidence_text(text)
    normalized_evidence = _normalize_numeric_evidence_text(evidence)
    nums = re.findall(r"\d+(?:\.\d+)?", normalized_claim)
    if nums and not all(num in normalized_evidence for num in nums):
        return FAIL
    if not _numeric_condition_compatible(text, evidence):
        return FAIL
    # Run348 deliberately audits qualifier loss that can survive value-only matching.
    qualifier_pairs = (
        (r"最大(?:で)?", r"平均|常に|すべて"),
        (r"一部|ベータ参加者", r"すべて|全(?:員|環境|ユーザー)"),
        (r"プレビュー", r"正式提供|一般提供"),
        (r"一部プランで無料", r"(?:^|[は、])無料(?:で|。)"),
        (r"のみ終了", r"すべて終了|全面終了"),
    )
    for source_pattern, overclaim_pattern in qualifier_pairs:
        if re.search(source_pattern, evidence) and re.search(overclaim_pattern, text):
            return FAIL
    if re.search(r"最大(?:で)?", evidence) and not re.search(r"最大(?:で)?|条件によって", text):
        return BORDERLINE
    return OK


def _detect_reader(case: AdversarialCase) -> str:
    signals = reader_experience_signals(case.text, _opening_excerpt)
    hardish = sum(signals.get(key) == "REVIEW" for key in (
        "jargon_translation", "non_engineer_core_clarity", "opening_non_engineer_access"
    ))
    soft_bad = sum(bool(signals.get(key)) for key in ("announcement_only", "analogy_overuse", "tone_mismatch", "conversational_overuse"))
    if hardish >= 2 or (hardish >= 1 and soft_bad >= 1):
        return FAIL
    if hardish or soft_bad:
        return BORDERLINE
    return OK


def _detect_human(case: AdversarialCase) -> str:
    signals = ai_style_composite_signals(case.text, DISPLAY_VARIANTS)
    if signals["high"]:
        return FAIL
    if signals["score"] >= 3:
        return BORDERLINE
    return OK


def _detect_score(case: AdversarialCase) -> str:
    assert case.score is not None
    expected_band = _score_band(case.score)
    observed_band = _narrative_band(case.narrative)
    if expected_band == observed_band:
        return OK
    ordered = ["reject", "watch", "promising", "strong", "exceptional"]
    if abs(ordered.index(expected_band) - ordered.index(observed_band)) == 1 and case.score in {59, 60, 69, 70, 79, 80, 89, 90}:
        return BORDERLINE
    return FAIL


def detect(case: AdversarialCase) -> str:
    return {"fact": _detect_fact, "reader_value": _detect_reader,
            "human_appeal": _detect_human, "score_narrative": _detect_score}[case.family](case)


def evaluate(cases: Iterable[AdversarialCase]) -> dict:
    by_family: dict[str, Counter] = defaultdict(Counter)
    samples: dict[str, list[dict]] = defaultdict(list)
    total = Counter()
    for case in cases:
        observed = detect(case)
        key = f"{case.expected}->{observed}"
        by_family[case.family][key] += 1
        total[key] += 1
        if observed != case.expected and len(samples[case.family]) < 12:
            samples[case.family].append({"case_id": case.case_id, "expected": case.expected,
                                         "observed": observed, "tags": list(case.tags),
                                         "text": case.text[:260], "evidence": case.evidence[:220]})

    families = {}
    for family in FAMILIES:
        matrix = by_family[family]
        known_good = sum(v for k, v in matrix.items() if k.startswith("OK->"))
        false_positive = sum(v for k, v in matrix.items() if k in {"OK->FAIL", "OK->BORDERLINE"})
        known_bad = sum(v for k, v in matrix.items() if k.startswith("FAIL->"))
        false_negative = sum(v for k, v in matrix.items() if k in {"FAIL->OK", "FAIL->BORDERLINE"})
        families[family] = {
            "matrix": dict(sorted(matrix.items())),
            "known_good": known_good,
            "known_bad": known_bad,
            "false_positive_rate": round(false_positive / known_good, 4) if known_good else 0.0,
            "false_negative_rate": round(false_negative / known_bad, 4) if known_bad else 0.0,
            "mismatch_samples": samples[family],
        }
    return {"run": "Run348 Zero-API Adversarial Editorial Lab", "total_cases": sum(total.values()),
            "matrix": dict(sorted(total.items())), "families": families,
            "safety_contract": {"gemini_calls": 0, "notion_reads": 0, "notion_writes": 0,
                                "network_calls": 0, "pipeline_imported": False}}


def corpus_digest(cases: Iterable[AdversarialCase]) -> str:
    payload = json.dumps([asdict(c) for c in cases], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=10_000)
    parser.add_argument("--report", default="run348-adversarial-report.json")
    args = parser.parse_args()
    cases = build_corpus(max(1_000, args.cases))
    report = evaluate(cases)
    report["corpus_sha256"] = corpus_digest(cases)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RUN348_ZERO_API_ADVERSARIAL_LAB cases={report['total_cases']} sha256={report['corpus_sha256'][:16]}")
    for family, row in report["families"].items():
        print(f"RUN348_FAMILY family={family} fp={row['false_positive_rate']:.4f} fn={row['false_negative_rate']:.4f} matrix={row['matrix']}")
    print("RUN348_SAFETY gemini=0 notion=0 network=0 pipeline_imported=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
