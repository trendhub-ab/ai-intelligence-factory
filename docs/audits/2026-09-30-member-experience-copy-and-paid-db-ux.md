# Paid member conversion & customer UX audit — 2026-09-30

Status: **code remediation prepared; no live note or Notion mutation**.
Cost: **zero Gemini / other LLM API calls**. Current Fresh v3 remains frozen: do not change its pinned files, thresholds, Writer, Gate, or source-stratified measurement.

## Evidence and limits

Sources inspected:
- Public note fixed LP: https://note.com/trendhub_biz/n/ned673e381ef8 (web cache returned an **older** Sep 1 published revision; do **not** override later production Run312/313 audit from cached text)
- Internal production verification: Run335 onboarding verified Sep 10, Run339b logged-out membership join surface verified Sep 10, including ¥1,980/month, Decision DB + Digest, exact members-only onboarding link.
- Canonical member-home Notion: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`, fetched Sep 30; current links to canonical DB, September 29 Decision Brief and judgment memo.
- Live canonical member DB sampled five pages from `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`, latest API fetch. **Two of five** (Dify and ComfyUI) visibly contained **two generated decision callouts**. That sample is not a population duplicate rate.
- Sep 29 Decision Brief links to DB pages with older `最終確認日` values. Dify / ComfyUI Aug 29, MLflow and Hugging Face Datasets Aug 23. `last_edited_at` from a newer Notion layout sync is **not proof that sources were reread**.
- One Dify source list includes comet.com third-party integration docs under the old blanket `公式・一次情報` label. Link is potentially useful but **not a first-party Dify source**.
- Production `Member Presentation Sync` already has an explicit `force_full_body_sync` mode and conservative duplicate generated-block cleanup. Normal delta mode scans changed rows + one sentinel, so some old duplicate pages can persist if not selected. **No assumption of root cause beyond observed duplicate surface and this documented scan limitation.**

## Copywriter diagnosis

The issue is not lack of content quantity. The paid product needs an unequivocal distinction between the *complete free article* and the value of a reusable, cross-topic decision workflow. Generic `Evidence / Action / 月次サマリー` copy requires readers to translate internal jargon into benefits.

**Fresh v3 / Ready protection:** Review discovered that `note_manuscript.py` is a fingerprinted public-note publication-policy input. Changing it—even with a canary-only legacy branch—would change the policy SHA and invalidate old Ready provenance or alter Fresh v3's frozen quality comparison. The code was **restored byte-for-byte to latest main**, and existing CTA tests remain unchanged. `member_offer_copy.py` is an **offline, reviewed proposal module only**: it is deliberately **not imported by** `note_manuscript.py`, not deployed to note and not fingerprinted. Its distinct contextual angles, accurate offer and tracking preservation are tested in isolation. Only after Fresh v3 is complete (or the experiment is explicitly re-registered as a new protocol) should a separate, fingerprinted publication/Ready rollout be considered.

## Read-only catalogue audit and safe repair

`member_experience_quality_audit.py --read-only` scans the canonical member DB. It reports proven duplicate generated callouts, similarly labeled **unclassified** callouts (manual content must not be silently removed), absent/30+ day old source review dates and pages with no visible generated decision body. This scan is separate from the existing mutating sync and is manually triggered; it has **no model credentials, no scheduled execution and no write functions**.

If the full audit confirms generated duplicates and no ambiguous/manual same-label blocks on target pages, run the existing `Member Presentation Sync` manually with `force_full_body_sync=true`. That pre-existing conservative path removes qualified duplicate generated callouts while keeping unrelated manual blocks. Then rerun this read-only audit to verify duplicates = 0 and inspect actual pages from a logged-out/member-reader standpoint. **Do not blindly delete callouts or relabel stale facts as freshly verified.** Exact source rechecks need their own evidence-reviewed maintenance workflow, not cosmetic timestamp changes.

## Human rewrite candidate — fixed LP (review first; never auto-publish)

### Headline
「新しいAIが出た」。それで、私たちは何をすればいい？

### Opening
便利そうなAIを見つけるたび、タブが一つ増える。
料金を調べて、公式情報を読んで、似たツールを探す。気づけば、何を決めたかったのか分からなくなる。

欲しいのはニュースの山ではありません。
**「自分の仕事や開発で、これは使えるのか？」を判断する材料**です。

AI Intelligence Factoryは、公式情報や技術資料を手がかりに、その判断を整理するサービスです。無料noteでは一つの話題を最後まで読めます。会員向けには、その後も使える判断材料をDBとDecision Briefにまとめています。

### Before / after use
**情報を知るだけでなく、使う・試す・待つ・避けるを選ぶ。**

- **まずBriefで見当をつける** — 重要な話題を絞って、今の判断を短時間で確認する。
- **気になる候補はDBで確かめる** — 使える場面、利用前の条件、主なリスク、判断理由、参照情報までたどる。
- **使う前に一度立ち止まる** — 会員ホームの判断メモで、何を小さく試せばよいか整理する。

たくさん読めることよりも、もう一度調べる手間を減らせることを大切にしています。

### Membership and delivery disclosure
**月額1,980円** — 会員限定のAI意思決定DBとDecision Brief。
加入後は、メンバー限定の「最初にお読みください」記事に従ってNotionの利用登録をお願いします。加入と同時にDBが自動開放されるわけではありません。閲覧のためにNotionの有料契約は必要ありません。PCでの閲覧を推奨し、スマートフォン向けの簡易ビューもあります。

**［月額1,980円のサービス内容を見る］**
Destination: https://note.com/trendhub_biz/membership

Note: The exact current public fixed LP must be re-read in a **fresh uncached logged-out browser** and diffed against the latest human-edited published manuscript before any manual publication. This copy is a **proposal**, not a claim that the live page has changed.

## Acceptance criteria

1. Offline **staged** CTA tests: safety/research/tool/general angles differ, price and entitlement disclosure are accurate, tracking attribution is unchanged, missing link fails closed; current note/Ready output is byte-identical and the proposed module is not yet wired.
2. Offline member UI tests: independent primary+third-party domains show neutral links; original `last_reviewed` remains unchanged and displays correctly; generic `非常に有力` topic adds no false `なぜ今` claim.
3. Paid DB audit tests reproduce two concurrent generated callouts and a separate similarly labeled human block without writing/deleting either; full scan reports exact source review dates, not Notion edit timestamps.
4. Repository-wide regression and member UX CI pass, **no Gemini usage**, no public note mutation, no automatic Fresh/Daily.
5. Subsequent *manual* operations: read-only full catalogue scan → explain ambiguous pages → explicit full body sync → read-only confirmation → fresh public LP audit → human publication approval.
