# AgentMemoryPromotionReview

- Schema version (`schema_version`): `{{ schema_version }}`
- Record kind (`record_kind`): `{{ record_kind }}`
- Review ID (`review_id`): `{{ review_id }}`
- Generated At (`generated_at`): `{{ generated_at }}`

## 1. Review Context

- Candidate ID (`review_context.candidate_id`): `{{ review_context.candidate_id }}`
- Candidate schema version (`review_context.candidate_schema_version`): `{{ review_context.candidate_schema_version }}`
- Source candidate ref (`review_context.source_candidate_ref`): `{{ review_context.source_candidate_ref }}`
- Review requested by task (`review_context.review_requested_by_task`): `{{ review_context.review_requested_by_task }}`
- Review surface version (`review_context.review_surface_version`): `{{ review_context.review_surface_version }}`
- Early Game closure status (`review_context.early_game_closure_status`): `{{ review_context.early_game_closure_status }}`

## 2. Candidate

- Candidate ID (`candidate.candidate_id`): `{{ candidate.candidate_id }}`
- Created by task (`candidate.created_by_task`): `{{ candidate.created_by_task }}`
- Promotion type (`candidate.promotion_type`): `{{ candidate.promotion_type }}`
- Summary (`candidate.summary`): `{{ candidate.summary }}`
- Scope (`candidate.scope`):
  - Scope kind (`candidate.scope.scope_kind`): `{{ candidate.scope.scope_kind }}`
  - Scope ID (`candidate.scope.scope_id`): `{{ candidate.scope.scope_id }}`
  - Applies to (`candidate.scope.applies_to[]`): `{{ candidate.scope.applies_to[] }}`
  - Exclusions (`candidate.scope.exclusions[]`): `{{ candidate.scope.exclusions[] }}`
  - Campaign boundary (`candidate.scope.campaign_boundary`): `{{ candidate.scope.campaign_boundary }}`

## 3. Provenance

- Source campaign refs (`provenance.source_campaign_refs[]`):
  - Campaign ID (`provenance.source_campaign_refs[].campaign_id`)
  - Ledger ref (`provenance.source_campaign_refs[].ledger_ref`)
  - Campaign scope (`provenance.source_campaign_refs[].campaign_scope`)
  - Evidence role (`provenance.source_campaign_refs[].evidence_role`)
- Source evidence refs (`provenance.source_evidence_refs[]`):
  - Source kind (`provenance.source_evidence_refs[].source_kind`)
  - Ref ID (`provenance.source_evidence_refs[].ref_id`)
  - Locator (`provenance.source_evidence_refs[].locator`)
  - Summary (`provenance.source_evidence_refs[].summary`)
  - Derived observation (`provenance.source_evidence_refs[].derived_observation`)
  - Captured at (`provenance.source_evidence_refs[].captured_at`)

## 4. Proposed Memory Target

- Target layer (`proposed_memory_target.target_layer`): `{{ proposed_memory_target.target_layer }}`
- Target path (`proposed_memory_target.target_path`): `{{ proposed_memory_target.target_path }}`
- Update kind (`proposed_memory_target.update_kind`): `{{ proposed_memory_target.update_kind }}`
- Target note (`proposed_memory_target.target_note`): `{{ proposed_memory_target.target_note }}`

## 5. Freshness

- Freshness class (`freshness.freshness_class`): `{{ freshness.freshness_class }}`
- Freshness note (`freshness.freshness_note`): `{{ freshness.freshness_note }}`
- Invalidation notes (`freshness.invalidation_notes[]`): `{{ freshness.invalidation_notes[] }}`
- Recheck triggers (`freshness.recheck_triggers[]`): `{{ freshness.recheck_triggers[] }}`

## 6. Guardrails

- Raw trace direct promotion (`guardrails.raw_trace_direct_promotion`): `{{ guardrails.raw_trace_direct_promotion }}`
- Baseline rare gear price parsing promotion (`guardrails.baseline_rare_gear_price_parsing_promotion`): `{{ guardrails.baseline_rare_gear_price_parsing_promotion }}`
- Source-copy as created-build proof (`guardrails.source_copy_as_created_build_proof`): `{{ guardrails.source_copy_as_created_build_proof }}`
- Campaign evidence as durable truth without review (`guardrails.campaign_evidence_as_durable_truth_without_review`): `{{ guardrails.campaign_evidence_as_durable_truth_without_review }}`
- Durable memory write performed (`guardrails.durable_memory_write_performed`): `{{ guardrails.durable_memory_write_performed }}`
- Build Layer promotion before Early Game closure (`guardrails.build_layer_promotion_before_early_game_closure`): `{{ guardrails.build_layer_promotion_before_early_game_closure }}`

## 7. Review Request

- Requested decision (`review_request.requested_decision`): `{{ review_request.requested_decision }}`
- Request reason (`review_request.request_reason`): `{{ review_request.request_reason }}`
- Requested by (`review_request.requested_by`): `{{ review_request.requested_by }}`
- Requested at (`review_request.requested_at`): `{{ review_request.requested_at }}`

## 8. Reviewer Decision

- Decision (`reviewer_decision.decision`): `{{ reviewer_decision.decision }}`
- Decision source (`reviewer_decision.decision_source`): `{{ reviewer_decision.decision_source }}`
- Reviewer ID (`reviewer_decision.reviewer_id`): `{{ reviewer_decision.reviewer_id }}`
- Decision ref (`reviewer_decision.decision_ref`): `{{ reviewer_decision.decision_ref }}`
- Decision reason (`reviewer_decision.decision_reason`): `{{ reviewer_decision.decision_reason }}`
- Decided at (`reviewer_decision.decided_at`): `{{ reviewer_decision.decided_at }}`
- Follow-up (`reviewer_decision.follow_up`):
  - Follow-up required (`reviewer_decision.follow_up.follow_up_required`): `{{ reviewer_decision.follow_up.follow_up_required }}`
  - Follow-up owner (`reviewer_decision.follow_up.follow_up_owner`): `{{ reviewer_decision.follow_up.follow_up_owner }}`
  - Follow-up target (`reviewer_decision.follow_up.follow_up_target`): `{{ reviewer_decision.follow_up.follow_up_target }}`
  - Follow-up items (`reviewer_decision.follow_up.follow_up_items[]`): `{{ reviewer_decision.follow_up.follow_up_items[] }}`
  - Defer until (`reviewer_decision.follow_up.defer_until`): `{{ reviewer_decision.follow_up.defer_until }}`

## 9. Durable Memory Boundary

- Review surface only (`durable_memory_boundary.review_surface_only`): `{{ durable_memory_boundary.review_surface_only }}`
- Changes durable memory (`durable_memory_boundary.changes_durable_memory`): `{{ durable_memory_boundary.changes_durable_memory }}`
- Follow-up write task required (`durable_memory_boundary.follow_up_write_task_required`): `{{ durable_memory_boundary.follow_up_write_task_required }}`
- Boundary note (`durable_memory_boundary.boundary_note`): `{{ durable_memory_boundary.boundary_note }}`
