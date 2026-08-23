# Run111 — ArXiv Practical Artifact Gate Validation

## Scope
Run110のポートフォリオ最適化は維持し、**ArXiv候補をPRACTICALとみなす条件だけ**を厳格化した。

変更対象:
- `inventory_bootstrap.py`
- `tests/test_run111_arxiv_practical_artifact_gate.py`（新規）

変更していない領域:
- 通常Daily収集 / Screening / Calibration
- Product Reviewの最終Assessment
- Adoption Score / Status
- Evidence / History / Subscriber同期
- 記事生成、Fact / Editorial / Publication / Human Appeal Gate
- Gemini budget / Persistent Counter
- Run110のSource/Category/Laneポートフォリオ分散ロジック

## Falsification
### 反証1: 「実務用語が多いArXiv = 実用Technology」ではない
Run110ではArXiv要約に `platform`, `workflow`, `deployment`, `SDK` 等が含まれるだけでPRACTICALになり得た。
Run111ではArXivに限り、実装Artifactの強い根拠がない場合はRESEARCHとする。

### 反証2: 「ArXivは全部RESEARCH」でもない
GitHub / GitLab / Codeberg / Hugging Face / PyPI / npm 等の実装Artifact根拠が確認できるArXivはPRACTICALを維持できる。

### 反証3: Security/Risk論文を実装有無で落としてはいけない
RISK判定をArtifact Gateより先に維持。Security/Attack/Vulnerability等の判断価値は従来どおり残る。

### 反証4: GitHub等の既存PRACTICAL判定を変えてはいけない
非ArXiv候補のPRACTICALロジックは変更していない。

## New behavior
`has_implementation_artifact(record)` を追加。
ArXiv候補についてのみ:
1. RISKなら従来どおりRISK
2. DISCOVERYなら従来どおりDISCOVERY
3. 実装Artifactあり → PRACTICAL
4. 実装Artifactなし → RESEARCH

強いArtifact根拠:
- github.com
- gitlab.com
- codeberg.org
- huggingface.co
- pypi.org
- npmjs.com
- URLを伴う `code available at`, `official implementation`, `github repository` 等

この判定はBootstrapの**review order専用**であり、Notionのauthoritative Categoryや最終Assessmentを変更しない。

## Verification
- Run111 targeted + Run110 tests: 12/12 PASS
- Full unittest: **492/492 PASS**
- pytest: **492 passed + 10 subtests**
- compileall: PASS
- Synthetic Full: **500/500 PASS**
- Synthetic critical failures: **0**
- Synthetic major failures: **0**
- production_write_isolation: **true**
- GitHub Actions YAML parse: **6/6 PASS**

## Release decision
PASS。Run110の他ロジックを維持した局所修正としてリリース可能。
次は `mode=plan` を再実行し、実データ上で `Tuning the Stochastic Machine` 等の実装ArtifactなしArXivがRESEARCHへ戻ることを確認してからApplyへ進む。
