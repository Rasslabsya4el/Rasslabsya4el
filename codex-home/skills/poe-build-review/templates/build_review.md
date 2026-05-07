# BuildReview

- Schema version (`schema_version`): `{{ schema_version }}`
- Record kind (`record_kind`): `{{ record_kind }}`
- Review ID (`review_id`): `{{ review_id }}`
- Generated At (`generated_at`): `{{ generated_at }}`

## 1. Build Summary

- Review status (`build_summary.review_status`): `{{ build_summary.review_status }}`
- Baseline verdict (`build_summary.baseline_verdict`): `{{ build_summary.baseline_verdict }}`
- Build label (`build_summary.build_label`): `{{ build_summary.build_label }}`
- Build ID (`build_summary.build_id`): `{{ build_summary.build_id }}`
- Build source (`build_summary.build_source`): `{{ build_summary.build_source }}`
- PoB run (`build_summary.pob_run_id`): `{{ build_summary.pob_run_id }}`
- Archetype (`build_summary.archetype_label`): `{{ build_summary.archetype_label }}`
- Headline (`build_summary.headline`): `{{ build_summary.headline }}`
- Recommendation summary (`build_summary.recommendation_summary`): `{{ build_summary.recommendation_summary }}`

## 2. Baseline Metrics

- Summary (`baseline_metrics.summary`): `{{ baseline_metrics.summary }}`
- Scope notes (`baseline_metrics.scope_notes[]`): `{{ baseline_metrics.scope_notes[] }}`
- Metric rows (`baseline_metrics.metric_rows[]`):
  - Label (`baseline_metrics.metric_rows[].label`)
  - Metric key (`baseline_metrics.metric_rows[].metric_key`)
  - Value (`baseline_metrics.metric_rows[].value`)
  - Unit (`baseline_metrics.metric_rows[].unit`)
  - Note (`baseline_metrics.metric_rows[].note`)

## 3. Conditional Metrics

- Summary (`conditional_metrics.summary`): `{{ conditional_metrics.summary }}`
- Scope notes (`conditional_metrics.scope_notes[]`): `{{ conditional_metrics.scope_notes[] }}`
- Metric rows (`conditional_metrics.metric_rows[]`):
  - Label (`conditional_metrics.metric_rows[].label`)
  - Metric key (`conditional_metrics.metric_rows[].metric_key`)
  - Value (`conditional_metrics.metric_rows[].value`)
  - Unit (`conditional_metrics.metric_rows[].unit`)
  - Note (`conditional_metrics.metric_rows[].note`)

## 4. Bottlenecks

## Proof Summary

- Proof status (`proof_summary.proof_status`): `{{ proof_summary.proof_status }}`
- Trial budget (`proof_summary.trial_budget`): `{{ proof_summary.trial_budget }}`
- Trials run (`proof_summary.trials_run`): `{{ proof_summary.trials_run }}`
- Accepted fix count (`proof_summary.accepted_fix_count`): `{{ proof_summary.accepted_fix_count }}`
- Ledger refs (`proof_summary.ledger_refs[]`): `{{ proof_summary.ledger_refs[] }}`
- Blockers (`proof_summary.blockers[]`):
  - Code (`proof_summary.blockers[].code`)
  - Summary (`proof_summary.blockers[].summary`)

- Ordered items (`bottlenecks[]`):
  - Priority (`bottlenecks[].priority`)
  - Category (`bottlenecks[].category`)
  - Severity (`bottlenecks[].severity`)
  - Title (`bottlenecks[].title`)
  - Summary (`bottlenecks[].summary`)
  - Evidence (`bottlenecks[].evidence[]`)
  - Affected area (`bottlenecks[].affected_area`)

## 5. Cheap Upgrades

- Ordered items (`cheap_upgrades[]`):
  - Priority (`cheap_upgrades[].priority`)
  - Upgrade kind (`cheap_upgrades[].upgrade_kind`)
  - Target slot (`cheap_upgrades[].target_slot`)
  - Title (`cheap_upgrades[].title`)
  - Summary (`cheap_upgrades[].summary`)
  - Expected benefit (`cheap_upgrades[].expected_benefit`)
  - Estimated cost note (`cheap_upgrades[].estimated_cost_note`)
  - Proof status (`cheap_upgrades[].proof_status`)
  - Invasiveness (`cheap_upgrades[].invasiveness`)
  - Resource cost (`cheap_upgrades[].resource_cost[]`)
  - Alternatives considered (`cheap_upgrades[].alternatives_considered[]`)
  - Trial refs (`cheap_upgrades[].trial_refs[]`)
  - Before/after metric refs (`cheap_upgrades[].before_after_metric_refs[]`)
  - Trade link bundle refs (`cheap_upgrades[].trade_link_bundle_refs[]`)
  - Trade link bundle id (`cheap_upgrades[].trade_link_bundle_refs[].bundle_id`)
  - Trade link bundle kind (`cheap_upgrades[].trade_link_bundle_refs[].bundle_kind`)
  - Trade link label (`cheap_upgrades[].trade_link_bundle_refs[].label`)
  - Trade link URL (`cheap_upgrades[].trade_link_bundle_refs[].resolved_search_url`)

## 6. Risks And Weak Points

- Items (`risks_and_weak_points[]`):
  - Severity (`risks_and_weak_points[].severity`)
  - Source area (`risks_and_weak_points[].source_area`)
  - Title (`risks_and_weak_points[].title`)
  - Summary (`risks_and_weak_points[].summary`)
  - Mitigation note (`risks_and_weak_points[].mitigation_note`)

## 7. Assumptions And Caveats

- Items (`assumptions_and_caveats[]`):
  - Category (`assumptions_and_caveats[].category`)
  - Statement (`assumptions_and_caveats[].statement`)
  - Impact on review (`assumptions_and_caveats[].impact_on_review`)

## 8. Next Actions

- Ordered items (`next_actions[]`):
  - Step (`next_actions[].step`)
  - Action (`next_actions[].action`)
  - Rationale (`next_actions[].rationale`)
  - Expected outcome (`next_actions[].expected_outcome`)
  - Trade link bundle refs (`next_actions[].trade_link_bundle_refs[]`)
  - Trade link bundle id (`next_actions[].trade_link_bundle_refs[].bundle_id`)
  - Trade link bundle kind (`next_actions[].trade_link_bundle_refs[].bundle_kind`)
  - Trade link label (`next_actions[].trade_link_bundle_refs[].label`)
  - Trade link URL (`next_actions[].trade_link_bundle_refs[].resolved_search_url`)
