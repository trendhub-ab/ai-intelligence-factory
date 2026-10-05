# P0 C-1 Network Admin Handoff

Status: **NO-GO until the running-state inbound-boundary proof passes**

Scope: GCP network boundary only. This is an ops-only handoff and must not be merged to `main`.

## Owner decision

- **Cloud NAT will not be introduced for this remediation.**
- The VM may retain its existing external access configuration so required outbound GitHub/note HTTPS connectivity continues to work.
- C-1 closure therefore depends on proving that no unauthorized inbound remote-shell path reaches the VM while it is running.

## Established evidence

- The persistent note VM is currently stopped after the emergency-stop proof.
- The VM NIC has one external access configuration. When the VM is started, that configuration can assign an ephemeral external IPv4 address.
- Five consecutive stopped-state reads returned an external access configuration count of `1`; treat that as the canonical current state.
- Two SSH ingress allow rules apply to the VM; both are untargeted/project-wide. One includes world SSH and one includes the IAP SSH range.
- Project SSH-key inheritance has been blocked on the VM.
- OS Login has been disabled on the VM.
- Serial console is disabled.
- No instance-level SSH key metadata was observed.
- A VM-specific deny firewall could not be created by the GitHub Actions operational identity because `compute.firewalls.create` is not granted.
- Project-level `testIamPermissions` is not available to the operational identity, so unobserved permissions must not be inferred.
- A guest-side attempt found TCP/22 listening even though `ssh.service` / `sshd.service` was not found. Ubuntu socket activation remains a hypothesis until the actual listener is identified.

## Minimal remediation design without NAT

Do **not** remove the VM external access configuration as part of this remediation.

1. With an already-authorized GCP network/security administrator, change the project-wide SSH firewall design so that **neither the world-SSH rule nor the IAP-SSH rule applies to this VM**. Prefer explicit target tags or target service accounts for the workloads that truly require SSH rather than untargeted project-wide SSH rules.
2. Do not add a replacement inbound SSH rule for this VM unless a separately reviewed operational requirement proves it is necessary.
3. Keep `block-project-ssh-keys=true`, OS Login disabled, no instance SSH-key metadata, and serial console disabled.
4. Start the VM for a bounded proof only after the firewall scoping change is complete.
5. Verify the self-hosted runner reconnects and required GitHub/note HTTPS outbound connectivity still works, with zero note mutation during the proof.
6. Identify the actual TCP/22 listener read-only. Disable/mask only the verified SSH socket/service that owns TCP/22. Do not guess a unit name.
7. Re-run the C-1 audit while the VM is **RUNNING** and require all of the following:
   - required outbound GitHub connectivity: present
   - required note HTTPS reachability: present, with zero note mutation during the proof
   - world-SSH firewall applicability to this VM: absent
   - IAP-SSH firewall applicability to this VM: absent, unless a separately approved operator path exists
   - TCP/22 listener: absent
   - project SSH-key inheritance: blocked
   - OS Login: disabled
   - instance SSH-key metadata: absent
   - serial console: disabled
   - ledger parent/database permissions remain `0700` / `0600`
8. If every condition passes, C-1 may be closed while retaining the VM external access configuration. If any inbound remote-shell path remains applicable or TCP/22 remains exposed, C-1 stays NO-GO.

## Least-privilege boundary

The required privileged change is now limited to **scoping/removing SSH ingress applicability for this VM**. Do not grant Owner/Editor/Compute Admin to the GitHub Actions operational identity.

Prefer a one-time change by an already-authorized GCP network/security administrator, followed by read-only verification through the existing ops workflow.

## Risk acceptance

Retaining an external IPv4 address is an explicit owner design decision. It is acceptable for this C-1 closure only if the running-state proof demonstrates that inbound remote-shell routes are not applicable to the VM and TCP/22 is not listening. External IP presence alone is no longer a C-1 failure condition under this approved design; exposed inbound administration is.

## Fail-closed rules

- Do not introduce Cloud NAT for this remediation.
- Do not start the VM before the SSH firewall applicability is corrected.
- Do not broaden IAM to Owner/Editor/Compute Admin.
- Do not leave project-wide world SSH applicable to this VM.
- Do not expose project IDs, service-account identities, VM names, public IPs, note draft IDs, or private URLs in public evidence.
- Do not merge this ops branch into `main`.
- No automatic note publication is authorized.
