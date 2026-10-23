# AIIF operational policy update — unrestricted Gemini API execution hours

Decision: 2026-10-24 (JST), directly authorized by the owner.
**Previous policy "Gemini API calls only after 17:00 JST" is withdrawn immediately.**
API may run at any hour. This supersedes historical scheduling limits and one-off 17+ gates, including the earlier P5 evidence-led proof. Historical documents and old completed Runs remain unchanged as audit evidence.

Scope: AIIF development, shadow/replay and standard operational API calls. This change removes only the clock gate; it does not authorize unapproved production deployment, publishing, unbounded retries or duplicate runs.

Unchanged safeguards:
- Respect user-authorized purpose and run count; no simultaneous duplicate triggering.
- Provider quota and cost controls, 429/503-only fallback where specified, bounded retries, no Lite.
- Frozen A/B digest, C-only 3-case whole-set model locking, human editorial and fact gates.
- No note/Notion/Production/main modifications in this P5.1 experimental proof branch.
- A workflow may be run immediately **after** its own required CI and prerequisite checks pass; time of day must no longer block it.

Implementation status: the P5.1 one-shot fallback helper and the new one-shot test workflow have their previous 17:00 JST guards removed. Other legacy/historical run files should not be treated as current operating-policy authority. Any independently active clock-based guard discovered in production requires a separate reviewed change before claiming all deployed code has been migrated.
