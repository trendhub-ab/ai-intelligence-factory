# V1 Eyecatch Copy: Production activation and proof

Status: **pending operator setup and MERGE GO.** This document does not authorize a Daily run, migration, note write, or PR merge.

## Why a repository secret is mandatory

`trendhub-ab/ai-intelligence-factory` is a **public** repository. The `runtime-state` branch is therefore public, even though it is used for mutable operational state. Never push unpublished article titles, summaries, bodies, eyecatch copy, or Fernet keys to this branch in plaintext. The V1 cache writes authenticated **Fernet ciphertext only**; the content-key URL is HMAC-obscured.

The optional cross-run cache is disabled if the Actions secret `AIIF_EYECATCH_COPY_FERNET_KEY` is absent, malformed, or the runtime token is unavailable. Local transient `.copy.json` remains ignored by Git.

## Zero-leak provisioning (repository administrator, **after review/merge**)

### CLI, on your own computer

1. Install and authenticate `gh` (GitHub CLI). Run `gh auth status` to confirm the target identity has admin access to this repository.
2. Generate a **new random Fernet-compatible 32-byte key locally** and pass it directly via standard input into GitHub's secret manager. **Do not** print, paste into chat, include in `--body`, save in a tracked file, or use a sample/static key.

   macOS / Linux shell:

   ```bash
   python3 -c 'import base64,os,sys;sys.stdout.write(base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"))' | gh secret set AIIF_EYECATCH_COPY_FERNET_KEY --app actions --repo trendhub-ab/ai-intelligence-factory
   ```

   Windows PowerShell:

   ```powershell
   python -c "import base64,os,sys;sys.stdout.write(base64.urlsafe_b64encode(os.urandom(32)).decode('ascii'))" | gh secret set AIIF_EYECATCH_COPY_FERNET_KEY --app actions --repo trendhub-ab/ai-intelligence-factory
   ```

   GitHub CLI encrypts secrets before submission. These pipelines do not expose the key value in the command line. A rotated key intentionally invalidates all earlier remote-cache entries (the existing source remains authoritative, and no article text is lost).

3. Confirm the **name and updated timestamp only**, never the value:

   ```bash
   gh secret list --app actions --repo trendhub-ab/ai-intelligence-factory
   ```

   Alternatively, use repository Settings → Secrets and variables → Actions → New repository secret. Generate the Fernet key locally and enter it directly in the GitHub UI; do not transmit it through support chat or a PR comment.

## Separate, synthetic-only activation test (after MERGE GO)

From the default `main` branch, manually run **Eyecatch Copy Activation Proof**. This workflow is deliberately **manual** and restricts its writer job to `refs/heads/main`. It does not generate article content, contact Gemini, create note drafts, or modify Notion.

```bash
gh workflow run eyecatch-copy-activation-proof.yml --ref main --repo trendhub-ab/ai-intelligence-factory
```

Expected jobs:

- `encrypted-writer`: `ACTIVATION_PROOF_WRITER=PASS` (only synthetic record encrypted and written to public `runtime-state`)
- `encrypted-reader`: `ACTIVATION_PROOF_SEPARATE_RUNNER=PASS` (different Actions runner, authenticated decryption; changed input rejected)
- `remove-synthetic-canary`: `ACTIVATION_PROOF_CLEANUP=PASS` (the exact synthetic record is deleted; HTTP 404 checked)

The workflow must be **GREEN overall**, and the cleanup must finish, before declaring the Actions secret activated. Failed or partial canaries are not an article-stage proof and must be investigated without weakening Publication/Eyecatch gates.

## Remaining proof boundary

The completed PR #832 synthetic Actions writer/reader/cleanup evidence proved the GitHub token and encrypted cross-run mechanics using a disposable key, **not the production key**. After this main-only activation proof, V1 still needs an explicitly authorized bounded real-article verification to demonstrate that the production caller binds the correct title/summary and never skips its render/Publication checks.

The current `pipeline.py` production eyecatch call passes title and summary; it **does not supply full article text** to the semantic layout function. Therefore do not claim that this cache is keyed by the full manuscript until that data flow is explicitly redesigned and independently tested. No additional Gemini provider send is introduced by the cache itself.

Only an explicit **MERGE GO** authorizes merging PR #832. This runbook does not change that gate.
