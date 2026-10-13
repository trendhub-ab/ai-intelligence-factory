# Execution ledger — published terminal + event-aware dedup

Plan: `docs/superpowers/plans/2026-10-13-published-terminal-event-dedup.md`
Spec: `docs/superpowers/specs/2026-10-13-published-terminal-event-dedup-design.md`

- Task 1 status: RED reconstruction in progress.
- Ruling: the first implementation commit was created before a failing test run was observed. To restore TDD evidence, the production module is temporarily removed on the implementation branch so CI can observe the intended RED state; the module will then be restored unchanged/minimally and CI re-run for GREEN. Main remains untouched.
- Pre-flight interface: Task 2 consumes `automatic_regeneration_decision` from Task 1.
- Pre-flight interface: Task 3 consumes `automatic_regeneration_decision` from Task 1.
- Pre-flight interface: Task 4 consumes existing `candidate_identity_urls`; no new shared interface is introduced unless characterization tests prove a gap.
