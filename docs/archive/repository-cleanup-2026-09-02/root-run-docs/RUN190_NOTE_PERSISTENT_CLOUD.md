# Run190 — note Persistent Cloud Chrome

## Purpose

Run190 replaces real note draft creation on GitHub-hosted disposable Chromium with an
on-demand Google Compute Engine VM that keeps the same Google Chrome profile across stop/start
cycles.

The normal operating flow is:

1. smartphone starts `Create note Draft` in GitHub Actions;
2. a GitHub-hosted controller job authenticates to Google Cloud with OIDC/WIF;
3. it starts the stopped Compute Engine VM;
4. the VM's registered self-hosted runner comes online;
5. the draft job runs in installed Google Chrome with the persistent profile;
6. existing Run185-189 safety and persistence checks remain active;
7. the workflow stops the VM even after a draft-job failure;
8. a guest startup failsafe also shuts the VM down after 35 minutes;
9. the user reviews the private note draft on the phone before any public release.

`prepare_only=true` remains on GitHub-hosted Ubuntu and does not start the VM.

## Why this architecture

A stopped Compute Engine VM keeps its attached persistent disk and configuration. Run190 keeps
Chrome's user-data directory on that disk instead of reconstructing a new browser profile for
every draft. The VM itself is started only for the workflow and stopped afterward.

## Repository variables required

Add these under `Settings -> Secrets and variables -> Actions -> Variables`:

- `GCP_PROJECT_ID`
- `GCP_NOTE_VM_ZONE`
- `GCP_NOTE_VM_NAME`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`

The helper `infra/gcp/run190_setup_controller.sh` prints the exact values after it creates the
controller identity and VM.

Existing repository secrets remain the source for Notion and Telegram credentials. The existing
`NOTE_STORAGE_STATE_B64` secret is retained only as an optional first-session bootstrap. Run190
filters it so only `note.com` cookies/localStorage can be applied to the cloud profile; Google or
other login-provider cookies are not copied.

## One-time Google Cloud setup

Open Google Cloud Shell and run the controller helper from a checkout of the repository:

```bash
export PROJECT_ID='YOUR_BILLING_ENABLED_PROJECT_ID'
bash infra/gcp/run190_setup_controller.sh
```

Defaults are:

- zone: `asia-northeast1-b`
- VM: `aiif-note-draft`
- machine: `e2-medium`
- boot disk: 30 GB balanced persistent disk
- OS: Ubuntu 24.04 LTS

The helper enables Compute Engine and WIF-related APIs, creates a GitHub-controller service
account, creates a repository-restricted GitHub OIDC provider, creates/updates the VM, and
installs a 35-minute shutdown startup failsafe.

For the first validation the controller service account receives
`roles/compute.instanceAdmin.v1`. The WIF provider is restricted to
`trendhub-ab/ai-intelligence-factory`. After production validation this role can be replaced by a
custom start/stop/get-only role.

## One-time VM runner setup

Start the VM once, open a shell on it, and obtain a fresh registration token from:

`GitHub repo -> Settings -> Actions -> Runners -> New self-hosted runner`

Then, inside the VM checkout:

```bash
export GITHUB_RUNNER_TOKEN='THE_FRESH_ONE_TIME_TOKEN'
bash infra/gcp/run190_bootstrap_runner.sh
```

The helper installs Google Chrome stable, Xvfb and the latest GitHub Actions runner, registers the
runner with label `aiif-note-cloud`, installs it as a service, and creates the persistent Chrome
profile directory under the runner user's home.

After the runner appears as `Idle` in GitHub, stop the VM. From then on the workflow starts and
stops it automatically.

## Browser/session behavior

Run190 uses Playwright's `launch_persistent_context(..., channel="chrome")` against installed
Google Chrome. It does not install or launch the GitHub-hosted Playwright Chromium build for the
actual draft job.

If the persistent profile does not yet have a working note session, Run190 can apply only the
`note.com` portion of the existing `NOTE_STORAGE_STATE_B64` once and retry the normal editor
entry flow. On success that state becomes part of the persistent Chrome profile. If note requires
interactive re-authentication in the future, the run fails closed and does not advance the Notion
queue.

## Cost and failure controls

- `prepare_only` never starts Compute Engine.
- actual draft workflow starts the VM only on demand.
- `stop-cloud-vm` uses `always()` so browser/test failure still requests VM stop.
- every VM boot independently schedules a guest shutdown after 35 minutes, covering a GitHub
  cleanup failure or an offline/stuck runner.
- Persistent Disk and other retained Google Cloud resources can still incur charges while the VM
  is stopped.

## Safety invariants retained

- no Gemini/model call in note draft automation;
- only `Ready` + `投稿待ち` queue rows are eligible;
- legacy paid-area control markers remain fail-closed/skip-safe under Run185;
- note editor route must be proven before mutations;
- header image, title, body, autosave and reopen persistence checks remain;
- Notion changes to `投稿準備中` only after draft persistence verification;
- no public-release action exists in Run190.
