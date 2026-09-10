# Run331 — Profile form snapshot hardening

## Why
Run330 successfully saved the exact new note biography, but its post-save invariant compared every input on the whole page. note re-rendered unrelated/transient controls after save, so the updater reported a false failure even though the public profile was already current.

## Change
- Scope unrelated-setting comparison to the form that owns `textarea[name="editBiography"][aria-label="自己紹介"]`.
- Compare only visible semantic user controls.
- Exclude the authorized biography field itself.
- Ignore DOM ordering, hidden framework tokens, global header/search controls, CSS/classes/React IDs, and transient disabled state.
- Preserve exact creator-name assertion and the exact-one-save contract.
- Emit a bounded concrete diff if a real unrelated profile-form setting changes.

## Production state
The profile is already current from Run330 and was independently confirmed by Run329 with status `already_current_no_probe_needed`. Run331 is a code-hardening change only; it does not require another profile save.

## Cost / boundaries
- Gemini/model calls: 0
- Notion writes: 0
- No article publication
- No profile mutation is required for Run331 validation
