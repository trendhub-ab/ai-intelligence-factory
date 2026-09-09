# AI Intelligence Factory Run308 仕様追補 — Public Copy Alignment

更新日: 2026-09-09  
状態: **current public-copy governance addendum**

## 1. 目的

Run307で確定したGeneric Use-Decision Productを、公開LP・プロフィール・記事CTAを含むcurrent reader-facing surfaceで一貫して維持する。

中心価値は変更しない。

> **「このAI、使える！」を、根拠付きで判断できる。**

Run308は新しい商品機能ではなく、Run307の価値提案が旧Proposal-First表現や旧Source表記へ回帰することを防ぐgovernance layerである。

## 2. current public-copy contract

- 商品の主語は顧客/クライアントではない。
- 自分の開発、業務利用、必要に応じた提案を横断する。
- 顧客提案は利用場面の一つとして許可する。
- current source listは **GitHub / Hacker News / ArXiv / OfficialVendor**。
- Product Huntはcurrent public sourceとして案内しない。
- article CTA link labelは **月額1,980円の内容を見る**。
- fixed note LP / profileの手動反映copyは `docs/reference/RUN308_PUBLIC_COPY_ALIGNMENT.md` を正本とする。
- Run307のPaid Product / Member Surfaceそのものは引き続きcurrent authority。

## 3. fail-closed scope

`run308_public_copy_alignment_guard.py` はcurrent surfaceだけを検査する。

対象:

1. `docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md` のCanonical fixed-note LP section
2. `run296_editorial_format_v2.py` のcurrent article CTA
3. `PAID_PRODUCT_CONTRACT.md` のnote有料導線
4. `docs/reference/RUN308_PUBLIC_COPY_ALIGNMENT.md` のhuman-only handoff

歴史資料やRun270互換層に旧見出しが存在すること自体はfailureにしない。監査証跡を消すための全置換は禁止する。

Repository-wide Falsification required check内でRun308 Guardと専用unit testsを実行する。

## 4. public note boundary

**公開noteの編集・公開はhuman-onlyを維持する。**

Run308は公開noteへブラウザ操作、API操作、DOM操作を行わない。公開済み固定LP・プロフィールの変更は、`docs/reference/RUN308_PUBLIC_COPY_ALIGNMENT.md` のexact handoffを人間が確認して反映する。

## 5. safety / cost

- Gemini/model追加call: **0**
- 新規有料API: **0**
- Notion schema変更: **0**
- Evidence / Decision / Source Score変更: **0**
- Production Source architecture変更: **0**
- Scheduled Daily: **PAUSEDのまま**
- Public note auto release: **禁止のまま**

## 6. authority relationship

- Paid Product Strategy: **Run307**
- Member Surface: **Run307**
- Source Architecture: **Run268**
- Current Public Copy Alignment / human-only handoff: **Run308**

Run308は上記既存authorityを上書きせず、reader-facing copyの整合だけを追加でFail-Closedする。
