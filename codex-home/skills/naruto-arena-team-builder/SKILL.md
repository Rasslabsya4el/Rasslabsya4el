---
name: naruto-arena-team-builder
description: Use for Naruto Arena team building, mission planning, mission-pool optimization, team diagnosis, substitutions, weakness analysis, and mechanics explanations grounded only in the validated local skill reference bundle.
---

# Naruto Arena Team Builder

## When To Use This Skill

- Use this skill for Naruto Arena requests about building teams around a character, building for a mission, optimizing a mission pool, diagnosing an existing team, suggesting substitutions, or explaining mechanics.
- Use this skill only for the canonical game version backed by the local bundle in this directory.

## Required Reference Load Order

1. Read `references/rules.md` first and obey it as the runtime mechanics policy.
2. Load only the skill-local bundle files needed for the request:
   - `references/characters.json` and `references/tags.json` for character-centric team building and diagnosis.
   - `references/missions.json` for mission and mission-pool requests.
   - `references/effect-taxonomy.json` when effect buckets or role inference matter.
   - `references/source-map.json` whenever exact provenance, source URLs, or `source_ref_ids` need to be resolved.
   - `references/data-quality-report.md` before making narrow claims and whenever record-level uncertainty needs to be surfaced.
3. Treat `references/` in this skill directory as the only runtime mechanics source.

## Hard Runtime Boundaries

- Do not use model memory as a mechanics source.
- Do not use non-canonical Naruto Arena sites, mirrors, or mixed-version knowledge.
- Do not bypass the skill-local bundle by reading project-root `references/` or `data/normalized/` at runtime.
- Do not invent cooldowns, costs, classes, effects, mission objectives, unlocks, or hidden requirements when the bundle does not prove them.
- Do not use a static best-team database as product logic. Generate and compare candidates from the local data for each request.

## Grounding And Uncertainty Rules

- Treat mechanics in `characters.json`, `missions.json`, `tags.json`, `effect-taxonomy.json`, `source-map.json`, and `data-quality-report.md` as the only allowed evidence surface.
- Resolve `source_ref_ids` through `source-map.json` whenever the answer needs exact source URLs, source lineage, or record-level proof.
- Surface `data_quality_tag_ids`, confidence fields, ambiguity flags, and unknown mission requirements as meaningful uncertainty, not as ignorable metadata.
- Keep explicit unknown mission objectives unknown. Never fill them from guesswork.
- Distinguish confirmed mechanics from strategic inference in every substantial answer.
- If a claim is not supported by the local bundle, say that the data is missing or uncertain.

## Mission Progression Ceiling

- Mission and mission-pool requests are progression-scoped by default.
- When the user asks for a team for one mission or a mission pool, infer the roster ceiling from the highest resolved mission `rank_requirement`.
- Unless the user explicitly says they already own higher-rank characters or asks for future/aspirational planning, recommend only base or unlisted mission-reward characters plus mission-reward unlocks at or below that highest mission rank.
- Do not use later-rank mission rewards as filler, carry units, or substitutions for a lower-rank mission by default.
- If an explicit higher-rank override is used, say that the roster was widened and keep that separate from default progression-safe advice.
- If mission rank is unavailable or ambiguous, say the ceiling could not be proven and avoid silently opening the full late-rank roster.
- For helper-backed planning, use the derived `progression` surfaces from `search_characters.py`, `team_candidate_report.py`, and `optimize_mission_pool.py`; `optimize_mission_pool.py --include-higher-rank` is the explicit override path.

## Stable Request Classes

- Build a team around a character.
- Build a team for a mission.
- Optimize a pool of missions into the fewest practical teams.
- Diagnose or improve an existing team.
- Explain mechanics, roles, or character differences.

## Core Reasoning Flow

1. Resolve entities.
   - Match character names and mission names carefully.
   - If multiple matches are plausible, surface the ambiguity and continue conservatively.
2. Load the relevant records from the skill-local bundle.
   - Read character roles, skills, costs, cooldowns, tags, effect buckets, confidence, ambiguity markers, and `data_quality_tag_ids`.
   - For mission work, read requirements, rewards/unlocks, rank requirements, level gates, confidence, ambiguity markers, and unknown-objective flags.
3. Convert the request into planning constraints.
   - Identify the core role, win condition, support needs, chakra needs, setup/payoff needs, mission constraints, and stated user preferences.
   - For mission work, apply the mission progression ceiling before accepting candidate partners or substitutions.
4. Generate multiple candidate teams or plans internally before recommending a final answer.
5. Reject weak candidates.
   - Reject teams with no clear win condition.
   - Reject teams with unresolved hard mission conflicts.
   - Reject teams with severe chakra conflict and no payoff.
   - Reject teams that duplicate roles without solving the user goal.
   - Reject teams that are all setup and no closer.
6. Explain the selected recommendation honestly.
   - State why the team exists.
   - State what each character contributes.
   - State the opening plan at a practical level.
   - State weaknesses, bad matchups, failure modes, and substitutions.
   - State mission coverage or mission limits.
   - State confirmed mechanics separately from inference and surface data gaps.

## Request-Specific Workflow

### Build Around A Character

- Resolve the exact character/version before team building.
- Use the record's skills, tags, effect buckets, and chakra profile to identify the character's likely role.
- If "build around" is ambiguous, consider multiple valid interpretations instead of assuming one.
- Generate several candidate teams, then recommend the best fit for the stated goal.
- Explain why the core character matters in the team, not just who the two partners are.

### Build For A Mission

- Resolve the exact mission record before recommending a team.
- Infer the default roster ceiling from the resolved mission `rank_requirement` and keep candidate partners at or below that rank unless the user explicitly requests higher-rank planning.
- Treat mission requirements as hard constraints first, soft optimization goals second.
- If the mission contains unknown or low-confidence requirements, say that explicitly before claiming coverage.
- Recommend teams for consistency and mission completion honesty, not just raw power.

### Optimize A Mission Pool

- Resolve each mission first, then compare hard constraints, soft constraints, and unknown requirements across the pool.
- Infer the default roster ceiling from the highest resolved mission `rank_requirement` in the pool and apply it to every recommended team group unless the user explicitly requests higher-rank planning.
- Group missions into the fewest coherent teams only when the constraints are actually compatible.
- Split missions into separate teams when requirements conflict, when the same team becomes incoherent, or when unresolved unknowns make a combined claim unsafe.
- Explain what each recommended team covers and what remains separate.

### Diagnose Or Improve An Existing Team

- Resolve every character/version in the existing team.
- Build a team profile covering win condition, support/control/defense coverage, chakra curve, setup dependency, and obvious weak points.
- Identify the biggest failure mode before suggesting changes.
- Prefer a minimal fix first, then give a broader rebuild only if the original shell is structurally weak.

### Explain Mechanics

- Use bundle data as the only mechanics evidence.
- Resolve provenance through `source-map.json` when exact sourcing matters.
- Separate confirmed mechanics from strategic interpretation.
- If the bundle leaves a field ambiguous or low-confidence, name that gap directly.

## Minimum Answer Requirements For Team Advice

- Include candidate generation and rejection logic in the reasoning, even if the final answer only shows the best options.
- Include matchup or weakness analysis, not just synergy.
- Include failure modes and at least one substitution path when a team recommendation is made.
- Include mission/objective honesty. If a mission has unknown requirements, do not claim guaranteed coverage.
- Keep the response practical and grounded, but do not lock the skill into a final formatting template in this base task.

## Concrete Response Contract For MVP Request Classes

- These output rules extend the base runtime contract above. Do not weaken or replace the required load order, local-reference-only evidence surface, or anti-hallucination boundaries.
- Generic advice is insufficient. Whenever the skill recommends a team, change, or plan, it must include practical play pattern, weaknesses, and substitutions where relevant.
- Keep confirmed mechanics, strategic inference, and unknowns visibly separated. Do not bury uncertainty in a closing sentence.
- If the user asks for a short answer, compress wording but keep the required sections or their equivalent content.

### Build Around A Character

- The final answer must include these practical sections:
  - `Recommendation`: the final team and the main reason it was chosen over rejected candidates.
  - `Team Identity`: what the team is trying to do, including win condition, pacing, and role shell.
  - `Why These Characters Fit`: what each character contributes and why the trio is coherent.
  - `Game Plan`: how the team converts setup into pressure or closing turns.
  - `First Turns`: the likely opening sequence or priorities for the first turns.
  - `Good Matchups`: what kinds of teams or mission contexts this lineup punishes.
  - `Bad Matchups / What Beats This`: what pressures or counters make the lineup unstable.
  - `Failure Modes`: how the plan falls apart when draws, chakra, or setup do not line up.
  - `Mission Coverage`: whether the team is generally useful for missions or only for ladder-style play, plus any relevant limits.
  - `Substitutions`: at least one swap path and what changes when the swap is made.
  - `Confidence / Data Gaps`: what is confirmed by the bundle and what remains uncertain.
- Do not stop at naming two partners. The answer must explain why building around the named character actually works in play.

### Build For A Mission

- The final answer must include these practical sections:
  - `Mission Resolution`: confirm the exact mission record being answered, or state ambiguity before recommending anything.
  - `Requirement Summary`: list the proven mission requirements, important constraints, and any unknown objectives or low-confidence fields.
  - `Progression Scope`: state the inferred mission-rank ceiling, or state that it is unavailable; mention any explicit override if higher-rank planning was requested.
  - `Recommended Team`: the best-effort team for the resolved mission.
  - `Why This Covers The Mission`: explain how the team satisfies the known mission requirements and where the proof is incomplete.
  - `Play Plan`: how to pilot the team toward the mission instead of only describing raw team strength.
  - `Weaknesses / Failure Modes`: what can still go wrong even if the team matches the known requirements.
  - `Substitutions`: optional replacements if the mission allows flexibility.
  - `Confidence / Unknowns`: explicit honesty about unknown objectives, unresolved text, or low-confidence requirements.
- If the mission data is incomplete, say the recommendation is best-effort rather than pretending the mission is fully solved.

### Optimize A Mission Pool

- The final answer must include these practical sections:
  - `Mission Pool Resolution`: list the missions that were matched and flag any unresolved identity issues.
  - `Progression Scope`: state the highest resolved mission-rank ceiling for the pool, or state that it is unavailable; mention any explicit override if higher-rank planning was requested.
  - `Grouped Plan`: show the recommended teams or team groups, with each mission assigned to a group.
  - `Coverage Explanation`: explain why each group covers its assigned missions.
  - `Conflict Explanation`: explain why certain missions can share a team or why they must be split.
  - `Coverage Matrix`: provide an explicit matrix, table, or equivalent per-mission coverage surface showing team-to-mission mapping and any uncertainty.
  - `Play Priorities`: if there is an efficient order or progression path, say it.
  - `Confidence / Data Gaps`: note missions that remain uncertain, partially covered, or blocked by unknown requirements.
- A generic "Team X covers most of these" answer is not acceptable without an explicit coverage surface.

### Diagnose Or Improve An Existing Team

- The final answer must include these practical sections:
  - `Verdict`: whether the current team is coherent for the stated goal.
  - `Biggest Problem`: the main structural issue, not just a list of minor flaws.
  - `Minimal Fix`: the smallest change that meaningfully improves the team.
  - `Why The Fix Helps`: what role, curve, matchup, or mission issue the fix actually addresses.
  - `Broader Rebuild`: include this when the shell is too weak for a one-slot fix, and say why.
  - `Mission Fit`: if the request includes missions or progression goals, explain whether the current or revised team fits them.
  - `Confidence / Data Gaps`: separate proven mechanics from inference and flag uncertain records.
- If the team is already sound, say that directly and justify it instead of forcing a fake rebuild.

### Explain Mechanics, Roles, Or Character Differences

- The final answer must include these practical sections:
  - `Question Resolution`: restate the mechanic or comparison being answered.
  - `Confirmed From Data`: only facts supported by the local bundle.
  - `Strategic Inference`: what follows from the confirmed facts in actual play.
  - `Data Gaps / Unknowns`: what the bundle does not prove or leaves ambiguous.
  - `Source Resolution`: when provenance matters, point to the resolved local source references and URLs.
- Do not blur confirmed effects with interpretation. The user should be able to see exactly which part is data and which part is judgment.
