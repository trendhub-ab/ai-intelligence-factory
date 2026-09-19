# Canonical Article Contract V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify AIIF Writer, Reader, Retry, and gate ownership around one Canonical Article Contract without lowering safety thresholds, adding provider calls, or increasing retry budgets.

**Architecture:** Add one provider-free `canonical_article_contract.py` as the single source of article-quality prompt policy. Existing Run226/228/208/248 modules remain compatibility/integration layers, but they delegate shared Writer/Reader rules to the canonical module instead of appending independent long-form contracts. Gate implementations stay fail-closed; V1 proves ownership with existing `gate` + `reason_code` data rather than adding a new persistence schema.

**Tech Stack:** Python 3.11, pytest/unittest, existing AIIF runtime-layer wrappers, zero-API deterministic tests.

**Spec:** `docs/superpowers/specs/2026-09-19-canonical-article-contract-v1-design.md`

## Global Constraints

- Fact / Evidence integrity has higher priority than Reader comprehension, article-specific interest, or surface polish.
- Gate thresholds must not be lowered.
- Fact / Evidence fail-closed behavior must not be weakened.
- No new Provider is added.
- Gemini call count must not increase.
- No new Blueprint-generation AI call is added.
- Existing bounded retry ownership and request budgets remain authoritative.
- Scheduled Daily remains paused during implementation.
- No note publication is automated.
- No fixed article template is introduced.
- Mechanical fixed-count limits such as “three technical terms maximum” must not return.
- A Production quality-success claim requires a later bounded live validation; deterministic tests alone do not prove real-article quality improvement.

## Review Focus

1. **Isolated layer installation** — Run228, Run208, or Run248 installed without Run226 must still produce exactly one Canonical Writer Contract, not silently lose it. Covered by Task 2.
2. **Mixed Fact/Publication + Reader failures** — a mixed failure must never receive Reader-only repair instructions or a second Reader owner. Covered by Task 3.
3. **Late final-surface defects** — summary/title assembly defects must remain blocked, while body-wide Reader weakness must not be duplicated by Run249. Covered by Task 4.
4. **Legacy prompt contamination** — old fixed-count quotas embedded in a base prompt must be removed before the canonical contract is appended. Covered by Task 1 and Task 2.
5. **Publication provenance** — changing the canonical contract must invalidate old Ready provenance through the existing publication-policy fingerprint. Covered by Task 5.

## File Structure

- Create: `canonical_article_contract.py`
  - Provider-free single source for Canonical Writer Contract, Reader Repair Contract, last-mile Reader Check, and legacy prompt deconfliction.
- Create: `tests/test_canonical_article_contract.py`
  - Unit tests for canonical text, idempotent assembly, no provider dependencies, and legacy quota removal.
- Create: `tests/test_canonical_writer_prompt_assembly.py`
  - Cross-layer prompt assembly tests for Run226 → Run228 → Reader bridge → Run208 → Run248-compatible behavior.
- Create: `tests/fixtures/canonical_article_contract/run74_reason_cases.json`
  - Deterministic regression cases distilled from the 2026-09-19 Daily outcomes.
- Modify: `run226_reader_delight_planning.py`
  - Keep Run226 as the compatibility/editorial-planning integration point; delegate policy text/deconfliction to the canonical module.
- Modify: `run228_reader_rhythm_planning.py`
  - Replace the long independent rhythm contract with a short compatibility marker plus canonical last-mile check.
- Modify: `run208_reader_value_repair.py`
  - Stop appending a second fresh-Writer article philosophy; use canonical Writer/Reader Repair contracts while preserving bounded retry ownership.
- Modify: `run248_first_real_publish_quality_calibration.py`
  - Ensure the canonical final Reader check is present exactly once; retain existing eyecatch, manuscript, Japanese-surface, and Reader gate behavior.
- Modify: `tests/test_run226_reader_delight_planning.py`
- Modify: `tests/test_run228_reader_rhythm_planning.py`
- Modify: `tests/test_run359_reader_repair_execution.py`
- Modify: `tests/test_run360_retry_owner_orthogonality.py`
- Modify: `tests/test_editorial_blueprint_retry_consistency.py`
- Modify: `tests/test_run248_first_real_publish_quality_calibration.py`
- Modify: `tests/test_run249_final_publication_surface_gate.py`
- Modify: `publication_contract.py`
  - Add `canonical_article_contract.py` to publication provenance.
- Modify: `tests/test_run194_publication_contract.py` or `tests/test_run226_reader_delight_planning.py`
  - Prove the canonical contract participates in the publication fingerprint.

---

### Task 1: Create the canonical provider-free article contract

**Files:**
- Create: `canonical_article_contract.py`
- Create: `tests/test_canonical_article_contract.py`

**Interfaces:**
- Consumes: plain prompt strings only; no pipeline object, network, environment, Provider SDK, or persistence.
- Produces:
  - `CANONICAL_ARTICLE_CONTRACT_MARKER: str`
  - `CANONICAL_FINAL_READER_CHECK_MARKER: str`
  - `canonical_writer_contract() -> str`
  - `canonical_reader_repair_contract() -> str`
  - `canonical_final_reader_check() -> str`
  - `deconflict_legacy_writer_rules(prompt: str) -> str`
  - `ensure_writer_contract(prompt: str) -> str`
  - `ensure_final_reader_check(prompt: str) -> str`

- [ ] **Step 1: Write failing canonical-contract tests**

Create `tests/test_canonical_article_contract.py` with:

```python
import inspect

import canonical_article_contract as cac


LEGACY_QUOTAS = (
    "原則2〜3個",
    "4個目",
    "最大3項目",
    "2段落続いたら",
    "3つ以上連打",
)


def test_writer_contract_contains_canonical_dimensions_and_priority():
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
    text = cac.canonical_writer_contract()
    assert "Evidence、重要数値、条件、反証、対象範囲を落とさない" in text
    assert "架空の経験・感情・因果・会話・多数派認識を作らない" in text
    assert "専門語の固定個数制限は設けない" in text


def test_deconflict_removes_legacy_numeric_quotas_before_contract():
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
    once = cac.ensure_final_reader_check(cac.ensure_writer_contract("BASE"))
    twice = cac.ensure_final_reader_check(cac.ensure_writer_contract(once))
    assert once == twice
    assert once.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
    assert once.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER) == 1


def test_reader_repair_keeps_fact_fixed_and_allows_reordering():
    text = cac.canonical_reader_repair_contract()
    assert "Reader Repair｜Factを固定した読者導線修正" in text
    assert "Decision/Score/Action" in text
    assert "段落・見出しを再編" in text
    assert "新しい数値、製品名、API名、比較対象、使用経験、感情、因果、保証表現を追加しない" in text
    assert "通らなければReadyにしない" in text


def test_canonical_module_has_no_provider_or_network_dependency():
    src = inspect.getsource(cac)
    for forbidden in (
        "_generate_via_chat(",
        "genai.Client(",
        "requests.",
        "httpx.",
        "NOTION_",
    ):
        assert forbidden not in src
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
pytest -q tests/test_canonical_article_contract.py
```

Expected: FAIL during import because `canonical_article_contract.py` does not yet exist.

- [ ] **Step 3: Implement the minimal canonical module**

Create `canonical_article_contract.py` with this shape and exact public API:

```python
"""Provider-free canonical article-quality policy for AI Intelligence Factory."""

CANONICAL_ARTICLE_CONTRACT_MARKER = "AIIF_CANONICAL_ARTICLE_CONTRACT_V1"
CANONICAL_FINAL_READER_CHECK_MARKER = "AIIF_CANONICAL_FINAL_READER_CHECK_V1"

_LEGACY_WRITER_REPLACEMENTS = (
    (
        "記事全体の温度を1〜2個の口語句で済ませず、硬い説明が2段落続いたら次の段落では、追加説明を足さず、既存文を「読者の判断／具体場面／平易な一言」のどれかへ置き換えて人間の言葉へ戻す。",
        "記事全体の温度を固定個数の口語句で作らない。Reader QuestionやReader Decisionとの関係が見えない箇所だけ、追加説明ではなく既存文の削除・順序変更・平易化で直す。",
    ),
    (
        "この無料ARTICLEで読者が本当に覚える専門概念を内部で原則2〜3個に絞る。4個目がないとDecisionを誤解する場合だけ4個まで許す。",
        "専門概念はCentral Conclusion / Capability Boundary / Reader Decisionの理解に必要なものだけを残し、固定個数で制限しない。",
    ),
    (
        "ARTICLE本文で説明する中核概念は原則2〜3個、実装識別子・規格名・コマンド名は意思決定に必要なものだけに限定し、列挙で専門性を演出しない。",
        "中核概念は固定個数で制限せず、Reader Decisionに必要なものだけを残す。実装識別子・規格名・コマンド名は判断に必要な場合だけ出す。",
    ),
    (
        "手順・機能・注意点の列挙はそれぞれ最大3項目まで。",
        "手順・機能・注意点は必要最小限にし、重要な制約や判断材料を個数上限で落とさない。",
    ),
    (
        "短文を3つ以上連打して広告コピーのように煽らない。",
        "短文の連打で広告コピーのように煽らない。",
    ),
)


def deconflict_legacy_writer_rules(prompt: str) -> str:
    text = str(prompt or "")
    for old, new in _LEGACY_WRITER_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def canonical_writer_contract() -> str:
    return f"""
[{CANONICAL_ARTICLE_CONTRACT_MARKER}]
ARTICLEの品質優先順位は Fact / Evidence integrity → Decision fidelity → Reader comprehension → article-specific discovery / interest → surface polish とする。
下位品質のために上位品質を壊さない。Evidence、重要数値、条件、反証、対象範囲を落とさない。架空の経験・感情・因果・会話・多数派認識を作らない。

本文を書く前に、取得済みSOURCE BOUNDARY / Evidence / 既存Decisionだけで次を内部決定する。固定見出しや固定順序にはしない。
- Reader Question — 読者のどの疑問・迷い・選択を解消するか。
- Why Now — なぜ今読む価値があるか。取得済みEvidenceだけで示す。
- Central Conclusion — 記事全体の中心判断。既存Decisionと一致させる。
- Discovery — 発表要約ではなく「そういうことだったのか」と残る記事固有の核心。
- Capability Boundary — できる／できない／まだ分からないをEvidenceどおりに分ける。
- Reader Decision — 読者が次に試す／比較する／待つ／見送る等を自然な日本語へ翻訳する。
- Evidence Integrity — 結論と判断を支える一次情報、重要数値、条件、対象範囲、反証を保持する。

Writerの中心原則は「記事を全部説明するな。読者が正しく判断するために必要な情報を選び、最も自然な順番で渡す」。
Reader Question、Central Conclusion、Capability Boundary、Reader Decision、重要Evidenceのどれにも不要な周辺仕様、内部実装名、コマンド名、規格番号、重複説明、名称紹介は削除または意味カテゴリへ圧縮する。

専門語の固定個数制限は設けない。必要な専門語は残すが、初出では可能な限り普通の言葉で役割を先に示し、その後で正式名称を出す。専門語を別の未説明専門語で説明しない。
Human Appealは会話句の数ではなく、記事固有の意外性、読者との関係、比較、因果、判断の分かれ目、具体的な意味から作る。Security / Risk等は落ち着いた文章でもよい。
です・ます調を土台にし、教師の講義や監査報告書ではなく、AI・ITに詳しい人が面白いところを順番に見せる距離感にする。
Reader-first summaryの「何が出た？／なぜ重要？／結論は？」を本文テンプレートにしない。
""".strip()


def canonical_reader_repair_contract() -> str:
    return """
【Reader Repair｜Factを固定した読者導線修正】
この修正では新しい調査・新しい事実追加をしない。前稿のFact/Evidenceを正本とする。
Evidence URL、一次情報の意味、Decision/Score/Action、判断を支える数値・単位・固有名詞・条件を変えない。
新しい数値、製品名、API名、比較対象、使用経験、感情、因果、保証表現を追加しない。
修正優先順位は Reader Decision理解 → 重要制約 → Evidence → 判断に必要な中核メカニズム → 実装名・略語。
保護するのは根拠と判断の意味であり、前稿の文面・段落順・見出しではない。必要なら段落・見出しを再編し、Decisionを前倒ししてよい。
不要な専門名・略語・内部部品名は削除または意味カテゴリへ圧縮する。必要な専門語は個数で制限しない。
修正後もFact / Evidence / Publication / Readerを再判定し、通らなければReadyにしない。
""".strip()


def canonical_final_reader_check() -> str:
    return f"""
[{CANONICAL_FINAL_READER_CHECK_MARKER}]
出力直前に、新情報を足さず次だけ確認する。
1. 非エンジニアにも何が起きたか、なぜ自分に関係するか、現時点の判断が分かる。
2. 判断に不要な実装細部、重複、報告書調の前置きを削る。
3. 必要な専門語は役割が普通の日本語で分かり、別の未説明専門語で説明していない。
4. Evidence、重要数値、条件、反証、Decisionは削らない。
5. 「要するに何の話か」と「自分なら次に何をするか」が説明できる。
Fact/Evidence安全境界がReader要件と衝突する場合はFact/Evidenceを優先する。
""".strip()


def ensure_writer_contract(prompt: str) -> str:
    base = deconflict_legacy_writer_rules(prompt).rstrip()
    if CANONICAL_ARTICLE_CONTRACT_MARKER in base:
        return base + ("\n" if base else "")
    return base + "\n\n" + canonical_writer_contract() + "\n"


def ensure_final_reader_check(prompt: str) -> str:
    base = ensure_writer_contract(prompt).rstrip()
    if CANONICAL_FINAL_READER_CHECK_MARKER in base:
        return base + "\n"
    return base + "\n\n" + canonical_final_reader_check() + "\n"
```

- [ ] **Step 4: Run the unit tests and verify GREEN**

Run:

```bash
pytest -q tests/test_canonical_article_contract.py
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add canonical_article_contract.py tests/test_canonical_article_contract.py
git commit -m "feat: add canonical article contract"
```

---

### Task 2: Make Fresh Writer prompt assembly use one canonical source

**Files:**
- Modify: `run226_reader_delight_planning.py`
- Modify: `run228_reader_rhythm_planning.py`
- Modify: `run248_first_real_publish_quality_calibration.py:310-405`
- Modify: `tests/test_run226_reader_delight_planning.py`
- Modify: `tests/test_run228_reader_rhythm_planning.py`
- Modify: `tests/test_editorial_blueprint_retry_consistency.py`
- Create: `tests/test_canonical_writer_prompt_assembly.py`

**Interfaces:**
- Consumes from Task 1: `canonical_writer_contract`, `deconflict_legacy_writer_rules`, `ensure_writer_contract`, `ensure_final_reader_check`.
- Produces: every Fresh Writer prompt has one canonical contract and one final Reader check, regardless of compatible layer installation order.

- [ ] **Step 1: Write failing cross-layer assembly tests**

Create `tests/test_canonical_writer_prompt_assembly.py`:

```python
from types import SimpleNamespace

import canonical_article_contract as cac
import reader_value_review_bridge as bridge
import run208_reader_value_repair as repair
import run226_reader_delight_planning as run226
import run228_reader_rhythm_planning as run228


def _pipeline():
    return SimpleNamespace(
        build_decision_prompt=lambda *a, **k: "SOURCE BOUNDARY\nEvidence-to-Decision",
        build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", ["ARTICLE"]),
        validate_human_appeal_gate=lambda parsed, peers=None: ("ACCEPTABLE", []),
        should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (False, "base_denied"),
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )


def test_production_editorial_stack_has_one_canonical_contract():
    p = _pipeline()
    for layer in (run226, run228, bridge, repair):
        layer.install(p)
    prompt = p.build_decision_prompt()
    assert prompt.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
    assert prompt.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER) == 1
    assert "SOURCE BOUNDARY" in prompt
    assert "Evidence-to-Decision" in prompt


def test_run228_is_safe_when_installed_without_run226():
    p = _pipeline()
    run228.install(p)
    prompt = p.build_decision_prompt()
    assert prompt.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
    assert prompt.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER) == 1


def test_run208_is_safe_when_installed_without_run226():
    p = _pipeline()
    repair.install(p)
    prompt = p.build_decision_prompt()
    assert prompt.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1


def test_long_legacy_reader_contract_is_not_repeated_in_fresh_prompt():
    p = _pipeline()
    for layer in (run226, run228, bridge, repair):
        layer.install(p)
    prompt = p.build_decision_prompt()
    assert prompt.count("記事を全部説明するな") == 1
    assert prompt.count("Reader Repair｜Factを固定した読者導線修正") == 0
    assert "原則2〜3個" not in prompt
    assert "最大3項目" not in prompt
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
pytest -q   tests/test_canonical_writer_prompt_assembly.py   tests/test_run226_reader_delight_planning.py   tests/test_run228_reader_rhythm_planning.py   tests/test_editorial_blueprint_retry_consistency.py   tests/test_run248_first_real_publish_quality_calibration.py
```

Expected: new assembly assertions fail because existing Run226/228/208/248 still append independent contracts.

- [ ] **Step 3: Convert Run226 into the canonical compatibility owner**

Modify `run226_reader_delight_planning.py` to import the canonical module and keep its public compatibility functions:

```python
from canonical_article_contract import (
    CANONICAL_ARTICLE_CONTRACT_MARKER,
    canonical_writer_contract,
    deconflict_legacy_writer_rules,
    ensure_writer_contract,
)

EDITORIAL_BLUEPRINT_MARKER = CANONICAL_ARTICLE_CONTRACT_MARKER


def editorial_planning_contract() -> str:
    return canonical_writer_contract()


def deconflict_writer_prompt(prompt: str) -> str:
    return deconflict_legacy_writer_rules(prompt)


def augment_prompt(prompt: str) -> str:
    base = ensure_writer_contract(prompt).rstrip()
    if QUALITY_MEMORY_MARKER not in base:
        base += "\n\n" + quality_memory_contract()
    return base.rstrip() + "\n"
```

Keep `RUN226_MARKER` as a Python/runtime compatibility attribute if existing code/tests need it, but do not require a second long Run226 prompt body.

- [ ] **Step 4: Collapse Run228 to a short compatibility marker + canonical final check**

Replace the long independent rhythm policy with:

```python
from canonical_article_contract import ensure_final_reader_check

def reader_rhythm_contract() -> str:
    return f"""
[{RUN228_MARKER} — compatibility layer]
Reader Rhythm is governed by AIIF_CANONICAL_ARTICLE_CONTRACT_V1.
This layer adds no independent article philosophy or fixed-count style quota.
""".strip()


def augment_prompt(prompt: str) -> str:
    base = str(prompt or "").rstrip()
    if RUN228_MARKER not in base:
        base += "\n\n" + reader_rhythm_contract()
    return ensure_final_reader_check(base)
```

Update Run228 tests to assert preservation of Evidence/Decision through the canonical marker rather than duplicating the old long paragraph contract.

- [ ] **Step 5: Make Run248 ensure, not append, the final Reader check**

In `run248_first_real_publish_quality_calibration.py`, import `ensure_final_reader_check` and change its Writer wrapper to:

```python
def build_decision_prompt(*args: Any, **kwargs: Any) -> str:
    return ensure_final_reader_check(original_prompt(*args, **kwargs))
```

Do not change its eyecatch, manuscript repair, Japanese-surface, or Reader gate wrappers.

- [ ] **Step 6: Update existing Run226/228 consistency assertions**

Adjust tests so they prove:

```python
assert prompt.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
assert prompt.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER) == 1
assert "必要な専門概念・制約・判断材料を個数合わせのために削らない" not in prompt
assert "専門語の固定個数制限は設けない" in prompt
```

The first assertion proves single-source assembly. The last two prove the old sentence was not retained merely to satisfy historical tests; the canonical equivalent is authoritative.

- [ ] **Step 7: Run focused Writer tests**

Run:

```bash
pytest -q   tests/test_canonical_article_contract.py   tests/test_canonical_writer_prompt_assembly.py   tests/test_run226_reader_delight_planning.py   tests/test_run228_reader_rhythm_planning.py   tests/test_editorial_blueprint_retry_consistency.py   tests/test_run248_first_real_publish_quality_calibration.py
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add   run226_reader_delight_planning.py   run228_reader_rhythm_planning.py   run248_first_real_publish_quality_calibration.py   tests/test_run226_reader_delight_planning.py   tests/test_run228_reader_rhythm_planning.py   tests/test_editorial_blueprint_retry_consistency.py   tests/test_run248_first_real_publish_quality_calibration.py   tests/test_canonical_writer_prompt_assembly.py
git commit -m "refactor: unify fresh article quality prompt"
```

---

### Task 3: Make Reader Repair use the same canonical contract without changing retry ownership

**Files:**
- Modify: `run208_reader_value_repair.py:72-109,245-265`
- Modify: `tests/test_run359_reader_repair_execution.py`
- Modify: `tests/test_run360_retry_owner_orthogonality.py`
- Modify: `tests/test_editorial_blueprint_retry_consistency.py`

**Interfaces:**
- Consumes from Task 1: `canonical_reader_repair_contract() -> str`, `ensure_writer_contract(prompt: str) -> str`.
- Preserves:
  - `should_attempt_dynamic_retry(...)`
  - one base retry owner
  - one Reader-only repair owner
  - Evidence `SUFFICIENT` + `decision_scope_safe=True` requirement
  - Run359 targeted reason directives
  - `Reader Repair｜Factを固定した読者導線修正` marker required by Run284 preservation logic.

- [ ] **Step 1: Add failing tests for canonical Reader Repair and mixed-failure isolation**

Add to `tests/test_run359_reader_repair_execution.py`:

```python
import canonical_article_contract as cac


def test_reader_repair_uses_canonical_contract_once():
    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (
            False, "reader_value_review_no_retry"
        ),
        build_decision_prompt=lambda *a, **k: "BASE",
        build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", ["reader"]),
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    instruction, _ = pipeline.build_dynamic_retry_instruction(
        [_row("non_engineer_access_failure")]
    )
    assert instruction.count("Reader Repair｜Factを固定した読者導線修正") == 1
    assert "段落・見出しを再編" in instruction
    assert "新しい数値、製品名、API名、比較対象" in instruction


def test_mixed_publication_and_reader_failure_never_gets_reader_only_contract():
    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (
            True, "base_quality_retry"
        ),
        build_decision_prompt=lambda *a, **k: "BASE",
        build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", ["ARTICLE"]),
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    rows = [
        _row("non_engineer_access_failure"),
        {"message": "score_narrative_mismatch", "severity": "REVIEW"},
    ]
    instruction, _ = pipeline.build_dynamic_retry_instruction(rows)
    assert "Reader Repair｜Factを固定した読者導線修正" not in instruction
```

- [ ] **Step 2: Run Reader Retry tests and confirm RED**

Run:

```bash
pytest -q   tests/test_run359_reader_repair_execution.py   tests/test_run360_retry_owner_orthogonality.py   tests/test_editorial_blueprint_retry_consistency.py
```

Expected: canonical-delegation assertions fail before implementation.

- [ ] **Step 3: Delegate Run208 policy text to the canonical module**

At the top of `run208_reader_value_repair.py`:

```python
from canonical_article_contract import (
    canonical_reader_repair_contract,
    ensure_writer_contract,
)

READER_REPAIR_CONTRACT = canonical_reader_repair_contract()
```

Keep `READER_PATH_CONTRACT` only as a compatibility constant if imported externally; it must not be appended to fresh prompts.

Change the fresh prompt wrapper to:

```python
def build_decision_prompt_with_reader_path(*args: Any, **kwargs: Any) -> str:
    quality_feedback = str(
        args[4] if len(args) > 4 else kwargs.get("quality_feedback") or ""
    )
    previous_article = str(kwargs.get("previous_article") or "")
    if not quality_feedback.strip() and not previous_article.strip():
        setattr(pipeline_module, _BASE_RETRY_SPENT_ATTR, False)
        setattr(pipeline_module, _READER_REPAIR_SPENT_ATTR, False)
    return ensure_writer_contract(original_prompt(*args, **kwargs))
```

Keep `build_dynamic_retry_instruction_with_reader_repair` behavior:

```python
if reader_only:
    instruction = str(instruction).rstrip() + "\n\n" + READER_REPAIR_CONTRACT
    targeted = _run359_targeted_repair(rows)
    if targeted:
        instruction = instruction.rstrip() + "\n\n" + targeted
```

Do not modify `should_attempt_dynamic_retry_with_reader_repair`.

- [ ] **Step 4: Prove Run284 preservation semantics still recognize Reader Repair**

In `tests/test_run360_retry_owner_orthogonality.py`, add:

```python
import canonical_article_contract as cac


def test_canonical_reader_repair_marker_skips_run352_paragraph_lock():
    feedback = cac.canonical_reader_repair_contract()
    out = run284.retry_feedback_with_preservation(feedback, "before article")
    assert out == feedback
    assert "指摘対象でない見出し、段落順" not in out
```

- [ ] **Step 5: Run Reader Retry tests and verify GREEN**

Run:

```bash
pytest -q   tests/test_canonical_article_contract.py   tests/test_run359_reader_repair_execution.py   tests/test_run360_retry_owner_orthogonality.py   tests/test_editorial_blueprint_retry_consistency.py   tests/test_run278_quality_retry_budget_guard.py   tests/test_run356_pending_retry_stack_parity.py
```

Expected: PASS; retry counts and evidence gating unchanged.

- [ ] **Step 6: Commit Task 3**

```bash
git add   run208_reader_value_repair.py   tests/test_run359_reader_repair_execution.py   tests/test_run360_retry_owner_orthogonality.py   tests/test_editorial_blueprint_retry_consistency.py
git commit -m "refactor: align reader repair with canonical contract"
```

---

### Task 4: Lock gate ownership to the observed Daily failure classes

**Files:**
- Create: `tests/fixtures/canonical_article_contract/run74_reason_cases.json`
- Create: `tests/test_canonical_gate_ownership.py`
- Modify only if a proven test requires it: `gate_reasoning.py`
- Modify: `tests/test_run249_final_publication_surface_gate.py`

**Interfaces:**
- Uses existing `map_gate_reasons`, `reason_code`, `gate_reason_disposition`, and Run208 `is_reader_only_repair`.
- V1 does **not** add a new persistence field. Existing `gate` is the owner; `reason_code` identifies the defect class. Add schema only if an existing consumer demonstrably cannot distinguish ownership.

- [ ] **Step 1: Add deterministic Daily reason fixtures**

Create `tests/fixtures/canonical_article_contract/run74_reason_cases.json`:

```json
[
  {
    "name": "ZCode",
    "rows": [
      {
        "gate": "publication",
        "message": "score_narrative_mismatch"
      },
      {
        "gate": "human_appeal",
        "message": "reader_value_review:dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)"
      },
      {
        "gate": "human_appeal",
        "message": "reader_value_review:non_engineer_access_failure (Accessibility/Opening/Information Budget/Jargon Translation/Non-Engineer Core Clarity)"
      }
    ],
    "reader_only": false
  },
  {
    "name": "Claude Code AGENTS.md",
    "rows": [
      {
        "gate": "human_appeal",
        "message": "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)"
      },
      {
        "gate": "human_appeal",
        "message": "reader_value_review:final_surface_summary_jargon_cluster (何が出た？/結論は？)"
      }
    ],
    "reader_only": true
  },
  {
    "name": "Inference Engine Fingerprinting",
    "rows": [
      {
        "gate": "fact",
        "message": "conditional scope lost from primary evidence"
      }
    ],
    "reader_only": false
  }
]
```

- [ ] **Step 2: Write ownership tests**

Create `tests/test_canonical_gate_ownership.py`:

```python
import json
from pathlib import Path

import gate_reasoning as gr
import run208_reader_value_repair as r208


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "canonical_article_contract"
    / "run74_reason_cases.json"
)


def _mapped(row):
    return gr.map_gate_reasons(row["gate"], [row["message"]])[0]


def test_observed_daily_reason_classes_keep_one_explicit_owner():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in cases:
        mapped = [_mapped(row) for row in case["rows"]]
        for source, result in zip(case["rows"], mapped):
            assert result["gate"] == source["gate"]
        hard = gr.GATE_SEVERITY_HARD
        assert r208.is_reader_only_repair(mapped, hard) is case["reader_only"]


def test_reader_reason_keeps_reader_code_without_becoming_publication_reason():
    row = _mapped(
        {
            "gate": "human_appeal",
            "message": "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)",
        }
    )
    assert row["reason_code"] == gr.REASON_CODE_READER_NON_ENGINEER_ACCESS
    assert row["gate"] == "human_appeal"
    assert row["severity"] == gr.GATE_SEVERITY_REVIEW


def test_fact_conditionality_loss_remains_hard_block():
    row = _mapped(
        {
            "gate": "fact",
            "message": "conditional scope lost from primary evidence",
        }
    )
    assert row["reason_code"] == gr.REASON_CODE_FACT_CONDITIONALITY_LOSS
    assert row["gate"] == "fact"
    assert row["severity"] == gr.GATE_SEVERITY_HARD


def test_unknown_publication_reason_remains_fail_closed():
    row = _mapped(
        {"gate": "publication", "message": "new_unknown_publication_defect"}
    )
    assert row["severity"] == gr.GATE_SEVERITY_HARD
```

- [ ] **Step 3: Run ownership tests**

Run:

```bash
pytest -q   tests/test_canonical_gate_ownership.py   tests/test_run249_final_publication_surface_gate.py   tests/test_reader_core_vs_style_policy.py   tests/test_run353_gate_reason_precision.py
```

Expected: PASS if current ownership is already correct. If any test fails, change only the specific misclassification in `gate_reasoning.py`; do not add thresholds or downgrade severity.

- [ ] **Step 4: Add a final-surface ownership regression**

Add to `tests/test_run249_final_publication_surface_gate.py`:

```python
def test_final_surface_owns_only_late_summary_or_title_defects():
    signals = {
        "accessibility": "REVIEW",
        "jargon_translation": "REVIEW",
        "non_engineer_core_clarity": "REVIEW",
        "reader_enjoyment": "REVIEW",
        "narrative_pull": "REVIEW",
        "information_budget": "REVIEW",
        "reader_temperature_rhythm": "REVIEW",
    }
    pipeline = _pipeline(signals=signals)
    r249.install(pipeline)
    state, issues = pipeline.validate_human_appeal_gate(
        {
            "title_text": "AIの説明を因果で見直す。",
            "note_draft": "本文です。",
        },
        [],
    )
    assert state == "ACCEPTABLE"
    assert not any("final_surface_multi_axis" in issue for issue in issues)
    assert not any("final_surface_non_engineer_access" in issue for issue in issues)
```

- [ ] **Step 5: Run ownership suite and verify GREEN**

Run:

```bash
pytest -q   tests/test_canonical_gate_ownership.py   tests/test_run249_final_publication_surface_gate.py   tests/test_reader_core_vs_style_policy.py   tests/test_run353_gate_reason_precision.py   tests/test_run357_quality_interaction_contract.py   tests/test_run358_reader_signal_precision.py
```

Expected: PASS with Fact/Evidence and unknown publication reasons still fail-closed.

- [ ] **Step 6: Commit Task 4**

```bash
git add   gate_reasoning.py   tests/fixtures/canonical_article_contract/run74_reason_cases.json   tests/test_canonical_gate_ownership.py   tests/test_run249_final_publication_surface_gate.py
git commit -m "test: lock canonical gate ownership"
```

If `gate_reasoning.py` was not changed, omit it from `git add`.

---

### Task 5: Put the canonical contract under publication provenance and run full deterministic regression

**Files:**
- Modify: `publication_contract.py`
- Modify: `tests/test_run194_publication_contract.py` or `tests/test_run226_reader_delight_planning.py`
- Verify: `runtime_layers.py` remains unchanged unless a failing test proves otherwise.

**Interfaces:**
- Consumes: `canonical_article_contract.py` from Task 1.
- Produces: any canonical quality-policy change changes `publication_contract.policy_sha256()`, making older Ready content stale under the existing fail-closed provenance contract.

- [ ] **Step 1: Write failing provenance assertion**

Add:

```python
def test_publication_policy_includes_canonical_article_contract():
    assert "canonical_article_contract.py" in publication_contract.PUBLICATION_POLICY_FILES
```

- [ ] **Step 2: Run the provenance test and confirm RED**

Run:

```bash
pytest -q tests/test_run194_publication_contract.py -k canonical_article_contract
```

Expected: FAIL because the new module is not yet in `PUBLICATION_POLICY_FILES`.

- [ ] **Step 3: Add the canonical module to the publication manifest**

In `publication_contract.py`, add `"canonical_article_contract.py"` next to the prompt/reader policy files, before `reader_value_review_bridge.py`.

Do not create a new manual policy version. Existing content hashing is authoritative.

- [ ] **Step 4: Run targeted provenance and runtime-layer tests**

Run:

```bash
pytest -q   tests/test_run194_publication_contract.py   tests/test_run226_reader_delight_planning.py   tests/test_run249_final_publication_surface_gate.py   tests/test_run280_publication_dependency_guard.py
```

Expected: PASS.

- [ ] **Step 5: Run the complete targeted article-quality suite**

Run:

```bash
pytest -q   tests/test_canonical_article_contract.py   tests/test_canonical_writer_prompt_assembly.py   tests/test_canonical_gate_ownership.py   tests/test_editorial_blueprint_retry_consistency.py   tests/test_run226_reader_delight_planning.py   tests/test_run228_reader_rhythm_planning.py   tests/test_run248_first_real_publish_quality_calibration.py   tests/test_run249_final_publication_surface_gate.py   tests/test_run359_reader_repair_execution.py   tests/test_run360_retry_owner_orthogonality.py   tests/test_run405_reader_density_compression.py   tests/test_reader_core_vs_style_policy.py   tests/test_reader_ready_guard.py   tests/test_reader_summary_sentence_integrity.py
```

Expected: PASS.

- [ ] **Step 6: Run full deterministic repository regression**

Run:

```bash
pytest -q
```

Expected: all tests PASS; only already-known warnings are acceptable. Any new warning/failure must be investigated before continuing.

- [ ] **Step 7: Run zero-provider structural checks**

Run the repository’s existing commands/workflows for:

```text
Synthetic Regression Suite
Repository-wide Falsification Guard
Integration Reconciliation CI
Notion Access Policy Guard
```

Expected: all PASS, with no Gemini/Google generation call and no Production write path.

- [ ] **Step 8: Verify the change did not increase Provider-call sites**

Run:

```bash
python - <<'PY'
from pathlib import Path

root = Path(".")
canonical = (root / "canonical_article_contract.py").read_text(encoding="utf-8")
assert "_generate_via_chat(" not in canonical
assert "genai.Client(" not in canonical
print("canonical provider calls: 0")
PY
```

Expected:

```text
canonical provider calls: 0
```

- [ ] **Step 9: Commit Task 5**

```bash
git add publication_contract.py tests/test_run194_publication_contract.py
git commit -m "chore: fingerprint canonical article policy"
```

If the provenance assertion was placed in a different existing test file, add that exact file instead.

---

## Final Branch Verification

Before opening or updating the implementation PR:

- [ ] Verify no production workflow was dispatched:

```bash
git status --short
git log --oneline --decorate -10
```

Expected: clean tree; only planned commits are present.

- [ ] Verify no scheduled Daily change exists:

```bash
git diff main...HEAD -- .github/workflows
```

Expected: empty diff.

- [ ] Verify no provider-budget or routing change exists:

```bash
git diff main...HEAD --   run260_gemini_model_routing.py   gemini_provider_resilience.py   production_pipeline.py
```

Expected: empty diff unless a test-only import formatting change was explicitly required; no budget/model routing values may change.

- [ ] Review the complete branch diff for scope:

```bash
git diff --stat main...HEAD
git diff main...HEAD
```

Expected: canonical contract, prompt compatibility layers, tests, and publication fingerprint only. No Notion schema, note publication, source acquisition, eyecatch design, screening, or Provider routing changes.

- [ ] Do **not** claim Production article-quality success after deterministic verification. The next separate phase is a user-authorized bounded live validation using the existing Production path, where success requires an actual article to achieve Fact PASS, Publication PASS, Reader PASS, Human Appeal ACCEPTABLE or better, Ready, and private-draft E2E without public publication.
