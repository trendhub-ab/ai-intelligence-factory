# P0 C-1 Network Admin Handoff

Status: **NO-GO until the running-state inbound-boundary proof passes**

Scope: GCP network boundary only. This is an ops-only handoff and must not be merged to `main`.

## Owner decision

- **Cloud NAT will not be introduced for this remediation.**
- The VM may retain its existing external access configuration so required outbound GitHub/note HTTPS connectivity continues to work.
- C-1 closure therefore depends on proving that no unauthorized inbound remote-shell path reaches the VM while it is running.

## Established evidence

- The persistent note VM is currently stopped.
- The VM NIC has one external access configuration; five consecutive stopped-state reads confirmed a stable count of `1`.
- Latest no-NAT boundary audit: two SSH-ingress allow rules are applicable to the VM; at least one includes world SSH (`0.0.0.0/0` or equivalent). The exact IAP source range was not applicable in the latest target-aware evaluation.
- Project SSH-key inheritance is blocked on the VM.
- OS Login is disabled on the VM.
- Serial console is disabled.
- No instance-level SSH key metadata was observed.
- A VM-specific deny firewall could not be created by the GitHub Actions operational identity because `compute.firewalls.create` is not granted.
- Project-level `testIamPermissions` is not available to the operational identity, so unobserved permissions must not be inferred.
- A prior guest-side attempt found TCP/22 listening even though `ssh.service` / `sshd.service` was not found. Ubuntu socket activation remains a hypothesis until the actual listener is identified.

## Minimal remediation design without NAT

Do **not** remove the VM external access configuration as part of this remediation.

1. With an already-authorized GCP network/security administrator, change the SSH firewall design so that **world SSH no longer applies to this VM**. Prefer explicit target tags or target service accounts for workloads that truly require SSH instead of untargeted/project-wide SSH.
2. Review the second applicable SSH-ingress rule as well and ensure it is either required and explicitly scoped or does not apply to this VM. Do not infer safety from its source range alone.
3. Do not add a replacement inbound SSH rule for this VM unless a separately reviewed operational requirement proves it is necessary.
4. Keep `block-project-ssh-keys=true`, OS Login disabled, no instance SSH-key metadata, and serial console disabled.
5. Start the VM for a bounded proof only after the firewall scoping change is complete.
6. Verify the self-hosted runner reconnects and required GitHub/note HTTPS outbound connectivity still works, with zero note mutation during the proof.
7. Identify the actual TCP/22 listener read-only. Disable/mask only the verified SSH socket/service that owns TCP/22. Do not guess a unit name.
8. Re-run the C-1 audit while the VM is **RUNNING** and require all of the following:
   - required outbound GitHub connectivity: present
   - required note HTTPS reachability: present, with zero note mutation during the proof
   - world-SSH firewall applicability to this VM: absent
   - any other SSH-ingress applicability: absent unless separately approved and explicitly scoped
   - TCP/22 listener: absent
   - project SSH-key inheritance: blocked
   - OS Login: disabled
   - instance SSH-key metadata: absent
   - serial console: disabled
   - ledger parent/database permissions remain `0700` / `0600`
9. If every condition passes, C-1 may be closed while retaining the VM external access configuration. If any unauthorized inbound remote-shell path remains applicable or TCP/22 remains exposed, C-1 stays NO-GO.

## Least-privilege boundary

The required privileged change is now limited to **scoping/removing SSH ingress applicability for this VM**. Do not grant Owner/Editor/Compute Admin to the GitHub Actions operational identity.

Prefer a one-time change by an already-authorized GCP network/security administrator, followed by read-only verification through the existing ops workflow.

## Risk acceptance

Retaining an external IPv4 address is an explicit owner design decision. It is acceptable for this C-1 closure only if the running-state proof demonstrates that unauthorized inbound remote-shell routes are not applicable to the VM and TCP/22 is not listening. External IP presence alone is no longer a C-1 failure condition under this approved design; exposed inbound administration is.

## Fail-closed rules

- Do not introduce Cloud NAT for this remediation.
- Do not start the VM before world SSH applicability is corrected.
- Do not broaden IAM to Owner/Editor/Compute Admin.
- Do not leave project-wide world SSH applicable to this VM.
- Do not expose project IDs, service-account identities, VM names, public IPs, note draft IDs, or private URLs in public evidence.
- Do not merge this ops branch into `main`.
- No automatic note publication is authorized.
