# V3 P5 — Evidence-led conversational writing and strict output hygiene

**2026-10-23, experimental Draft. Not publication-approved.** Parent: `feature/editorial-engine-v3-p5-compact-colloquial-20261023` at `df2ab9a1852085c5c2f9b1072fa56cc649140a67`.

## Actual evidence for the change

Review the three real C manuscripts from Gemini 3 Flash Preview Run [#39959106785](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/39959106785). Their structural proof passed 16/16, but editorial quality did not. The source material and prior owner-approved examples are the evidence here, **not an inferred measure of interestingness**.

- FFT: `今、私たちが取るべきアクション` is a consulting-style conclusion; sweeping claims such as FFT being the backbone of all digital technology and AI's mathematical accuracy are not in frozen case Evidence.
- Elastic: `いつも頭を悩ませる` invents an industry-universal pain point; `私が特に注目したのは` announces Writer emotion; `膨大なコストがかかる再学習` strengthens the source claim without evidence. A prior actual P5 output successfully explained the technique as a `計算量のつまみ`: favor specific mechanism-first explanation.
- Claude + Workspace: `仕事中、ブラウザのタブを何往復もしている自分に気づくことがあります` implies firsthand experience the Writer did not have; `混ぜてみる dream。` is an unrepaired English filler in Japanese prose, not a proper technical term.

## Smallest targeted correction

1. Keep compact policies from #850. Add **one short contrastive voice card** to C *Persona Article Generation* and the five-stage C bundle only; do not paste it into the Fact-Safe Review stage, the A/B baseline, or other planning stages. Concrete examples identify why the actual failed language sounds false/stiff, and show fact-grounded casual alternatives. All examples are *style-only*, not source facts or text to copy. No word-count quotas, mandatory slang, or one-size-fits-all rhetorical questions.
2. **Narrow hard output guard** rejects examples of dangling lower-case English editorial filler (such as `混ぜてみる dream。`). It intentionally allows real technical words and correctly supplied source quotations. Ignore Markdown inline/fenced code. Never auto-rewrite AI output.
3. **Non-gating audit flags** identify *possible* fabricated lived experiences, *possible* unsupported industry generalizations, consulting-style action headings, and broader suspicious English tokens. These are surface cues only: **not** source-verification, reader delight measurement, or permission to publish. The existing Fact-Safe Review and H1 full-manuscript gate continue unchanged.
4. Dedicated provider-free tests exercise actual prior failure patterns and negative controls, source-quotation exemption, preserved B persona, and the C-only path.

## Product and operating bounds

- Absolutely no Gemini calls or workflow dispatch in this change. No production, main, note, Notion, release, queue, or DB mutation. Parent PR and this revision remain Draft.
- No relaxation of source-locked factual assertions, uncertainty, model metrics, plan/pricing restrictions, comparison conditions, Human Appeal or Publication Gate.
- The C bundle prompt fingerprint necessarily changes, so older C proofs are invalid for acceptance of this revision. A/B from Run #39239644474 stay immutable, and any next C-only provider run needs a **new explicit user authorization after 17:00 JST**.
- Editorial GO requires **blind comparative human review** of three fresh real C manuscripts against the previous ones, with specific attention to human warmth, live factual boundaries, absence of fabricated experience and output cleanliness.
