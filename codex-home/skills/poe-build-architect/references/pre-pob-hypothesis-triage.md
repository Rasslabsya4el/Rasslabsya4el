# Pre-PoB Hypothesis Triage

Status: skill-owned runtime triage contract.

Pre-PoB Hypothesis Triage is the bounded static check before a product agent
spends PoB/materializer budget. It is not an optimizer, universal scorer,
passive tree solver, route generator, PoB run, or Direct Build proof.

## Required Protocol

Before material measurement, the agent must author 2-3 candidate hypotheses and
classify them as:

- selected for measurement;
- rejected before PoB;
- blocked by missing or unsupported evidence.

Every candidate hypothesis must record:

- candidate action;
- expected surfaces;
- estimated resource cost;
- expected value summary;
- risk flags;
- missing evidence;
- unsupported claims when present;
- reason;
- why the selected hypothesis is worth PoB cost.

## MVP Rules

- Fewer than two candidate hypotheses blocks triage.
- Every hypothesis requires `expected_surfaces`.
- Every hypothesis requires `estimated_resource_cost`.
- Unsupported claims cannot be selected for measurement.
- Unsupported claims must be rejected before PoB or blocked.
- If all hypotheses are missing critical evidence, triage is blocked or
  partial, never `measure`.
- A selected hypothesis must explain why it is worth PoB/materializer cost.

## Relationship To CV1-CV4

CV5 happens before a material action:

1. CV5 triages authored hypotheses before PoB.
2. CV4 Comparison Protocol compares candidate actions before material action.
3. CV1 Action Cost/Value Ledger records resource cost, alternatives, evidence
   refs, value summary, and verdict.
4. CV2 Calc Snapshot Diff records measured before/after deltas after PoB.
5. CV3 Pathing Opportunity Cost prices tree/pathing travel tax and value per
   point when the decision family is `direct_build.tree_pathing`.

CV5 does not replace those records. It decides whether a hypothesis is worth
spending measurement budget, should be rejected statically, or is blocked until
evidence exists.

## Observability

Normal Mode should emit compact triage status plus artifact refs when triage is
part of the decision flow. Debug Mode should include a full Pre-PoB Hypothesis
Packet when triage fails, a high-cost action is selected, evidence is missing,
or the orchestrator explicitly requests debug packets.

The full triage packet is an internal artifact by default. It is not a
user-facing prose report.

## Utility

Use the skill-owned Python utility:

```text
python -m poe_build_research.pob.pre_pob_hypothesis_triage example --output-dir <dir>
python -m poe_build_research.pob.pre_pob_hypothesis_triage produce --input <triage.json> --output-dir <dir>
```

The utility writes:

- `pre-pob-hypothesis-triage.json`;
- `pre-pob-hypothesis-triage-validation.json`.

The utility validates triage artifacts only. It does not mutate PoB, author a
build, run materializer/verifier, or spawn product agents.
