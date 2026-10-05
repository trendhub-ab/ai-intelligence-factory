# P0 C-1 Network Admin Handoff

Status: **NO-GO until the running-state proof passes**

Scope: GCP network boundary only. This is an ops-only handoff and must not be merged to `main`.

## Established evidence

- The persistent note VM is currently stopped after the emergency-stop proof.
- The VM NIC has one external access configuration. When the VM is started, that configuration assigns an ephemeral external IPv4 address.
- There is currently no Cloud NAT configuration covering the VM subnet.
- Two SSH ingress allow rules apply to the VM; both are untargeted/project-wide. One includes world SSH and one includes the IAP SSH range.
- Project SSH-key inheritance has been blocked on the VM.
- OS Login has been disabled on the VM.
- Serial console is disabled.
- No instance-level SSH key metadata was observed.
- A VM-specific deny firewall could not be created by the GitHub Actions operational identity because `compute.firewalls.create` is not granted.
- Project-level `testIamPermissions` is not available to the operational identity, so unobserved permissions must not be inferred.
- A guest-side attempt found TCP/22 listening even though `ssh.service` / `sshd.service` was not found. The listener owner still needs to be identified after private egress exists; Ubuntu socket activation is a hypothesis, not evidence.

## Minimal remediation design

Do **not** grant broad firewall administration merely to close C-1. The preferred sequence is:

1. With an already-authorized GCP network administrator, create a **Public Cloud NAT** path for the VM subnet in the VM region. Use automatic NAT IP allocation unless an existing policy requires a reserved address.
2. Verify the NAT configuration covers the exact VM subnet.
3. Only after NAT exists, remove the VM NIC external access configuration so the VM cannot receive an external IP on start.
4. Start the VM for a bounded proof. Verify the self-hosted runner reconnects outbound through NAT and can reach the required GitHub/note HTTPS endpoints without making a note mutation.
5. Identify the actual TCP/22 listener read-only. Disable/mask only the verified SSH socket/service that owns TCP/22. Do not guess a unit name.
6. Re-run the C-1 audit while the VM is **RUNNING** and require all of the following:
   - external IPv4/IPv6: absent
   - Cloud NAT (or equivalent approved private egress): present and covering the VM subnet
   - outbound GitHub connectivity: present
   - required note HTTPS reachability: present, with zero note mutation during the proof
   - TCP/22 listener: absent
   - project SSH-key inheritance: blocked
   - OS Login: disabled
   - instance SSH-key metadata: absent
   - serial console: disabled
   - ledger parent/database permissions remain `0700` / `0600`
7. If every condition passes, C-1 can be closed without changing the project-wide SSH firewall rules. If TCP/22 or another remote shell path remains reachable, C-1 stays NO-GO and firewall/security-admin remediation becomes necessary.

## Least-privilege boundary

Google Cloud documents `roles/compute.networkAdmin` as sufficient to configure Public Cloud NAT. That role manages networking resources but does not grant firewall-rule administration. Do not grant `roles/compute.securityAdmin` unless the final running-state proof demonstrates that firewall changes are actually required.

Do not grant a new privileged role to the GitHub Actions operational identity merely for convenience. Prefer a one-time change by an already-authorized network administrator, followed by read-only verification through the existing ops workflow.

## Fail-closed rules

- Do not remove the external access configuration before private egress exists.
- Do not start the VM merely to probe TCP/22 until the external-IP issue is remediated.
- Do not broaden IAM to Owner/Editor/Compute Admin.
- Do not alter project-wide firewall rules without a separate reviewed plan.
- Do not expose project IDs, service-account identities, VM names, public IPs, note draft IDs, or private URLs in public evidence.
- Do not merge this ops branch into `main`.
- No automatic note publication is authorized.
