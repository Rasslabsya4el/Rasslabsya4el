# LoadoutPlan

- Schema version (`schema_version`): `{{ schema_version }}`
- Record kind (`record_kind`): `{{ record_kind }}`
- Plan ID (`plan_id`): `{{ plan_id }}`
- Generated At (`generated_at`): `{{ generated_at }}`

## 1. Review Context

- Review ID (`review_context.review_id`): `{{ review_context.review_id }}`
- Build ID (`review_context.build_id`): `{{ review_context.build_id }}`
- Build label (`review_context.build_label`): `{{ review_context.build_label }}`
- Build source (`review_context.build_source`): `{{ review_context.build_source }}`
- PoB run ID (`review_context.pob_run_id`): `{{ review_context.pob_run_id }}`
- Archetype label (`review_context.archetype_label`): `{{ review_context.archetype_label }}`
- Review status (`review_context.review_status`): `{{ review_context.review_status }}`
- Baseline verdict (`review_context.baseline_verdict`): `{{ review_context.baseline_verdict }}`

## 2. Route Summary

- Route kind (`route_summary.route_kind`): `{{ route_summary.route_kind }}`
- Route label (`route_summary.route_label`): `{{ route_summary.route_label }}`
- Breakpoint count (`route_summary.breakpoint_count`): `{{ route_summary.breakpoint_count }}`
- Current setup ID (`route_summary.current_setup_id`): `{{ route_summary.current_setup_id }}`
- Current setup label (`route_summary.current_setup_label`): `{{ route_summary.current_setup_label }}`
- Target setup ID (`route_summary.target_setup_id`): `{{ route_summary.target_setup_id }}`
- Target setup label (`route_summary.target_setup_label`): `{{ route_summary.target_setup_label }}`
- Swap breakpoint ID (`route_summary.swap_breakpoint_id`): `{{ route_summary.swap_breakpoint_id }}`
- Swap step (`route_summary.swap_step`): `{{ route_summary.swap_step }}`
- Swap target level (`route_summary.swap_target_level`): `{{ route_summary.swap_target_level }}`
- Swap target budget chaos (`route_summary.swap_target_budget_chaos`): `{{ route_summary.swap_target_budget_chaos }}`

## 3. Breakpoints

- Breakpoint items (`breakpoints[]`):
  - Step (`breakpoints[].step`)
  - Breakpoint ID (`breakpoints[].breakpoint_id`)
  - Phase kind (`breakpoints[].phase_kind`)
  - Level target (`breakpoints[].level_target`)
  - Budget target chaos (`breakpoints[].budget_target_chaos`)
  - Current play setup (`breakpoints[].current_play_setup`)
  - Current setup ID (`breakpoints[].current_play_setup.setup_id`)
  - Current label (`breakpoints[].current_play_setup.label`)
  - Current primary skill (`breakpoints[].current_play_setup.primary_skill`)
  - Current notes (`breakpoints[].current_play_setup.notes`)
  - Next play setup (`breakpoints[].next_play_setup`)
  - Next setup ID (`breakpoints[].next_play_setup.setup_id`)
  - Next label (`breakpoints[].next_play_setup.label`)
  - Next primary skill (`breakpoints[].next_play_setup.primary_skill`)
  - Next notes (`breakpoints[].next_play_setup.notes`)
  - Swap trigger (`breakpoints[].swap_trigger`)
  - Trigger kind (`breakpoints[].swap_trigger.trigger_kind`)
  - Trigger target level (`breakpoints[].swap_trigger.target_level`)
  - Trigger target budget chaos (`breakpoints[].swap_trigger.target_budget_chaos`)
  - Required gear target IDs (`breakpoints[].swap_trigger.required_gear_target_ids[]`)
  - Requires review pass (`breakpoints[].swap_trigger.requires_review_pass`)
  - Condition note (`breakpoints[].swap_trigger.condition_note`)
  - Gear targets (`breakpoints[].gear_targets[]`)
  - Gear target ID (`breakpoints[].gear_targets[].target_id`)
  - Gear slot (`breakpoints[].gear_targets[].slot`)
  - Gear label (`breakpoints[].gear_targets[].label`)
  - Gear priority (`breakpoints[].gear_targets[].priority`)
  - Gear summary (`breakpoints[].gear_targets[].summary`)
  - Mandatory for swap (`breakpoints[].gear_targets[].mandatory_for_swap`)
  - Acquisition kind (`breakpoints[].gear_targets[].acquisition_kind`)
  - Shopping actions (`breakpoints[].shopping_actions[]`)
  - Shopping step (`breakpoints[].shopping_actions[].step`)
  - Shopping timing (`breakpoints[].shopping_actions[].timing`)
  - Shopping action kind (`breakpoints[].shopping_actions[].action_kind`)
  - Shopping title (`breakpoints[].shopping_actions[].title`)
  - Shopping summary (`breakpoints[].shopping_actions[].summary`)
  - Shopping target gear IDs (`breakpoints[].shopping_actions[].target_gear_ids[]`)
  - Shopping trade link bundle refs (`breakpoints[].shopping_actions[].trade_link_bundle_refs[]`)
  - Shopping bundle ID (`breakpoints[].shopping_actions[].trade_link_bundle_refs[].bundle_id`)
  - Shopping bundle kind (`breakpoints[].shopping_actions[].trade_link_bundle_refs[].bundle_kind`)
  - Shopping bundle label (`breakpoints[].shopping_actions[].trade_link_bundle_refs[].label`)
  - Shopping bundle URL (`breakpoints[].shopping_actions[].trade_link_bundle_refs[].resolved_search_url`)
  - Craft follow-up refs (`breakpoints[].craft_follow_up_refs[]`)
  - Craft record kind (`breakpoints[].craft_follow_up_refs[].record_kind`)
  - Craft record ID (`breakpoints[].craft_follow_up_refs[].record_id`)
  - Craft label (`breakpoints[].craft_follow_up_refs[].label`)
  - Craft status (`breakpoints[].craft_follow_up_refs[].status`)
  - Craft note (`breakpoints[].craft_follow_up_refs[].note`)
  - Caveats (`breakpoints[].caveats[]`)
  - Caveat category (`breakpoints[].caveats[].category`)
  - Caveat statement (`breakpoints[].caveats[].statement`)
  - Caveat impact on progression (`breakpoints[].caveats[].impact_on_progression`)
