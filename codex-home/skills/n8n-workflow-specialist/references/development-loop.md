# Development Loop

## Pinning And Mocking

During workflow development, use n8n's data mocking and pinning features to reduce unnecessary calls to live systems.

Pinning is especially useful when:

- the trigger depends on an external system
- an API has rate limits
- you want deterministic test data across repeated edits

Remember:

- pinning is for development, not production runs
- binary outputs cannot be pinned
- you can edit pinned JSON to test edge cases quickly

## Practical Loop

For many workflow edits, the cheapest loop is:

1. run the upstream node once
2. pin or edit its output
3. patch downstream logic
4. validate the workflow JSON if applicable
5. run only the downstream path that changed

## Execution Evidence

When a workflow change needs proof, capture narrow evidence:

- returned webhook payload
- execution error node and message
- Data Table row written
- minimal screenshot or HTML result

Avoid broad reruns when a pinned dataset plus one focused execution proves the contract.

## Custom Execution Data

If execution history needs lightweight, reviewer-friendly metadata, consider custom execution data rather than inventing ad hoc logging everywhere. Keep it small and purposeful.
