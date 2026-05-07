# Data Quality Report

## Bundle Summary

- Generated at: `2026-04-25T14:43:02Z`
- Bundle version: `skill-reference-bundle-v1`
- Playable character records: 196
- Mission records: 179
- Excluded disabled zero-skill raw characters: 2
- Explicit unknown mission objective records: 118

## Character Bundle Scope

- The playable character bundle is intentionally narrower than the raw roster when the canonical source exposes disabled zero-skill stubs.
- Accepted exclusions: Edo Tensei Itachi (S), Shinobi Alliance Kakashi (S).
- Accepted raw-versus-playable counts: raw=198, playable=196.

## Mission Objective Uncertainty

- `118` mission records retain explicit `unknown` requirements because the accepted source evidence does not reveal objective text.
- Accepted raw-detail evidence breakdown:
  - redirect payloads: 71
  - error-page payloads: 46
  - unexpected-home payloads: 1

## Record-Level Data Quality Tags

- `character.data.effect_target_unknown`: 190 character records
- `character.data.effect_type_heuristic`: 145 character records
- `character.data.effect_magnitude_unknown`: 74 character records
- `character.data.effect_fallback_unknown`: 28 character records
- `mission.data.objective_text_missing`: 118 mission records
- `mission.data.detail_payload_redirect`: 71 mission records
- `mission.data.detail_payload_error_page`: 46 mission records
- `mission.data.detail_payload_unexpected_home`: 1 mission records
- `mission.data.character_group_not_modeled`: 13 mission records
- `mission.data.multi_character_condition_not_structured`: 11 mission records
- `mission.data.character_subject_not_resolved`: 3 mission records
- `mission.data.skill_reference_not_resolved`: 1 mission records

## Taxonomy Guardrails

- The accepted taxonomy is intentionally conservative. Downstream skill logic must not collapse broad parser buckets into narrower claimed mechanics.
- `protect`: This bucket is broader than invulnerability alone; inspect raw text when exact protection semantics matter.
- `apply_state`: This bucket is intentionally broad and should not be mistaken for a single canonical mechanic family.
- `remove_state`: Do not assume every remove_state entry is chakra denial; check evidence when exact removal type matters.
- `gain`: This bucket may mix direct resource gain with other beneficial gain text; keep the tag broad.
- `drain`: Some drain entries describe setup or replacement text instead of already-resolved drain output.

## Build Inputs

- `data\normalized\characters.json` (`sha256=882c2b2f2661f4dc20e3f8abe7eb1478b866b1cdfa4d74ae5a32bb982bfc59b2`)
- `data\normalized\missions.json` (`sha256=762bbc7d969b9a6e8da178f9aad4b55e807bf74fb77d608ce26a27afac8fa384`)
- `references\tags.json` (`sha256=803821eca4ce2eae9dc75f0cd6aaae31c92664eb01a674fb1e734016b943558e`)
- `references\effect-taxonomy.json` (`sha256=11ae790cc8b357a5867a8598d56494c6b903f4a2dfed96b85a0c7877be999966`)
- `.orchestrator\tasks\TASK-EXTRACT-CHARACTERS-VALIDATE-01\RESULT.txt` (`sha256=f87da2f40b9df416cc68f48149574fd7c9bf27214f5f9fa52ebafaf46479a460`)
- `.orchestrator\tasks\TASK-EXTRACT-MISSIONS-VALIDATE-01\RESULT.txt` (`sha256=982aba9bb0a8ba99d41c99d499eb4db3d92754b4930dacf769bc1c50d408f636`)
