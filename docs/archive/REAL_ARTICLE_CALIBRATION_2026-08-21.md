# Real Article Gate Calibration — 2026-08-21

対象: 2026-08-21 Dailyで生成され、private gate reviewへ保存された4記事。

## 実地で確認した不一致

| ケース | 旧Gate判定 | 実地監査での論点 | 一般化した修正 |
|---|---|---|---|
| AI Post-Training | Quality Failed | PDFに存在する`10時間`をunsupported扱い。架空の「現場でAI導入を進める立場として」は未検出 | PDF/HTMLの広いverification context、単位正規化、fabricated experience検出 |
| VLA / covert coordination | Quality Failed | `50〜80%`等のrangeを条件不一致扱い、`LLM API`を固有名扱い | range正規化、一般略語複合語の除外、広いverification context |
| Rust arrayref | Quality Failed | LOW RISKの`Cargo.lock`監査Actionを一次資料外Fact扱い | Fact主張とLOW RISK Actionを分離 |
| Harness Continual Learning | Needs Editorial Review | researchの`future work`系表現がFreshness不足へ寄りやすい | Freshness Triggerをrelease/availability等の状態変更予定へ限定 |

## 設計原則

- Gateを一律に緩めない。
- 実在Evidenceを見落とすFalse Positiveは減らす。
- 架空体験のようなFalse Negativeは新たに止める。
- 固有記事タイトル・URLによる例外処理は作らない。
- GeminiへのPrompt contextは12,000文字のまま維持し、追加APIコストを発生させない。
- Fact/Evidence照合だけ、実取得一次資料から最大180,000文字の`verification_context`を利用する。

## Regression化した代表条件

1. `10-hour` と `10時間` は同一数値条件として扱う。
2. `50–80 percent` と `50〜80%`、`3–7x` と `3〜7倍`を同値化する。
3. `Cargo.lock`等のローカルLOW RISK監査成果物は、逐語一致がないだけでFact FAILにしない。
4. LOW RISK文脈でも、未根拠の具体的外部製品能力は引き続きSource Boundary FAILとする。
5. `LLM API`等の一般略語複合語を固有製品名扱いしない。
6. `現場で〜を進める立場として`等の架空職務経験をHuman Appeal Review対象にする。
7. `私なら`、`私の見解では`等の編集判断は架空体験と区別して許可する。
8. arXivの`future work`だけではFreshness follow-upを発火しない。
9. `future version is planned for public release`等の明示的な状態変更予定はFreshness対象のまま維持する。

## 追加の防御（実装時再監査）

- `verification_context`は単純な先頭truncateを行わない。長文は冒頭と末尾を残す。
- Landing pageが180,000文字近くまで埋まっていても、後取得の論文PDF/公式Docsへ監査枠を確保する。
- `日常のコーディング支援でも同じ傾向を感じます`のように主語を省略した筆者体験も検出する。
- `〜経験はないでしょうか`のような読者への問いは、筆者が体験を詐称した表現とは扱わない。

## Release Regression結果

- Safety: 76/76
- Notion Persistence: 48/48
- Adversarial / Failure Injection: 127/127
- Subscription Attribution: 11/11
- unittest discovery: 262/262
- Synthetic Regression Full: 500/500, critical failure 0
