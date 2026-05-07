# CandidateShortlist

- Schema version (`schema_version`): `{{ schema_version }}`
- Record kind (`record_kind`): `{{ record_kind }}`
- Shortlist ID (`shortlist_id`): `{{ shortlist_id }}`
- Generated At (`generated_at`): `{{ generated_at }}`

## 1. Request Context

- Request ID (`request_context.request_id`): `{{ request_context.request_id }}`
- Request generated at (`request_context.generated_at`): `{{ request_context.generated_at }}`
- League (`request_context.league`): `{{ request_context.league }}`
- Max budget chaos (`request_context.max_budget_chaos`): `{{ request_context.max_budget_chaos }}`
- Shortlist size (`request_context.shortlist_size`): `{{ request_context.shortlist_size }}`
- Max candidate count (`request_context.max_candidate_count`): `{{ request_context.max_candidate_count }}`
- Max variants per archetype (`request_context.max_variants_per_archetype`): `{{ request_context.max_variants_per_archetype }}`
- Required filters (`request_context.required_filters`):
  - Class names (`request_context.required_filters.class_names[]`)
  - Ascendancies (`request_context.required_filters.ascendancies[]`)
  - Main skills (`request_context.required_filters.main_skills[]`)
  - Archetypes (`request_context.required_filters.archetypes[]`)
  - Unique items (`request_context.required_filters.unique_items[]`)
- Preferred filters (`request_context.preferred_filters`):
  - Class names (`request_context.preferred_filters.class_names[]`)
  - Ascendancies (`request_context.preferred_filters.ascendancies[]`)
  - Main skills (`request_context.preferred_filters.main_skills[]`)
  - Archetypes (`request_context.preferred_filters.archetypes[]`)
  - Unique items (`request_context.preferred_filters.unique_items[]`)
  - Tags (`request_context.preferred_filters.tags[]`)
- Bans (`request_context.bans`):
  - Candidate IDs (`request_context.bans.candidate_ids[]`)
  - Archetype keys (`request_context.bans.archetype_keys[]`)
  - Tags (`request_context.bans.tags[]`)
- Request notes (`request_context.request_notes[]`): `{{ request_context.request_notes[] }}`

## 2. Intake Summary

- Source candidate count (`intake_summary.source_candidate_count`): `{{ intake_summary.source_candidate_count }}`
- Accepted candidate count (`intake_summary.accepted_candidate_count`): `{{ intake_summary.accepted_candidate_count }}`
- Ranked candidate count (`intake_summary.ranked_candidate_count`): `{{ intake_summary.ranked_candidate_count }}`
- Shortlist candidate count (`intake_summary.shortlist_candidate_count`): `{{ intake_summary.shortlist_candidate_count }}`
- Constraint rejected count (`intake_summary.constraint_rejected_count`): `{{ intake_summary.constraint_rejected_count }}`
- Scoring rejected count (`intake_summary.scoring_rejected_count`): `{{ intake_summary.scoring_rejected_count }}`
- Archetype capped count (`intake_summary.archetype_capped_count`): `{{ intake_summary.archetype_capped_count }}`

## 3. Intake Trace

- Trace items (`intake_trace[]`):
  - Candidate ID (`intake_trace[].candidate_id`)
  - Build label (`intake_trace[].build_label`)
  - Archetype key (`intake_trace[].archetype_key`)
  - Archetype label (`intake_trace[].archetype_label`)
  - Status (`intake_trace[].status`)
  - Matched preferences (`intake_trace[].matched_preferences[]`)
  - Reasons (`intake_trace[].reasons[]`)
  - Reason code (`intake_trace[].reasons[].code`)
  - Reason summary (`intake_trace[].reasons[].summary`)
  - Reason details (`intake_trace[].reasons[].details`)
  - Supporting artifact refs (`intake_trace[].supporting_artifact_refs[]`)
  - Total cost chaos (`intake_trace[].total_cost_chaos`)
  - League (`intake_trace[].league`)

## 4. Ranked Shortlist

- Ranked items (`ranked_shortlist[]`):
  - Candidate ID (`ranked_shortlist[].candidate_id`)
  - Build label (`ranked_shortlist[].build_label`)
  - Archetype key (`ranked_shortlist[].archetype_key`)
  - Archetype label (`ranked_shortlist[].archetype_label`)
  - Status (`ranked_shortlist[].status`)
  - Rank (`ranked_shortlist[].rank`)
  - Overall score (`ranked_shortlist[].overall_score`)
  - Component scores (`ranked_shortlist[].component_scores[]`)
  - Component id (`ranked_shortlist[].component_scores[].component_id`)
  - Component label (`ranked_shortlist[].component_scores[].label`)
  - Component weight (`ranked_shortlist[].component_scores[].weight`)
  - Component raw score (`ranked_shortlist[].component_scores[].raw_score`)
  - Component weighted score (`ranked_shortlist[].component_scores[].weighted_score`)
  - Component details (`ranked_shortlist[].component_scores[].details`)
  - Penalties (`ranked_shortlist[].penalties[]`)
  - Penalty code (`ranked_shortlist[].penalties[].code`)
  - Penalty summary (`ranked_shortlist[].penalties[].summary`)
  - Penalty points (`ranked_shortlist[].penalties[].points`)
  - Penalty details (`ranked_shortlist[].penalties[].details`)
  - Failed gate (`ranked_shortlist[].failed_gate`)
  - Rejection reasons (`ranked_shortlist[].rejection_reasons[]`)
  - Baseline summary (`ranked_shortlist[].baseline_summary`)
  - Conditional summary (`ranked_shortlist[].conditional_summary`)
  - Budget summary (`ranked_shortlist[].budget_summary`)
  - Risks (`ranked_shortlist[].risks[]`)
  - Assumptions (`ranked_shortlist[].assumptions[]`)
  - Why this ranked here (`ranked_shortlist[].why_this_ranked_here[]`)
  - Gate trace (`ranked_shortlist[].gate_trace[]`)
  - Gate id (`ranked_shortlist[].gate_trace[].gate_id`)
  - Gate passed (`ranked_shortlist[].gate_trace[].passed`)
  - Gate summary (`ranked_shortlist[].gate_trace[].summary`)
  - Gate details (`ranked_shortlist[].gate_trace[].details`)
  - Required unique items (`ranked_shortlist[].required_unique_items[]`)
  - Tags (`ranked_shortlist[].tags[]`)
  - Matched preferences (`ranked_shortlist[].matched_preferences[]`)
  - Supporting artifact refs (`ranked_shortlist[].supporting_artifact_refs[]`)

## 5. Reserve Candidates

- Reserve items (`reserve_candidates[]`) reuse the same ordered candidate surface as `ranked_shortlist[]`.

## 6. Rejected Candidates

- Rejected items (`rejected_candidates[]`):
  - Candidate ID (`rejected_candidates[].candidate_id`)
  - Build label (`rejected_candidates[].build_label`)
  - Archetype key (`rejected_candidates[].archetype_key`)
  - Archetype label (`rejected_candidates[].archetype_label`)
  - Status (`rejected_candidates[].status`)
  - Rejection stage (`rejected_candidates[].rejection_stage`)
  - Rejection reasons (`rejected_candidates[].rejection_reasons[]`)
  - Matched preferences (`rejected_candidates[].matched_preferences[]`)
  - Supporting artifact refs (`rejected_candidates[].supporting_artifact_refs[]`)
  - Overall score (`rejected_candidates[].overall_score`)
  - Component scores (`rejected_candidates[].component_scores[]`)
  - Penalties (`rejected_candidates[].penalties[]`)
  - Failed gate (`rejected_candidates[].failed_gate`)
  - Baseline summary (`rejected_candidates[].baseline_summary`)
  - Conditional summary (`rejected_candidates[].conditional_summary`)
  - Budget summary (`rejected_candidates[].budget_summary`)
  - Risks (`rejected_candidates[].risks[]`)
  - Assumptions (`rejected_candidates[].assumptions[]`)
  - Why this ranked here (`rejected_candidates[].why_this_ranked_here[]`)
  - Gate trace (`rejected_candidates[].gate_trace[]`)
  - Constraint-stage candidates may leave `baseline_summary` and `conditional_summary` as `null`

## 7. Supporting Artifacts

- Supporting artifacts (`supporting_artifacts[]`):
  - Artifact kind (`supporting_artifacts[].artifact_kind`)
  - Artifact ID (`supporting_artifacts[].artifact_id`)
  - Label (`supporting_artifacts[].label`)
  - Locator (`supporting_artifacts[].locator`)

## 8. Assumptions

- Assumptions (`assumptions[]`): `{{ assumptions[] }}`

## 9. Risks

- Risks (`risks[]`): `{{ risks[] }}`
