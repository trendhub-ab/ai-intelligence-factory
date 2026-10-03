"""Canonical paid-member customer-surface contract.

This module is presentation-only and provider-free.  It exists so customer-facing
surfaces cannot be added ad hoc without an owner, a readability audit, and a clear
human-language purpose.

Live Notion page copy for the manually managed member home / judgment memo is kept
here as the repository source of truth.  The generated Monthly Brief / DB detail /
Digest remain owned by their deterministic renderers.
"""
from __future__ import annotations

from pathlib import Path
import ast

MEMBER_HOME_PAGE_ID = "3c5479ff-dca9-8103-bff0-f2d5f408d35f"
MONTHLY_BRIEF_PAGE_ID = "3d0479ff-dca9-81de-b614-fef528d2f32c"
JUDGMENT_MEMO_PAGE_ID = "3d3479ff-dca9-8119-b0d8-c014b068fe82"
MEMBER_DB_ID = "b2787ee0-5b58-4ca7-b4eb-774f60237f1f"
MEMBER_DATA_SOURCE_ID = "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404"

SURFACES = {
    "free_note_article": {
        "owner": "note_manuscript.py",
        "audit": "run222_note_presentation_integrity.py",
        "purpose": "one complete free article",
    },
    "free_note_cta": {
        "owner": "note_manuscript.py",
        "audit": "run308_public_copy_alignment_guard.py",
        "purpose": "honest bridge from a complete free article to membership",
    },
    "membership_lp_and_join": {
        "owner": "run333_membership_description_exact_update.py",
        "audit": "run339_membership_public_funnel_audit.py",
        "purpose": "price, benefit, access steps and join action",
    },
    "member_onboarding": {
        "owner": "run315_member_onboarding_update.py",
        "audit": "run326_member_onboarding_public_audit.py",
        "purpose": "first-use setup without surprises",
    },
    "member_home": {
        "owner": "member_customer_surface_contract.py",
        "audit": "member_surface_coverage_guard.py",
        "purpose": "tell members what to do next without teaching internal codes",
    },
    "monthly_decision_brief": {
        "owner": "member_monthly_decision_brief_sync.py",
        "audit": "tests/test_member_monthly_decision_brief_sync.py",
        "purpose": "scan-first monthly shortlist: decision, meaning, action, evidence",
    },
    "monthly_digest": {
        "owner": "content_generation_protocol.py",
        "audit": "tests/test_member_customer_surface_contract.py",
        "purpose": "monthly reading index with finished articles separate from unreviewed candidates",
    },
    "member_db_views": {
        "owner": "member_customer_surface_contract.py",
        "audit": "member_surface_coverage_guard.py",
        "purpose": "find candidates without exposing operator metadata by default",
    },
    "member_db_detail": {
        "owner": "run307_use_decision_member_surface.py",
        "audit": "tests/test_run307_use_decision_member_surface.py",
        "purpose": "plain-language use decision with evidence disclosure",
    },
    "judgment_memo": {
        "owner": "member_customer_surface_contract.py",
        "audit": "member_surface_coverage_guard.py",
        "purpose": "turn a candidate into a small, explicit test or a deliberate no-go",
    },
}

REQUIRED_SURFACES = frozenset((
    "free_note_article", "free_note_cta", "membership_lp_and_join",
    "member_onboarding", "member_home", "monthly_decision_brief",
    "monthly_digest", "member_db_views", "member_db_detail", "judgment_memo",
))
# Explicit inventory of the current member modules, including historical adapters
# and read-only probes. New modules in these namespaces need classification.
CLASSIFIED_MEMBER_MODULES = frozenset((
    "member_body_delta_checkpoint.py",
    "member_client_action_alignment.py",
    "member_customer_surface_contract.py",
    "member_experience_quality_audit.py",
    "member_human_language_ux.py",
    "member_human_language_ux_v2.py",
    "member_monthly_decision_brief_sync.py",
    "member_notion_read_healthcheck.py",
    "member_offer_copy.py",
    "member_presentation_body_sync.py",
    "member_presentation_identity.py",
    "member_presentation_sync.py",
    "member_reader_quality_policy.py",
    "member_surface_coverage_guard.py",
    "member_ux_body_fast.py",
    "member_ux_guard.py",
    "member_verified_rereview_apply.py",
    "member_verified_rereview_dryrun.py",
    "provision_member_presentation_db.py",
    "run174_monthly_digest_integrity.py",
    "run212_member_review_copy.py",
    "run213_member_topic_specificity.py",
    "run214_member_action_specificity.py",
    "run215_member_action_final_dedup.py",
    "run219_member_human_language_ui.py",
    "run225_member_lifecycle_ui.py",
    "run250_member_client_action_product.py",
    "run270_proposal_first_member_surface.py",
    "run270_proposal_first_member_surface_guard.py",
    "run271_member_body_delta_sync_guard.py",
    "run307_use_decision_member_surface.py",
    "run314_member_onboarding_audit.py",
    "run315_member_onboarding_update.py",
    "run315_member_onboarding_update_dom_range.py",
    "run316_member_onboarding_finalize_probe.py",
    "run317_member_onboarding_server_save.py",
    "run318_member_onboarding_publish_cta_probe.py",
    "run319_member_onboarding_article_list_probe.py",
    "run320_member_onboarding_membership_dialog_probe.py",
    "run321_member_onboarding_official_edit_route_probe.py",
    "run321b_member_onboarding_edit_route_diagnostic.py",
    "run322_member_onboarding_version_confirm_publish_probe.py",
    "run323_member_onboarding_publish_surface_deep_probe.py",
    "run324_member_onboarding_trial_read_surface_probe.py",
    "run325_member_onboarding_finalize_latest.py",
    "run326_member_onboarding_public_audit.py",
    "run332_membership_description_edit_route_probe.py",
    "run333_membership_description_exact_update.py",
    "run334_membership_description_exact_update.py",
    "run337_membership_public_funnel_audit.py",
    "run339_membership_public_funnel_audit.py",
    "subscriber_decision_brief.py",
))
CUSTOMER_ENTRYPOINTS = {
    "note_manuscript.py": frozenset(["_fix_bold_boundary_brackets","find_internal_publication_markers","_strip_internal_note_control_lines","normalize_markdown_for_note","_normalize_note_title","build_article_attribution_id","build_subscription_tracking_url","build_subscription_cta","_reader_plain_text","_compact_reader_summary","_reader_summary_complexity","_pick_reader_summary_candidate","_find_reader_intro_fact_sentence","_reader_decision_fallback","build_reader_first_summary","_reader_published_date","build_reader_first_header","_remove_markdown_sections","_remove_reader_redundant_provenance","_prepare_reader_first_body","_split_reader_lead","build_clean_note_manuscript"]),
    "run333_membership_description_exact_update.py": frozenset(["_canon","_description_state","_public_description_state","_open_exact_edit","_other_plan_snapshot","_snapshot_diff","_require_other_settings_unchanged","_final_button","_verify_public_current_with_retry","update","main"]),
    "run315_member_onboarding_update.py": frozenset(["_field_text","_body_text","_sha256","_is_exact_editor","_open_editor","_membership_add_button","_membership_visible_state","_choose_all_members_if_prompted","_ensure_membership_selected","_verify_editor","_verify_public","update","main"]),
    "run307_use_decision_member_surface.py": frozenset(["_clean","_use_decision_text","_use_update_text","_show_topic","_source_label","_last_reviewed_label","_build_children","_body_matches_use_decision","install_navigation","install_body","contract"]),
    "content_generation_protocol.py": frozenset(["build_monthly_digest_markdown","_source_fact_discipline","_human_editorial_style_rules","_human_narrative_editorial_style_rules","_duo_narrative_editorial_style_rules","editorial_style_rules","_parse_gemini_response","extract_field","field_or_body","_promote_plaintext_section_titles","build_decision_prompt"]),
    "member_monthly_decision_brief_sync.py": frozenset(["_headers","_request","_rt","_paragraph","_heading","_bullet","_callout","_toggle","_divider","_page_url","_query_states","_score","select_top","select_changes","_change_direction_text","build_blocks","_children","_append","_delete","_rename","sync_monthly_brief","main"]),
}
# Other existing modules are explicitly classified as infrastructure/compatibility.
# A new Python module must be classified before it can introduce a new surface.
NON_MEMBER_MODULES = frozenset((
    "local_skills/__init__.py",
    "local_skills/a_plus.py",
    "local_skills/compiler.py",
    "local_skills/evidence_boundary.py",
    "local_skills/production_canary.py",
    "local_skills/publication_canonicalizer.py",
    "local_skills/writer.py",
    "tools/capture_note_session.py",
    "tools/editorial_ab.py",
    "x_discovery/__init__.py",
    "x_discovery/dedupe.py",
    "x_discovery/factory_adapter.py",
    "x_discovery/handoff.py",
    "x_discovery/models.py",
    "x_discovery/normalize.py",
    "x_discovery/providers.py",
    "x_discovery/runner.py",
    "x_discovery/url_resolution.py",
    "x_intelligence/__init__.py",
    "x_intelligence/freeform.py",
    "x_intelligence/generator.py",
    "x_intelligence/persona.py",
    "x_intelligence/runner.py",
    "x_intelligence/selector.py",
    "a_plus_editorial_orchestration.py",
    "article_revalidation.py",
    "arxiv_exhaustion_circuit.py",
    "arxiv_stability_layer.py",
    "backfill_evidence_ledger.py",
    "business_source_acquisition.py",
    "candidate_identity.py",
    "canonical_article_contract.py",
    "comment_write_contract.py",
    "content_db_contract_guard.py",
    "context_first_enrichment.py",
    "conversion_copy_diagnostics.py",
    "cross_db_contract_guard.py",
    "daily_portfolio_review.py",
    "operational_output_contract.py",  # P0-C operational receipts, not reader copy
    "decision_intelligence.py",
    "decision_intelligence_run255_core.py",
    "deep_dive_portfolio.py",
    "deferred_queue_policy.py",
    "editorial_eyecatch.py",
    "editorial_naturalness.py",
    "editorial_quality_memory.py",
    "evidence_authority.py",
    "evidence_context.py",
    "evidence_db_contract_guard.py",
    "evidence_ledger.py",
    "evidence_sufficiency.py",
    "external_product_review_import.py",
    "eyecatch_badge_taxonomy.py",
    "eyecatch_publication_contract.py",
    "fact_validation_signals.py",
    "fresh_candidate_supply_experiment.py",
    "fresh_model_fallback_budget.py",
    "fresh_protocol_quota_lock.py",
    "fresh_zero_model_preflight.py",
    "gate_reasoning.py",
    "gemini_provider_resilience.py",
    "gemini_temporary_exclusion.py",
    "gemini_timeout_rpd_fail_closed.py",
    "gemini_transient_recovery.py",
    "integration_stability_guard.py",
    "inventory_bootstrap.py",
    "legacy_eyecatch_renderer.py",
    "local_skills_daily_canary.py",
    "migrate_decision_intelligence.py",
    "migrate_japanese_display_label.py",
    "note_draft_automation.py",
    "note_eyecatch_persistence.py",
    "note_publication_reconcile.py",
    "note_ready_sync.py",
    "notion_access_policy_guard.py",
    "notion_payloads.py",
    "paid_db_launch_readiness.py",
    "pending_retry_validation.py",
    "pipeline.py",
    "portfolio_inventory_bootstrap.py",
    "product_delivery_maintenance.py",
    "product_review_assessment_rescue.py",
    "product_review_protocol.py",
    "production_e2e_validation.py",
    "production_pipeline.py",
    "public_db_contract_guard.py",
    "publication_contract.py",
    "publication_source_contract.py",
    "publish_yield_benchmark.py",
    "publish_yield_replay.py",
    "reader_experience_signals.py",
    "reader_quality_precision.py",
    "reader_value_review_bridge.py",
    "ready_eyecatch_finalize.py",
    "ready_note_body_resync.py",
    "ready_note_cover_apply.py",
    "ready_rescue_validation.py",
    "regression_suite.py",
    "repository_falsification_guard.py",
    "run156_decision_review_import.py",
    "run164_ai_relevance_calibration.py",
    "run172_production_reliability.py",
    "run173_operational_yield.py",
    "run175_semantic_fact_precision.py",
    "run176_scope_fidelity.py",
    "run177_paid_funnel_alignment.py",
    "run178_eyecatch_editorial_layout_optimizer.py",
    "run179_eyecatch_font_refinement.py",
    "run180_eyecatch_semantic_layout.py",
    "run181_eyecatch_visual_balance.py",
    "run182_eyecatch_conclusion_emphasis.py",
    "run183_eyecatch_emphasis_scale.py",
    "run185_note_ready_legacy_skip.py",
    "run186_note_header_image_resilience.py",
    "run187_note_editor_readiness.py",
    "run188_note_header_upload_fallback.py",
    "run189_note_editor_route_gate.py",
    "run190_note_persistent_cloud.py",
    "run191_note_crop_dialog_resilience.py",
    "run193_note_official_header_upload.py",
    "run194_note_current_contract.py",
    "run194_note_persistent_cloud.py",
    "run194_publication_contract.py",
    "run199_note_vm_preflight.py",
    "run202_chatops_control.py",
    "run203_runtime_state_channel.py",
    "run208_reader_value_repair.py",
    "run222_note_presentation_integrity.py",
    "run223_technical_claim_precision.py",
    "run224_multiplier_deterministic_rescue.py",
    "run225_portfolio_lifecycle.py",
    "run225_stock_lifecycle.py",
    "run226_reader_delight_planning.py",
    "run227_japanese_surface_integrity.py",
    "run228_reader_rhythm_planning.py",
    "run231_performance_telemetry.py",
    "run235_stage3b_source_normalization_migration.py",
    "run237_product_delivery_maintenance_migration.py",
    "run238_deep_dive_portfolio_migration.py",
    "run239_reader_experience_migration.py",
    "run240_editorial_naturalness_migration.py",
    "run241_batched_modularization_migration.py",
    "run242_notional_source_deferred_migration.py",
    "run243_content_generation_protocol_migration.py",
    "run244_decision_product_protocol_migration.py",
    "run245_fact_validation_migration.py",
    "run248_first_real_publish_quality_calibration.py",
    "run249_final_publication_surface_gate.py",
    "run260_gemini_model_routing.py",
    "run262_documentation_contract_guard.py",
    "run267_documentation_contract_guard.py",
    "run268_business_source_strategy.py",
    "run268_business_source_strategy_guard.py",
    "run269_acquisition_precision.py",
    "run269_acquisition_precision_guard.py",
    "run269_business_source_precision.py",
    "run269_live_acquisition_smoke.py",
    "run269_vendor_current_state.py",
    "run279_runtime_layer_guard.py",
    "run280_publication_dependency_guard.py",
    "run283_numeric_evidence_equivalence.py",
    "run284_reader_recovery_precision.py",
    "run285_operational_accounting.py",
    "run287_publication_date_provenance.py",
    "run291_note_private_draft_audit.py",
    "run292_note_rendered_body_audit.py",
    "run294_note_eyecatch_persistence_diagnostics.py",
    "run295_note_private_draft_audit.py",
    "run296_editorial_format_v2.py",
    "run297_genrec_run296_rebase.py",
    "run298_existing_header_replace.py",
    "run298_genrec_inplace_refresh.py",
    "run298_header_readonly_diagnostics.py",
    "run298_hover_header_final.py",
    "run299_genrec_body_structure_diagnostic.py",
    "run300_genrec_final_body_repair.py",
    "run301_genrec_summary_restore.py",
    "run302_genrec_publication_reconcile.py",
    "run307_use_decision_product_guard.py",
    "run308_public_copy_alignment_guard.py",
    "run309_public_lp_editor_audit.py",
    "run310_public_lp_update.py",
    "run311_note_profile_update.py",
    "run313_public_lp_minimal_reconcile.py",
    "run328_note_profile_settings_probe.py",
    "run329_note_profile_direct_route_probe.py",
    "run330_note_profile_exact_update.py",
    "run346_backlog_budget_reserve.py",
    "run348_adversarial_editorial_lab.py",
    "run367_x_daily_discovery.py",
    "run374_ready_rescue.py",
    "run399_article_revalidation_apply.py",
    "run400_approved_reader_repair.py",
    "run406_approved_second_reader_repair.py",
    "run408_approved_quality_fallback.py",
    "run409_approved_reader_owner_bridge.py",
    "run411_fact_retry_specificity.py",
    "run412_approved_38_35_routing.py",
    "run417_note_body_verification.py",
    "run624_delivery_causality.py",
    "run_openai2015_current_eyecatch_resync.py",
    "run_openai2015_existing_draft_resync.py",
    "run_public_legacy_critical_repair.py",
    "run_sgps_existing_draft_repair.py",
    "run_vtcode_existing_draft_repair.py",
    "runtime_layers.py",
    "screening_protocol.py",
    "source_boundary_validation.py",
    "source_document_parsing.py",
    "source_normalization.py",
    "source_roi_policy.py",
    "source_stability_layer.py",
    "stale_ready_batch_revalidation.py",
    "stale_ready_retirement.py",
    "stale_ready_retirement_audit.py",
    "stale_ready_top_fast_path_preflight.py",
    "stale_ready_zero_api_portfolio_audit.py",
    "stock_lifecycle_reconcile.py",
    "subscription_attribution.py",
    "technology_portfolio_policy.py",
    "test_run360_gemini_retry_owner.py",
    "workflow_reference_guard.py",
))

MEMBER_MODULE_MARKERS = ("member", "membership", "onboard", "digest", "subscriber_decision_brief")

FORBIDDEN_PRIMARY_JARGON = (
    "Decision Score",
    "Step1",
    "Step2",
    "PROP_STATUS",
    "同期ID",
)
RAW_DECISION_CODES = ("ADOPT", "TEST", "WATCH", "AVOID")

HOME_CONTENT = """<callout icon="🧭" color="blue_bg">
	**迷ったら、ここからで大丈夫です。**
	新しいAIを全部追う必要はありません。**今月見るものをBriefで絞る → 気になったものだけDBで確かめる → 使う前に判断メモへ条件を書く。** 会員向けは、この3つで回します。
</callout>
## まずは、この3つだけ
### 1｜今月のDecision Brief
**今見るものだけを先に絞る入口です。** ニュースを並べるのではなく、「いま使う候補か」「まず試すか」「まだ待つか」を短く確認できます。

<mention-page url="https://app.notion.com/p/3d0479ffdca981deb614fef528d2f32c">今月のDecision Brief</mention-page>
### 2｜AI意思決定DB
気になるものが見つかったら、ここで詳しく確かめます。**向いている場面、注意点、まずやること、根拠にした情報**まで一か所で確認できます。

<mention-database url="https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f">AI・技術一覧｜判断DB</mention-database>
### 3｜判断メモ
実際に使う前に、目的・扱うデータ・成功条件・やめる条件を整理します。**「良さそう」で始めず、何を確かめれば次へ進めるかを決めるためのメモ**です。

<mention-page url="https://app.notion.com/p/3d3479ffdca98119b0d8c014b068fe82">AI活用 判断メモ</mention-page>
---
## やりたいことから探す
- **社内文書を探す・FAQや問い合わせ対応を楽にしたい** → [Dify](https://app.notion.com/p/3d0479ffdca981329f5de0043cd43a69) / [AnythingLLM](https://app.notion.com/p/3d0479ffdca981d29539c81d2d7c8a8f)
- **ブラウザで繰り返す作業を減らしたい** → [browser-use](https://app.notion.com/p/3d0479ffdca981b8b90ace2a3fb5b53c)
- **画像・動画制作の手順を再利用できる形にしたい** → [ComfyUI](https://app.notion.com/p/3d0479ffdca981bc9a22c2664163f577)
- **Web制作・開発工程をAIで短縮したい** → [Cline](https://app.notion.com/p/3d0479ffdca981c48839d980581324f5)
## 迷ったときの4つの目安
<table fit-page-width="true" header-row="true">
	<tr><td>いまの判断</td><td>どうする？</td></tr>
	<tr><td>条件が合えば使う候補</td><td>利用条件を確認して、導入候補へ</td></tr>
	<tr><td>まず小さく試す</td><td>本番に近い小さな条件で比べる</td></tr>
	<tr><td>いまは様子を見る</td><td>急がず、更新や代替案を確認する</td></tr>
	<tr><td>いまは選ばない</td><td>別の候補へ切り替える</td></tr>
</table>
<details>
<summary>もっと詳しく探したいとき</summary>
	- [まず見る3件](https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f?v=3d0479ffdca9813ea01f000cdbb2fd23)
	- [すべてから探す](https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f?v=3d0479ffdca98111a529000cba6d89b5)
	- [分野から探す](https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f?v=3d0479ffdca98187adb0000c59859508)
	- [スマホで見る](https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f?v=3d0479ffdca981a49d7b000c4ced31ab)
	- [これから注目したい新技術](https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f?v=3d0479ffdca981a885cb000cb0cd12c8)
</details>
---
## 判断が変わったものだけ確認したいとき
変化そのものより、**その変化で自分の使い方を変える必要があるか**を見ます。

[判断が大きく変わったものを見る](https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f?v=3d0479ffdca981ec92ef000c7a503fb6)
<callout icon="💡" color="gray_bg">
	大きな変化がなければ、無理に判断を変えません。**変わっていないことも、立派な判断材料です。**
</callout>
---
<callout icon="🧩" color="green_bg">
	候補が決まったら、判断メモに **目的・扱うデータ・注意点・最小検証・成功条件** を書いてから試します。
</callout>
<page url="https://app.notion.com/p/3d3479ffdca98119b0d8c014b068fe82">AI活用 判断メモ｜使う・試す・待つ・避ける</page>"""

JUDGMENT_MEMO_CONTENT = """<callout icon="🧩" color="blue_bg">
	**使うか迷ったら、AIの名前より先に条件を書きます。**
	このメモは「良さそう」を「何を確かめれば次へ進めるか」に変えるためのものです。全部埋める必要はありません。まず下の5つから始めてください。
</callout>
## まず書く5つ
1. **何を良くしたい？** — いま困っていること、減らしたい手間、改善したい仕事
2. **何を扱う？** — 公開情報 / 社内情報 / 個人情報 / 機密情報
3. **どこまでAIに任せる？** — 提案まで / 下書きまで / 実行まで。人が確認する場所も決める
4. **何ができれば成功？** — 時間、品質、費用、運用負荷など、いまの方法と比べるもの
5. **何が起きたらやめる？** — 情報管理、品質、費用、権限、運用で許容できない条件
## 最初の判断
<table fit-page-width="true" header-row="true">
	<tr><td>判断</td><td>次にすること</td></tr>
	<tr><td>条件が合えば使う候補</td><td>利用条件を確認し、本番候補として詰める</td></tr>
	<tr><td>まず小さく試す</td><td>本番に近い小さな条件で比較する</td></tr>
	<tr><td>いまは様子を見る</td><td>急がず、更新や代替案を追う</td></tr>
	<tr><td>いまは選ばない</td><td>別候補へ切り替える</td></tr>
</table>
<callout icon="⚠️" color="yellow_bg">
	**最初から全面導入しません。** 公開可能または低リスクなデータ、限定した操作、人が確認できる範囲から始めます。
</callout>
<details>
<summary>もう少し丁寧に整理したいとき</summary>
	1. **目的 / 利用シーン**
	2. **候補AI / 技術**
	3. **今回の判断**
	4. **この候補を選ぶ理由**
	5. **向かない条件**
	6. **主なリスク**
	7. **最小検証**
	8. **成功条件**
	9. **次に判断する日**
</details>
## DBとつなげる
目的と条件を書いたら、会員DBで候補の **向いている場面 / 注意点 / まずやること / 根拠にした情報** を確認します。

<mention-database url="https://app.notion.com/p/b2787ee05b584ca7b4eb774f60237f1f">AI・技術一覧｜判断DB</mention-database>

<callout icon="💡" color="gray_bg">
	DBの結論をそのまま採用するのではなく、**自分の条件に当てはめて、小さく試すか・待つか・見送るか**を決めてください。
</callout>"""

# User-facing view tabs intentionally hide operator-only score/sync metadata.
VIEW_CONTRACTS = {
    "02e4ebb2-b035-4ab5-9923-24eefd948c2f": {
        "name": "一覧｜すべて見る",
        "show": ("AI・技術名", "分野", "これは何？", "次にやること", "最終確認日"),
    },
    "3d0479ff-dca9-813e-a01f-000cdbb2fd23": {
        "name": "まず見る3件",
        "show": ("AI・技術名", "これは何？", "次にやること", "最終確認日"),
    },
    "3d0479ff-dca9-8112-a791-000c815a253f": {
        "name": "ほかのおすすめ",
        "show": ("AI・技術名", "これは何？", "次にやること", "最終確認日"),
    },
    "3d0479ff-dca9-8111-a529-000cba6d89b5": {
        "name": "すべてから探す",
        "show": ("AI・技術名", "分野", "これは何？", "次にやること", "最終確認日"),
    },
    "3d0479ff-dca9-8187-adb0-000c59859508": {
        "name": "分野から探す",
        "show": ("AI・技術名", "分野", "これは何？", "最終確認日"),
    },
    "3d0479ff-dca9-8138-8135-000c9c6a8585": {
        "name": "条件が合えば使う候補",
        "show": ("AI・技術名", "これは何？", "次にやること", "最終確認日"),
    },
    "3d0479ff-dca9-8160-b6fe-000c9865dd42": {
        "name": "まず小さく試したいもの",
        "show": ("AI・技術名", "これは何？", "次にやること", "最終確認日"),
    },
    "3d0479ff-dca9-8137-99c5-000c606813ca": {
        "name": "もう少し様子を見たいもの",
        "show": ("AI・技術名", "これは何？", "次にやること", "最終確認日"),
    },
    "3d0479ff-dca9-8193-8963-000ce71542be": {
        "name": "いまは選ばないもの",
        "show": ("AI・技術名", "これは何？", "主なリスク", "最終確認日"),
    },
    "3d0479ff-dca9-81d3-a24f-000c3aea5e41": {
        "name": "分野ごとに比べる",
        "show": ("AI・技術名", "これは何？", "分野"),
        "group_by": "分野",
    },
    "3d0479ff-dca9-818d-90a0-000c24860d55": {
        "name": "最近、判断材料が増えたもの",
        "show": ("AI・技術名", "評価が変わった理由", "次にやること", "最終確認日"),
    },
    "3d0479ff-dca9-81a8-85cb-000cb0cd12c8": {
        "name": "これから注目したい新技術",
        "show": ("AI・技術名", "これは何？", "今回の話題", "最終確認日"),
    },
    "3d0479ff-dca9-81ec-92ef-000c7a503fb6": {
        "name": "前と判断が大きく変わったもの",
        "show": ("AI・技術名", "評価が変わった理由", "次にやること", "重要変化日"),
    },
    "3d0479ff-dca9-81a4-9d7b-000c4ced31ab": {
        "name": "スマホで見る",
        "show": ("AI・技術名", "これは何？"),
    },
}

INTERNAL_VIEW_RENAMES = {
    "3d1479ff-dca9-8149-8334-000c097549f5": "運営用｜品質確認",
    "3d7479ff-dca9-8170-be98-000c475c0591": "運営用｜リスク情報の確認待ち",
}


def validate_repository(root: Path) -> list[str]:
    failures: list[str] = []
    if set(SURFACES) != set(REQUIRED_SURFACES):
        failures.append("member surface registry changed without updating REQUIRED_SURFACES")
    classified = CLASSIFIED_MEMBER_MODULES | NON_MEMBER_MODULES | set(CUSTOMER_ENTRYPOINTS)
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in {"tests", "archive", "archives", ".git", ".venv", "venv", "__pycache__"} for part in relative.parts):
            continue
        if relative.as_posix() not in classified:
            failures.append(f"unclassified member/customer module: {relative.as_posix()}")
    for owner, allowed in CUSTOMER_ENTRYPOINTS.items():
        path = root / owner
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError) as exc:
            failures.append(f"{owner}: cannot audit entrypoints: {exc}")
            continue
        declared = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in sorted(declared - allowed):
            failures.append(f"unclassified customer entrypoint: {owner}:{name}")
    for key, spec in SURFACES.items():
        for field in ("owner", "audit", "purpose"):
            if not str(spec.get(field) or "").strip():
                failures.append(f"{key}: missing {field}")
        for field in ("owner", "audit"):
            path = root / str(spec[field])
            if not path.is_file():
                failures.append(f"{key}: {field} does not exist: {spec[field]}")
    for label, copy in (("member_home", HOME_CONTENT), ("judgment_memo", JUDGMENT_MEMO_CONTENT)):
        for token in (*FORBIDDEN_PRIMARY_JARGON, *RAW_DECISION_CODES):
            if token in copy:
                failures.append(f"{label}: internal jargon leaked: {token}")
    internal_fields = {"判断スコア", "同期ID", "評価の変化", "分類", "情報源"}
    for view_id, spec in VIEW_CONTRACTS.items():
        leaked = internal_fields & set(spec["show"])
        if leaked:
            failures.append(f"view {view_id}: operator fields exposed: {sorted(leaked)}")
    return failures
