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
   - Gemini quotaはProject単位で共有されるため、旧`key_scopes`方式を廃止。`GEMINI_QUOTA_PROJECT_ID`のhashを永続scopeとし、APIキー交換・複数キーでも同一Projectの使用量を共有する。旧counterは同一quota dayなら保守的に合算migrationし、生のProject ID/API Keyは保存しない。
36. Gemini API消費の原因追跡不能
   - `GeminiUsageAudit`を追加し、model / request kind /短いcandidate context / success-error / SDKが返すtoken usageで送信試行を記録。Prompt本文は保存せず、`gate_history/gemini_usage_*.json`をPrivate Artifact化。Daily通知にもmodel別・用途別のattempt内訳を出し、Screening/Calibration/Deep Dive/Quality Retry/transport retryの消費原因を追跡可能にした。

## テスト結果

- Adversarial / Failure Injection: 105/105 PASS
- Notion Persistence: 48/48 PASS
- Safety Unit: 75/75 PASS
- Subscription Attribution: 11/11 PASS
- unittest discovery: 239/239 PASS
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
