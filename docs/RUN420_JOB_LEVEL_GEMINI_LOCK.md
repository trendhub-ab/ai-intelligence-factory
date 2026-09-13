# Run420 — Job-level Gemini Concurrency Lock

## Background

The Run418/419 ChatOps workflow is triggered by an `issue_comment`. The repository has many other `issue_comment` workflows. With the shared `ai-intelligence-gemini-budget` concurrency group declared at workflow level, even workflows whose jobs will later be skipped can enter the concurrency queue first. GitHub keeps at most one running and one pending member in a concurrency group, so a later irrelevant run can replace/cancel the pending eyecatch workflow before `render-attach` starts.

This was observed after the Run419 merge: the Run418 workflow was created and immediately completed as `cancelled` with zero jobs. No Gemini, Notion, GCP or note operation ran.

## Change

Move the existing shared concurrency declaration from workflow scope to the `render-attach` job only:

- group remains `ai-intelligence-gemini-budget`;
- `cancel-in-progress` remains `false`;
- only the exact owner-approved Run418 command can reach the job and acquire the lock;
- irrelevant skipped `issue_comment` workflows can no longer cancel the pending eyecatch job;
- the Gemini request remains serialized against other jobs using the same shared group.

The VM start, existing private-draft header refresh and VM stop jobs do not call Gemini and therefore do not need the Gemini budget lock.

## Safety boundaries

Run420 does not change the eyecatch design, Run419 deterministic plan repair, target page, model choice, model budget, Notion mutation boundary, existing-draft identity checks or publication policy. Public publication remains prohibited; the workflow ends after the existing private draft header is updated and verified.
