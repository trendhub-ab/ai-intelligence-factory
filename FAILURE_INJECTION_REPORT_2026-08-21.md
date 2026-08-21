# AI Intelligence Factory Failure Injection / Adversarial Regression Report

実施日: 2026-08-21
対象: 最終監査版 + 収益最適化 + Content Portfolio Balance + Source ROI Learning（4 Source同格化）

## 結論

実記事を待たずに想定事故を人工再現し、危険なFalse Negativeを優先して修正した。Gate閾値は緩和していない。

## 発見・修正した主要リスク

1. Evidence metadataの部分一致誤認
   - `rapid`→`API`、`latest`→`test`等を誤FOUND化する余地をword boundaryで修正。
2. 数値の条件すり替え
   - 同じ20%・1.8xでもmetric、hardware、datasetが明示的に矛盾する場合を拒否。
3. 数値表現差のFalse Positive
   - `x/×/倍`、`1/40/40分の1`、sec/秒、ms/ミリ秒等を正規化。
4. Primary Sourceの見せかけ解決
   - URL存在だけではResolvedにせず実取得を要求。外部記事付きHNのcommentだけではResolvedにしない。
5. Redirect SSRF
   - 全redirect hopでpublic URL検証しprivate/link-local/credential destinationを遮断。
6. Cross-source Duplicate
   - 公式/一次URL共有をidentityとして利用。タイトル類似だけの推測dedupeは採用しない。
7. Needs Editorial Reviewの誤公開
   - Public DB syncはPublic Approved AND Readyを必須化。Monthly Digest/StaleでもReadyとReviewを分離。
8. Budget枯渇
   - Deep Dive model cap、transport retry cap、reserve判定が上限超過しないことを固定テスト化。
9. Retry品質劣化
   - Retryで具体Action/Decision Voiceが「注視」へ崩壊するケースをHuman Appeal degradationとして検出。
10. Gate組合せ誤遷移
   - `Fact FAIL × Publication REVIEW`がNeeds Editorial Reviewへ入る経路を修正し、Fact FAILはQuality Failedへ固定。
11. Public DB失効漏れ
   - Public Approved AND Readyの追加/更新だけでなく、承認取消・Review・Quality Failedへ戻った内部レコードの会員DBコピーをarchiveするreconciliationへ変更。
12. Notion/公開責務混線
   - note無料公開とNotion会員資産の可視性を分離し、Readyでも`Subscription Visibility=Subscriber Only`を維持。
13. Pending Retry飢餓
   - `last_edited_time ASC`で最長待機候補から処理し、同じ3件の再失敗で後続が永久に詰まる経路を防止。
14. Workflow時間・Quota競合
   - Daily/Real Regressionを同一Gemini concurrency groupへ統一しtimeoutを45分へ拡張。Persistent Counterはlocal budget precheck後にreserve。
15. Notion Schemaコスト事故
   - production開始時に必須Property名/型をPreflightし、Schema破損ならGemini消費前に停止。
16. 4 Source必須性 / Product Hunt日次鮮度
   - GitHub / Hacker News / arXiv / Product Huntを同格の必須4 Sourceとして維持。Product HuntはToken欠落をPreflightし、72時間lookback＋NEWESTで日次新着を優先するが、これはAPI adapter要件でありROI上の優遇ではない。
17. 会員限定Digest/未公開ログ漏洩
   - 月次Digestの公開GitHub raw URL生成をhard disableしPrivate Artifact化。Real Regressionも原稿全文をWorkflow Logへ出さない。
18. Review本文陳腐化
   - 再Review時に新稿commit後、旧Review manuscriptをbest-effort archiveして古いReview本文の固定化を防止。
19. Screening/Calibration通信ハング
   - Deep DiveだけでなくScreening/Calibrationにも1call watchdogを設定し、同期SDKの長時間hangでWorkflow全体を失わない。
20. Public DB write payload互換性
   - Notion read responseの`id/type/plain_text`等response-only fieldを除去してwritable payloadへ変換。同名列の型違いはpartial sync前にFail-Closed。
21. 旧事業モデルPrompt残存
   - Screening Promptの「有料note」前提を除去し、無料noteで認知獲得→会員向け意思決定DBへ接続する現行モデルに統一。
22. Evidence監査証跡欠落
   - Supplementで実取得したPDF/DocsをReady/Needs Editorial Review双方のEvidence URLsと原稿末尾へ残す。arXiv abs/pdfはStock identityでは統合するが監査証跡では別URL保持。
23. Stock未永続化候補へのGemini浪費
   - Final Scoreが閾値以上でもNotion Stock保存失敗候補は同RunのDeep Dive対象から除外し、3層設計とコスト整合を固定。
24. 旧Discovery URLによる再重複
   - HN item URL / Product Hunt discovery URLを明示migration aliasとしてidentityへ追加し、旧Stock行との重複再発を防止。
25. Test harness直接実行差
   - `if __name__ == "__main__"`を末尾へ移し、直接実行とunittest discoveryで新規Regressionが欠落しないよう修正。
26. 品質スコアと利益スコアの混線
   - Commercial Value / Shelf-LifeをDecision Scoreと独立推定し、Stock閾値・Quality Gateを一切変更しない。Commercial 100でもDecision 59はStock不可。
27. 短命ニュース偏重
   - Profit Priority上位3枠にEVERGREENがない場合だけ、cutoffから8点以内のEVERGREENを最大1枠まで条件付き繰上げ。弱いEVERGREENを強制しない。
28. Profit metadata欠損によるScreening行喪失
   - Commercial/Shelf補助値の欠落・不正は中立値50へFail-Safeし、有効なDecision Score行をRecoveryへ落とさない。
29. 高収益テーマの単一Topic偏重
   - Screening/Calibrationの同一Gemini呼出しでTopicを9分類し、TOP3が単一Topicへ偏る場合だけcutoffから6点以内の別Topicを保守的に繰り上げる。`OTHER`/欠落時は並べ替えず、大幅に弱い別Topicも強制しない。唯一のEVERGREEN枠を保護し、品質・収益Priorityを侵食しない。

30. Source ROIでのProduct Hunt特別扱い
   - 旧実装ではProduct Huntだけ動的配分上限50、他3 Sourceは75であり、必須Sourceである一方ROI上は非対称だった。Source固有capを撤去し、4 Sourceすべて共通`SOURCE_ROI_MAX_FETCH_PER_SOURCE=75`へ統一。同一ROIなら同一配分になる対称性テストを追加した。

31. 無料記事と有料商品の責務混線
   - CTAは「会員向け意思決定DB + 月次サマリー」だけを訴求し、有料note記事を商品化しない。無料本文は最後まで無料のまま維持する。
32. Attribution ID分裂
   - article_idをDiscovery Sourceではなくcanonical Primary URLから生成し、utm差・HN/Product Hunt/GitHub等の発見経路差で同一記事の実績が分裂しないよう固定。
33. 壊れた/危険なCTA公開
   - Landing URLはHTTP(S)かつhost必須。不正・未設定時はCTA/manifestだけをSkipし、公開記事や品質Pipelineは止めない。
34. False Revenue Attribution / PII混入
   - metrics importで`attribution_method`を必須化し、note dashboardだけの数値から加入・売上を帰属する入力を拒否。未知article_id、PII様column、負値/不正数値もFail-Closed。実測は現版のランキングへ自動反映しない。

35. APIキー単位counterによるRPD過少計上
   - Gemini provider quotaはProject単位だが、repository内のPersistent Counterは他のAI Studio/別repository利用を観測できない。Project ID必須停止を撤廃し、repository-local stable scopeへ変更。旧`key_scopes`/`project_scopes`は同一quota dayなら保守的に合算migrationし、生のRepository名/Project ID/API Keyは保存しない。Project-wideの最終的な正はAI Studio Rate Limits画面とする。
36. Gemini API消費の原因追跡不能
   - `GeminiUsageAudit`を追加し、model / request kind /短いcandidate context / success-error / SDKが返すtoken usageで送信試行を記録。Prompt本文は保存せず、`gate_history/gemini_usage_*.json`をPrivate Artifact化。Daily通知にもmodel別・用途別のattempt内訳を出し、Screening/Calibration/Deep Dive/Quality Retry/transport retryの消費原因を追跡可能にした。

37. Persistent上限拒否でDeep Dive local budgetを空費
   - 旧実装は`DEEP_DIVE_MODEL_BUDGET.consume()`がPersistent Counter reserveより先で、18/18到達modelへの「実API未送信」試行でも12回/Run枠を消費した。Local budgetは事前確認だけ行い、Persistent reserve成功後にのみconsumeする順序へ変更。Persistent Safety Cap到達modelは同Runの`SESSION_EXHAUSTED_MODELS`へ登録し、後続候補で再試行しない。
38. Pending RetryによるFresh候補Quota侵食
   - 旧Pending RetryはTOP3候補を新規収集前に処理し、各候補のQuality Retryまで許可したため、前日失敗記事だけでFlash系RPDを大量消費し得た。`GEMINI_PENDING_RETRY_REQUEST_BUDGET=2`を追加し、Pending Retry由来の実Gemini送信を最大2回/Runへ制限。専用枠超過時は翌Runへ残し、Fresh候補用Deep Dive枠を優先する。
39. 非Repairable Quality Retryのtoken浪費
   - `primary_evidence_insufficient`等、再作文では一次Evidenceが増えないReason Codeでも1回Retryしていた。Primary Source未解決、Technical Claims不足、Numeric Conditions不足、Freshness未解決、高リスクAction根拠不足、`PUB_SOURCE_SUFFICIENCY`等をnon-repairableとしてRetry対象外にし、Fact/表現/構造など再生成で修復可能な問題だけをRetryする。
40. 初稿MAX_TOKENSのFunnel消失
   - 初稿が`FINISHREASON.MAX_TOKENS`でもRetry後の最終Reason CodeだけでFunnelを集計すると0件に見える不整合を修正。各生成試行の`generation_attempt_history`と`any_generation_truncated`をGate Recordへ保持し、最終稿が別理由でもRun中に一度でもtruncatedなら`MAX_TOKENS`へ計上する。

41. Prompt用12k contextによるFact Evidence欠落
   - 実記事で、論文PDFに存在する数値がPrompt用の短縮contextから落ち、Fact Gateがunsupportedと誤判定した。Gemini Promptは12kのまま維持し、Fact/Evidence Gate専用に最大180kの`verification_context`を分離。PDF/公式HTMLの実取得本文を照合対象へ含め、追加APIコストを発生させない。
42. 数値Range・単位翻訳のFalse Positive
   - `10-hour`↔`10時間`、`50–80 percent`↔`50〜80%`、`3–7x`↔`3〜7倍`を正規化し、Range内部の末尾値を二重claimとして再判定しない。明示条件の矛盾検出は維持する。
43. LOW RISK ActionとSource Factの混線
   - Rust記事の`Cargo.lockを監査する`のような低リスク運用Actionを、一次資料に語が無いだけで`FACT_UNSUPPORTED_NAMED_FACT`へ落としていた。ローカル設定/lock/log等の監査成果物だけを限定許可し、未確認の外部製品機能は従来どおりFailする。
44. 一般略語複合語の固有名誤認
   - `LLM API`等の一般技術略語の組合せを外部製品名扱いしてSource Boundary Failする誤検出を修正。ALL-CAPS一般略語のHard Negative保護は維持。
45. 架空の実体験persona見逃し
   - `現場でAI導入を進める立場として`、`日常のコーディング支援でも同じ傾向を感じます`等、実在しない職務/日常体験をHuman Appeal Review理由として検出。編集判断（`私なら`等）や読者への経験質問は許可する。
46. Research future workのFreshness誤発火
   - 論文中の`future work`や一般的な将来研究を製品release予定と混同しない。公開/提供/発売/support/availability等の状態変更予定だけFreshness follow-up対象とする。
47. 長大LandingがSupplement PDFをverificationから押し出す事故
   - Verification contextを単純な先頭truncateで連結せず、既存Evidenceと後取得PDF/Docsへ配分し、双方の冒頭/末尾を保持する。後取得Evidenceが丸ごと監査対象外になる経路をRegression化した。

## テスト結果

- Adversarial / Failure Injection: 127/127 PASS
- Notion Persistence: 48/48 PASS
- Safety Unit: 76/76 PASS
- Subscription Attribution: 11/11 PASS
- unittest discovery: 262/262 PASS
- Synthetic Regression Full: 500/500 PASS
- Critical failures: 0

## 残存リスク

- 真のSemantic Duplicate（同じ内容だが公式URLも異なるミラー/転載）は、誤除外防止のため自動統合していない。将来は人間確認付き候補化が安全。
- 外部サイトのJS-only本文、認証壁、Cloudflare等はEvidence取得不能になり得る。Fail-Closed/Pending Retryで扱う。
- Gemini側モデル挙動・API障害、および同一Google ProjectをFactory外から使ったAPI消費は完全には内部counterだけで把握できない。モデル上限を公式上限より低く設定するSafety Marginと、AI Studio dashboardの実Run観測は引き続き必要。
- Public DB reconciliationはURLを内部/会員DBの安定キーとして扱うため、同一記事のURL自体を人手で別URLへ置換した場合は旧公開コピーの自動失効が効かない余地が残る。
- 数値条件の自然言語は無限に多様であり、現在は明示的なmetric/hardware/dataset条件の矛盾を重点防御している。
- Commercial Value / Shelf-Lifeはmetadata-onlyの予測値であり、実売上・CTR・会員転換をまだ学習していない。Revenue Feedback Loop導入までは「利益の代理指標」として扱う。

## 判断

現段階では機能追加より、実Runで新しいFailure Patternが出た時だけ固定Regressionへ追加する運用へ移行するのが合理的。
