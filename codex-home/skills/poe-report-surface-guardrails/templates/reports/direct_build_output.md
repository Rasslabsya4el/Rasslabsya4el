# DirectBuildOutput

- Schema version (`schema_version`): `{{ schema_version }}`
- Record kind (`record_kind`): `{{ record_kind }}`
- Assembly ID (`assembly_id`): `{{ assembly_id }}`
- Generated At (`generated_at`): `{{ generated_at }}`

## 1. Source Context

- Entry kind (`source_context.entry_kind`): `{{ source_context.entry_kind }}`
- Request summary (`source_context.request_summary`): `{{ source_context.request_summary }}`
- Brief ref (`source_context.brief_ref`):
  - Brief ID (`source_context.brief_ref.brief_id`)
  - Label (`source_context.brief_ref.label`)
  - Locator (`source_context.brief_ref.locator`)
- Accepted candidate ref (`source_context.accepted_candidate_ref`):
  - Shortlist ID (`source_context.accepted_candidate_ref.shortlist_id`)
  - Candidate ID (`source_context.accepted_candidate_ref.candidate_id`)
  - Candidate label (`source_context.accepted_candidate_ref.candidate_label`)
  - Locator (`source_context.accepted_candidate_ref.locator`)

## 2. Artifact Locator

- Artifact ID (`artifact_locator.artifact_id`): `{{ artifact_locator.artifact_id }}`
- Artifact kind (`artifact_locator.artifact_kind`): `{{ artifact_locator.artifact_kind }}`
- Locator (`artifact_locator.locator`): `{{ artifact_locator.locator }}`
- Workspace locator (`artifact_locator.workspace_locator`): `{{ artifact_locator.workspace_locator }}`
- Handoff locator (`artifact_locator.handoff_locator`): `{{ artifact_locator.handoff_locator }}`

## 3. Proof Refs

- PoB run ID (`proof_refs.pob_run_id`): `{{ proof_refs.pob_run_id }}`
- Primary proof kind (`proof_refs.primary_proof_kind`): `{{ proof_refs.primary_proof_kind }}`
- Primary proof locator (`proof_refs.primary_proof_locator`): `{{ proof_refs.primary_proof_locator }}`
- Live control result locator (`proof_refs.live_control_result_locator`): `{{ proof_refs.live_control_result_locator }}`
- Workspace manifest locator (`proof_refs.workspace_manifest_locator`): `{{ proof_refs.workspace_manifest_locator }}`
- Next run handoff locator (`proof_refs.next_run_handoff_locator`): `{{ proof_refs.next_run_handoff_locator }}`
- Import code verifier status (`proof_refs.import_code_verifier_status`): `{{ proof_refs.import_code_verifier_status }}`
- Import code verifier locator (`proof_refs.import_code_verifier_locator`): `{{ proof_refs.import_code_verifier_locator }}`
- Import code verifier payload SHA-256 (`proof_refs.import_code_verifier_payload_sha256`): `{{ proof_refs.import_code_verifier_payload_sha256 }}`
- Semantic validation status (`proof_refs.semantic_validation_status`): `{{ proof_refs.semantic_validation_status }}`
- Semantic validation locator (`proof_refs.semantic_validation_locator`): `{{ proof_refs.semantic_validation_locator }}`
- Semantic validation mode (`proof_refs.semantic_validation_mode`): `{{ proof_refs.semantic_validation_mode }}`

## 4. Composition Summary

- Build label (`composition_summary.build_label`): `{{ composition_summary.build_label }}`
- Class name (`composition_summary.class_name`): `{{ composition_summary.class_name }}`
- Ascendancy (`composition_summary.ascendancy`): `{{ composition_summary.ascendancy }}`
- Main skill (`composition_summary.main_skill`): `{{ composition_summary.main_skill }}`
- Ready PoB import (`composition_summary.ready_pob_import`):
  - Surface kind (`composition_summary.ready_pob_import.surface_kind`)
  - Locator (`composition_summary.ready_pob_import.locator`)
  - Payload (`composition_summary.ready_pob_import.payload`)
- Tree summary (`composition_summary.tree_summary`):
  - Summary (`composition_summary.tree_summary.summary`)
  - Keystones (`composition_summary.tree_summary.keystones[]`)
  - Mastery focus (`composition_summary.tree_summary.mastery_focus[]`)
- Gem links (`composition_summary.gem_links[]`):
  - Group label (`composition_summary.gem_links[].group_label`)
  - Primary gem (`composition_summary.gem_links[].primary_gem`)
  - Support gems (`composition_summary.gem_links[].support_gems[]`)
  - Notes (`composition_summary.gem_links[].notes`)
- Item shell (`composition_summary.item_shell[]`):
  - Slot (`composition_summary.item_shell[].slot`)
  - Label (`composition_summary.item_shell[].label`)
  - Rarity expectation (`composition_summary.item_shell[].rarity_expectation`)
  - Source note (`composition_summary.item_shell[].source_note`)
- Config summary (`composition_summary.config_summary`):
  - Baseline guards (`composition_summary.config_summary.baseline_guards[]`)
  - Conditional enables (`composition_summary.config_summary.conditional_enables[]`)
  - Notes (`composition_summary.config_summary.notes[]`)

## 5. Budget Shell

- League (`budget_shell.league`): `{{ budget_shell.league }}`
- Currency basis (`budget_shell.currency_basis`): `{{ budget_shell.currency_basis }}`
- Budget cap chaos (`budget_shell.budget_cap_chaos`): `{{ budget_shell.budget_cap_chaos }}`
- Estimated total chaos (`budget_shell.estimated_total_chaos`): `{{ budget_shell.estimated_total_chaos }}`
- Mandatory total chaos (`budget_shell.mandatory_total_chaos`): `{{ budget_shell.mandatory_total_chaos }}`
- Optional total chaos (`budget_shell.optional_total_chaos`): `{{ budget_shell.optional_total_chaos }}`
- Headroom chaos (`budget_shell.headroom_chaos`): `{{ budget_shell.headroom_chaos }}`
- Budget status (`budget_shell.budget_status`): `{{ budget_shell.budget_status }}`
- Price basis note (`budget_shell.price_basis_note`): `{{ budget_shell.price_basis_note }}`
- Budget line items (`budget_shell.line_items[]`):
  - Slot (`budget_shell.line_items[].slot`)
  - Label (`budget_shell.line_items[].label`)
  - Amount chaos (`budget_shell.line_items[].amount_chaos`)
  - Mandatory (`budget_shell.line_items[].mandatory`)
  - Source kind (`budget_shell.line_items[].source_kind`)
  - Source ref (`budget_shell.line_items[].source_ref`)
  - Note (`budget_shell.line_items[].note`)

## 6. Baseline State

- Summary (`baseline_state.summary`): `{{ baseline_state.summary }}`
- Metric rows (`baseline_state.metric_rows[]`):
  - Metric key (`baseline_state.metric_rows[].metric_key`)
  - Label (`baseline_state.metric_rows[].label`)
  - Value (`baseline_state.metric_rows[].value`)
  - Unit (`baseline_state.metric_rows[].unit`)
  - Note (`baseline_state.metric_rows[].note`)
- Scope notes (`baseline_state.scope_notes[]`): `{{ baseline_state.scope_notes[] }}`

## 7. Conditional State

- Summary (`conditional_state.summary`): `{{ conditional_state.summary }}`
- Metric rows (`conditional_state.metric_rows[]`):
  - Metric key (`conditional_state.metric_rows[].metric_key`)
  - Label (`conditional_state.metric_rows[].label`)
  - Value (`conditional_state.metric_rows[].value`)
  - Unit (`conditional_state.metric_rows[].unit`)
  - Note (`conditional_state.metric_rows[].note`)
- Scope notes (`conditional_state.scope_notes[]`): `{{ conditional_state.scope_notes[] }}`

## 8. Assumptions

- Items (`assumptions[]`):
  - Category (`assumptions[].category`)
  - Statement (`assumptions[].statement`)
  - Impact on output (`assumptions[].impact_on_output`)

## 9. Blockers

- Items (`blockers[]`):
  - Severity (`blockers[].severity`)
  - Blocker kind (`blockers[].blocker_kind`)
  - Summary (`blockers[].summary`)
  - Unblock condition (`blockers[].unblock_condition`)

## 10. Freshness Notes

- Items (`freshness_notes[]`):
  - Surface kind (`freshness_notes[].surface_kind`)
  - Status (`freshness_notes[].status`)
  - Note (`freshness_notes[].note`)
  - Captured at (`freshness_notes[].captured_at`)
