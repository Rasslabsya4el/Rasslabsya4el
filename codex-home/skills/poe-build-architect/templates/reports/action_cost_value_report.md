# Action Cost/Value Report

- Ledger ID: `{{ ledger_id }}`
- Status: `{{ status }}`
- Decision family: `{{ decision_family }}`
- Action scope: `{{ action_scope }}`
- Product-agent behavioral proof required: `{{ product_agent_behavioral_proof_required }}`

## Selected Action

- Action: `{{ selected_action.label }}` (`{{ selected_action.action_id }}`)
- Cost: `{{ selected_action.resource_cost_summary }}`
- Expected surfaces: `{{ selected_action.expected_surfaces[] }}`
- Evidence refs: `{{ selected_action.evidence_refs[] }}`
- Verdict reason: `{{ selected_action.verdict_reason }}`

## Rejected Alternatives

- Action: `{{ rejected_alternatives[].label }}` (`{{ rejected_alternatives[].action_id }}`)
- Cost: `{{ rejected_alternatives[].resource_cost_summary }}`
- Expected surfaces: `{{ rejected_alternatives[].expected_surfaces[] }}`
- Evidence refs: `{{ rejected_alternatives[].evidence_refs[] }}`
- Verdict reason: `{{ rejected_alternatives[].verdict_reason }}`

## Comparison Rows

| Verdict | Action | Cost | Expected surfaces | Evidence refs | Reason |
| --- | --- | --- | --- | --- | --- |
| `{{ comparison_rows[].verdict }}` | `{{ comparison_rows[].label }}` | `{{ comparison_rows[].resource_cost_summary }}` | `{{ comparison_rows[].expected_surfaces[] }}` | `{{ comparison_rows[].evidence_refs[] }}` | `{{ comparison_rows[].verdict_reason }}` |
