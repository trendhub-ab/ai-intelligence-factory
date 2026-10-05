from pathlib import Path

path = Path('tests/test_run273_reader_draft_autoflow.py')
text = path.read_text(encoding='utf-8')
old = '''    def test_target_workflow_keeps_zero_vm_preflight_and_human_only_publication_boundary(self) -> None:\n        source = DRAFT_WORKFLOW.read_text(encoding="utf-8")\n        hosted = source[source.index("  preflight:"):source.index("  start-cloud-vm:")]\n        worker = source[source.index("  create-draft:"):source.index("  stop-cloud-vm:")]\n\n        self.assertIn("Validate publish-safe candidate before any VM start", hosted)\n        self.assertIn("run199_note_vm_preflight.py", hosted)\n        self.assertIn("needs.preflight.outputs.should_start_vm == 'true'", source)\n        self.assertIn("Revalidate and pin exact candidate on private worker", worker)\n        self.assertIn("Read durable ledger authority before heavy browser setup", worker)\n        self.assertIn("Create one private note draft", worker)\n        self.assertIn("NOTE_DRAFT_CONFIRM", worker)\n        self.assertNotIn("needs.preflight.outputs.selected_sync_id", source)\n        self.assertNotIn("public release", source.lower().replace("no public release", ""))\n'''
new = '''    def test_target_workflow_keeps_hosted_preflight_and_human_only_publication_boundary(self) -> None:\n        source = DRAFT_WORKFLOW.read_text(encoding="utf-8")\n        hosted = source[source.index("  preflight:"):source.index("  create-draft:")]\n        worker = source[source.index("  create-draft:"):]\n\n        self.assertIn("Validate publish-safe candidate before browser delivery", hosted)\n        self.assertIn("run199_note_vm_preflight.py", hosted)\n        self.assertIn("needs.preflight.outputs.should_continue == 'true'", source)\n        self.assertIn("Revalidate and pin exact candidate on hosted worker", worker)\n        self.assertIn("Read durable ledger authority before browser setup", worker)\n        self.assertIn("Create one private note draft", worker)\n        self.assertIn("NOTE_DRAFT_CONFIRM", worker)\n        self.assertIn("python run194_note_hosted.py", worker)\n        self.assertNotIn("needs.preflight.outputs.selected_sync_id", source)\n        self.assertNotIn("self-hosted", source)\n        self.assertNotIn("start-cloud-vm", source)\n        self.assertNotIn("public release", source.lower().replace("no public release", ""))\n'''
if old not in text:
    raise SystemExit('Run273 VM-specific test block not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

path = Path('member_customer_surface_contract.py')
text = path.read_text(encoding='utf-8')
needle = '    "note_delivery_ledger.py",  # P0-B durable delivery authority, not reader/customer copy\n'
replacement = (
    '    "note_delivery_gcs.py",  # P0-B hosted cloud ledger adapter, not reader/customer copy\n'
    '    "note_delivery_ledger.py",  # P0-B durable delivery authority, not reader/customer copy\n'
)
replacement_text = ''.join(replacement)
if '"note_delivery_gcs.py"' not in text:
    if needle not in text:
        raise SystemExit('NON_MEMBER note delivery marker not found')
    text = text.replace(needle, replacement_text, 1)

needle2 = '    "note_publication_reconcile.py",\n'
replacement2 = (
    '    "note_publication_reconcile.py",\n'
    '    "run194_note_hosted.py",  # Hosted private-draft entrypoint; operational infrastructure only\n'
)
if '"run194_note_hosted.py"' not in text:
    if needle2 not in text:
        raise SystemExit('NON_MEMBER note reconcile marker not found')
    text = text.replace(needle2, replacement2, 1)
path.write_text(text, encoding='utf-8')
