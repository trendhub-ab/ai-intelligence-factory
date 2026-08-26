from pathlib import Path

path = Path('pipeline.py')
text = path.read_text(encoding='utf-8')

old_budget = '''    # Information-budget signal: do not solve accessibility by adding more prose. Several dense
    # jargon paragraphs plus many analogies indicate the article may be explaining everything twice.
    # This is diagnostic only; it never removes Evidence or changes a hard gate.
    article_char_count = len(re.sub(r"\\s+", "", prose))
    information_budget = "GOOD"
    if (
        jargon_dense_paragraphs >= 3
        or (len(analogy_markers) >= 3 and technical_density >= 30.0)
        or article_char_count > 3200
    ):
        information_budget = "REVIEW"
'''
new_budget = '''    # Reader-value budget: length itself is never a defect. Diagnose only the patterns that make
    # an article *feel* long to a non-engineer: repeated dense explanation, duplicated analogy,
    # implementation overload, or long uninterrupted explanatory runs. Evidence/Decision depth may
    # legitimately require a longer article, so character count remains observability only.
    article_char_count = len(re.sub(r"\\s+", "", prose))
    information_budget = "GOOD"
    if (
        jargon_dense_paragraphs >= 3
        or (len(analogy_markers) >= 3 and technical_density >= 30.0)
        or (max_explanatory_run >= 4 and technical_density >= 26.0)
        or (len(unique_implementation_identifiers) >= 10 and jargon_dense_paragraphs >= 2)
    ):
        information_budget = "REVIEW"
'''
if old_budget not in text:
    raise SystemExit('Run136 patch anchor missing: information budget')
text = text.replace(old_budget, new_budget, 1)

old_length_rule = '・記事本文は目安として2,200〜3,000字、3,200字をSoft Ceilingとし、同じ事実を別の見出しで繰り返さない。重要Evidenceや制約のため超えることは許容するが、Decisionに不要な技術詳細の列挙で長文化しない。'
new_length_rule = '・記事本文の文字数を品質目標にしない。同じ事実の言い換え反復、Decisionに不要な実装列挙、長いコード例、説明の二重化は削る。一方で、Evidence・数値条件・制約・比較・反証・Decisionを文字数のために削らない。長くても読者が迷わず読み進められる情報順序と温度変化を優先する。'
if old_length_rule not in text:
    raise SystemExit('Run136 patch anchor missing: article length rule')
text = text.replace(old_length_rule, new_length_rule, 1)

old_retry = '''    # Retry itself must not re-introduce internal management vocabulary into the public article.
    instructions.append("ARTICLE本文には内部管理コード NOW / TRY / WATCH / WAIT / AVOID を絶対に出力せず、読者向けの自然な日本語判断文へ言い換えてください。")
    if any((row.get("reason_code") or "") in {REASON_CODE_APPEAL_AI_STYLE_COMPOSITE, REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT} for row in reason_rows):
        instructions.append("AI臭・量産テンプレ感の修正では見出し名・段落分割・文章リズムを変更してよい。必要なら情報提示順も変更してよい。ただし一次情報、数値、固有名詞、Decisionの意味、制約条件は変更・追加しないでください。")
    else:
        instructions.append("修正対象外の一次情報・数値・固有名詞は不用意に書き換えないでください。ただしARTICLE本文が2,300字を超えている場合は、局所修正だけで長文を温存せず、Evidence・数値・制約・比較・反証・Decisionを保持したまま、実装列挙・二重説明・一般論・完全なコードブロック・実装チュートリアルを削除または統合して1,800〜2,300字へ再編集してください。Retryで本文を長くすることは禁止です。根拠にない保証表現、業界標準との断定、時間・金額・性能などの数値を新たに補わないでください。")
'''
new_retry = '''    # Retry itself must not re-introduce internal management vocabulary into the public article.
    instructions.append("ARTICLE本文には内部管理コード NOW / TRY / WATCH / WAIT / AVOID を絶対に出力せず、読者向けの自然な日本語判断文へ言い換えてください。")
    hard_retry = any(row.get("severity") == GATE_SEVERITY_HARD for row in normalize_gate_reason_rows(reason_rows))
    if hard_retry:
        # HARD retry has one job: repair factual/publication safety. Combining it with whole-article
        # compression caused new overclaims in real regression, so explicitly forbid broad rewriting.
        instructions.append("HARD修正では記事全体の短文化・全面再構成を同時に行わず、指摘された事実・条件・導入・結論など必要箇所だけを最小限修正してください。修正対象外のEvidence・数値・固有名詞・制約・比較・反証・Decisionの意味と文章構造はできるだけ保持してください。")
        instructions.append("Retry中に『安全性が担保される』『保証される』『完全に防げる』『必ず改善する』等、一次情報より強い保証・一般化を新たに作らないでください。根拠にない時間・金額・性能・業界標準も追加しないでください。")
    elif any((row.get("reason_code") or "") in {REASON_CODE_APPEAL_AI_STYLE_COMPOSITE, REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT} for row in reason_rows):
        instructions.append("AI臭・量産テンプレ感の修正では見出し名・段落分割・文章リズムを変更してよい。必要なら情報提示順も変更してよい。ただし一次情報、数値、固有名詞、Decisionの意味、制約条件は変更・追加しないでください。文字数合わせではなく、重複説明を減らして長く感じさせないことを優先してください。")
    else:
        instructions.append("修正対象外の一次情報・数値・固有名詞は不用意に書き換えないでください。文字数を目標にせず、同じ事実の言い換え、不要な実装列挙、一般論、完全なコードブロック、実装チュートリアルなど読者の判断に不要な重複だけを削除・統合してください。Evidence・数値・制約・比較・反証・Decisionは短文化のために削らず、非エンジニアでも流れを追える説明順序を優先してください。")
'''
if old_retry not in text:
    raise SystemExit('Run136 patch anchor missing: retry block')
text = text.replace(old_retry, new_retry, 1)
path.write_text(text, encoding='utf-8')

Path('tests/test_run136_reader_value_priority.py').write_text('''import inspect\nimport unittest\nimport pipeline\n\n\nclass Run136ReaderValuePriorityTests(unittest.TestCase):\n    def test_article_prompt_has_no_3200_soft_ceiling(self):\n        src = inspect.getsource(pipeline.build_decision_prompt)\n        self.assertNotIn("3,200字", src)\n        self.assertNotIn("2,200〜3,000字", src)\n        self.assertIn("文字数を品質目標にしない", src)\n\n    def test_information_budget_is_not_character_count_gate(self):\n        src = inspect.getsource(pipeline._reader_experience_signals)\n        self.assertNotIn("article_char_count > 3200", src)\n        self.assertIn("max_explanatory_run >= 4", src)\n        self.assertIn("unique_implementation_identifiers", src)\n\n    def test_hard_retry_prioritizes_local_fact_repair(self):\n        rows = [{"reason_code": pipeline.REASON_CODE_PUB_INTRO_OVERCLAIM, "message": "intro_overclaim", "gate": "publication", "severity": pipeline.GATE_SEVERITY_HARD}]\n        instruction, _ = pipeline.build_dynamic_retry_instruction(rows)\n        self.assertIn("記事全体の短文化・全面再構成を同時に行わず", instruction)\n        self.assertNotIn("1,800〜2,300字", instruction)\n        self.assertNotIn("2,300字を超えて", instruction)\n\n    def test_hard_retry_forbids_new_guarantees(self):\n        rows = [{"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM, "message": "unsupported claim", "gate": "fact", "severity": pipeline.GATE_SEVERITY_HARD}]\n        instruction, _ = pipeline.build_dynamic_retry_instruction(rows)\n        self.assertIn("安全性が担保される", instruction)\n        self.assertIn("一次情報より強い保証", instruction)\n\n    def test_reader_value_keeps_length_observable_only(self):\n        article = ("## 身近な入口\\n\\n普通の読者にも分かる説明です。\\n\\n## 判断\\n\\n私なら小さく試します。\\n") * 150\n        signals = pipeline._reader_experience_signals(article)\n        self.assertGreater(signals["article_char_count"], 3200)\n        self.assertTrue(signals["soft_only"])\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8')
