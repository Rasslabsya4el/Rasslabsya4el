# BuildReview Runtime Operation Contract

Status: skill-owned runtime rule.

This file is the concrete operating protocol for reviewing one existing
PoB-backed build. It must stay packaged inside the installed skill.

## Scope Boundary

BuildReview improves or diagnoses an existing build. It must not turn into a
full archetype rebuild unless the user explicitly asks for that different mode.

Use only this skill bundle, sibling installed PoE skills, the submitted PoB, and
explicit external evidence providers. Do not read the development repo as
runtime memory.

## Required Review Loop

1. Intake:
   record the user goal, target league/economy, budget, max invasiveness, and
   output boundary.
2. Inspect:
   import/read the current PoB state before changing anything. Keep baseline and
   conditional lanes separate.
3. Bottleneck map:
   identify the weakest DPS, defense, resource, attribute, accuracy,
   reservation, mana, cost, and QoL surfaces that the review is allowed to touch.
4. Hypotheses:
   propose bounded fixes with alternatives considered, expected upside, risks,
   resource cost, and stop condition.
5. Trials:
   test fixes on copies of the build. Record before/after PoB metrics, Calc
   deltas or precise unavailable reason, rejected alternatives, and blockers.
6. Ranking:
   rank fixes by measured gain, resource cost, risk, invasiveness, and whether a
   hard constraint was repaired or broken.
7. Report:
   publish only the accepted BuildReview surface with trial/evidence refs.

## Invasiveness Scale

- 0: config/read-back fix.
- 1: gem or support swap.
- 2: small passive tree respec.
- 3: same-slot item replacement.
- 4: multi-slot rebalance.
- 5: archetype change.

Bounded review defaults to max invasiveness 3. Higher levels require explicit
user approval or a mode switch.

## Minimum Proof Bar

- No accepted fix without before/after PoB metrics.
- No material recommendation without resource cost.
- No tree recommendation without package cost.
- No accepted action without alternatives considered.
- No final review without rejected/blocked findings recorded.
- Default trial budget is at least 20 real trials unless the operator explicitly
  approves a smaller budget or a precise runtime blocker prevents it.

## Stop Conditions

Valid stop conditions:

- trial budget exhausted;
- no safe bounded action remains;
- missing PoB/runtime dependency is proven;
- user budget/max invasiveness is insufficient for every remaining repair;
- accepted BuildReview report has the required proof refs.

Invalid stop conditions:

- one mutation failed;
- first plausible fix improved headline DPS;
- the review can be explained as prose;
- a full rebuild would be easier than bounded review.
