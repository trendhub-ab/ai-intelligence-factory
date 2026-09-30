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

## Human rewrite candidate — fixed LP (human review, not published)

**UX goal:** On mobile, show the problem, the difference from the free article, the monthly price and the next step before a long feature explanation. Reduce ambiguity and friction, not manufacture urgency. Reuse the current verified note membership destination, not an unverified checkout URL.

### Headline

「このAI、使える？」を、毎回ゼロから調べないために。

### First screen: a concrete problem, the offer and one next step

新しいAIを見つけた。公式サイトを読んで、料金を調べて、似たツールとも比べてみる。  
気になる情報は増えたのに、肝心の「自分の仕事で使える？」が決まらない。

そんな調べ物を、少しでも減らしたい人のために作りました。

**AI Intelligence Factory｜月額1,980円**  
月次Decision BriefとAI意思決定DBで、候補を選ぶときの根拠を、あとから確かめられる形にまとめています。

無料noteは、一本の記事だけで最後まで読めます。有料会員は、その記事の続きではありません。複数のAI・技術を比較し、実際に試すかどうかを考えるための場所です。

**［月額1,980円のサービス内容・参加手順を見る］**  
Destination: https://note.com/trendhub_biz/membership

### Before/after: one short reader journey, not a feature catalogue

たとえば、仕事で使うAIを選ぶとき。

1. **まずBriefを開く。** 重要な話題を絞って読み、調べる候補を決める。
2. **気になったらDBで確かめる。** 向いている用途、確認すべき条件、主なリスク、判断理由、参照先を一か所で読む。
3. **使う前に、次の一手を考える。** 自分の業務に近い条件で小さく試すのか、まだ見送るのかを整理する。

「話題を知った」で終わらず、「自分ならどうする？」まで進む。そのための会員サービスです。

### Free versus paid: draw an honest boundary

- **無料note：** その日の一つの話題を、背景と結論まで読めます。続きを読むための支払いは不要です。
- **月額会員：** 話題を横断したDecision BriefとDBで、あとから複数の候補を調べ、判断材料と参照先に戻れます。

収録されている情報には、それぞれ確認した時点があります。あらゆる価格・仕様が常に最新であることを保証するものではありません。導入前には参照先の最新の提供条件をご確認ください。

### Who it is for (and an honest non-fit)

自分でAIを開発・試用する人、業務でツールを選ぶフリーランスや小規模事業者、必要に応じて顧客に提案する人へ。

反対に、ニュースを毎日たくさん読むことだけが目的なら、無料noteから始めていただければ十分です。

### Membership and delivery: remove the post-payment surprise

**月額1,980円**で、会員向けのDecision BriefとAI意思決定DBを利用できます。

加入後は、noteのメンバー限定「最初にお読みください」に沿ってNotionの利用登録をお願いします。その後、招待を受けて閲覧します。**お支払いと同時にDBが自動で開く仕組みではありません。** 閲覧のためにNotionの有料プランは必要ありません。PCでの閲覧を推奨し、スマートフォン用の簡易ビューも用意しています。

**［月額1,980円のサービス内容・参加手順を見る］**  
Destination: https://note.com/trendhub_biz/membership

**Publication safeguard:** This manuscript is a proposal. Before publication, capture the actual current published LP and membership join screen in an uncached logged-out browser; reconcile any later human edits and verify the precise access steps, benefits and CTA destination. Obtain explicit human publication approval. Do not deploy the staged free-article CTA while Fresh v3 provenance remains frozen.

## Existing + future catalogue consistency (follow-up to PR #663)

This branch now connects **both member DB detail rendering and the monthly Decision Brief**
to a single presentation-only `member_reader_quality_policy.py` module.
The shared rules identify actual source domains, translate decision states into
plain Japanese and classify **recorded** source-review dates as current (up to
30 days), older, missing, invalid or future. A page's Notion edit timestamp
and the Brief refresh time **never imply a fresh source review**.

- Canonical Subscriber Technology → Member Presentation → Run307 body remains
  the existing route for **both newly created and previously stored** entities.
  It uses the same shared disclosure before recommendations. No new model
  generation or historical Evidence/Decision rewrites were added.
- Run271 normal delta body sync continues to process recent edits/new pages,
  checking a body-contract sentinel. A changed sentinel causes a full
  migration; however, a single sentinel **cannot prove that all old pages
  are free of duplicates**, so a dedicated complete audit and explicit
  full sync are still necessary.
- Monthly Brief consumes the canonical member DB **after** presentation/body
  sync and now prints the source-review date before each shortlist judgment
  and each recorded important change. Stale/missing/future dates display
  honest warnings; raw internal ADOPT/TEST abbreviations and blanket
  `公式` link labels are no longer exposed. The month/page update label is
  visibly distinct from evidence verification.
- The independent read-only full-catalogue audit now uses the same date
  classification, including invalid or future review dates. It never
  upgrades a date merely to make a page look consistent.
- Synthetic tests exercise new vs. existing rows, the 30-day boundary,
  malformed/future dates, third-party source labels and both Brief views.
  The same shared-policy tests run before any member write workflow.

**Use of Gemini:** The owner has permitted limited Gemini work where genuinely
useful. This consistency implementation still makes **zero model calls**;
it only transforms previously stored/verified fields. Gemini may be considered
for *separate evidence-bound editorial improvements*, not for inventing a
review date or overriding original source/decision fields.

### Post-merge operating acceptance (NOT YET DONE)

1. Full **read-only** canonical paid-catalogue audit on the merged main,
   preserving the report and separating confirmed generated duplicates from
   unclassified same-label manual content.
2. Investigate ambiguous pages individually. Use existing explicit
   `force_full_body_sync=true` Member Presentation Sync only when the
   preflight demonstrates manual content will not be deleted. The workflow
   creates/updates detail views, then rebuilds the Brief.
3. Run the full read-only audit again; confirm **zero confirmed duplicates**,
   no unreviewed ambiguous cleanup, and all absent/old/invalid dates visibly
   disclosed rather than cosmetically refreshed.
4. Confirm a newly created synthetic/integration member record and an existing
   record render the same disclosure and section order, and confirm the Brief
   matches the canonical DB.
5. Approve and publish the separately staged note/LP copy only after fresh
   logged-out visual checks and the frozen Fresh protocol is respected.

**Limit:** Display consistency can be guaranteed by the shared deterministic
policy and guarded sync; actual evidence freshness cannot be guaranteed
without performing a separate source recheck.

## Acceptance criteria

1. Offline **staged** CTA tests: safety/research/tool/general angles differ, price and entitlement disclosure are accurate, tracking attribution is unchanged, missing link fails closed; current note/Ready output is byte-identical and the proposed module is not yet wired.
2. Offline member UI tests: independent primary+third-party domains show neutral links; original `last_reviewed` remains unchanged and displays correctly; generic `非常に有力` topic adds no false `なぜ今` claim.
3. Paid DB audit tests reproduce two concurrent generated callouts and a separate similarly labeled human block without writing/deleting either; full scan reports exact source review dates, not Notion edit timestamps.
4. Repository-wide regression and member UX CI pass, **no Gemini usage**, no public note mutation, no automatic Fresh/Daily.
5. Subsequent *manual* operations: read-only full catalogue scan → explain ambiguous pages → explicit full body sync → read-only confirmation → fresh public LP audit → human publication approval.
