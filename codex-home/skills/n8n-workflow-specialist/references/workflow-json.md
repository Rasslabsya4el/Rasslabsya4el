# Workflow JSON

## Core Contract

An exported n8n workflow is mainly:

- workflow metadata such as `name`, `settings`, `tags`, `active`
- `nodes`: array of node objects
- `connections`: object keyed by source node name

The dangerous part is that `connections` reference node `name`, not node `id`.

## Preserve By Default

When editing an existing node, preserve these fields unless the task requires a change:

- `id`
- `name`
- `type`
- `typeVersion`
- `position`
- `parameters`

At workflow level, preserve existing `settings`, `pinData`, `tags`, and `active` unless there is a concrete reason to change them.

## Treat As Instance-Specific

Be careful with:

- workflow `id`
- `versionId`
- `meta.instanceId`
- node `webhookId`
- credential names and IDs inside node `credentials`

For a real exported workflow, preserve them unless the task is explicitly sanitizing the file.

## Safe Connection Editing

Rules:

- every source key in `connections` must match an existing node `name`
- every target `node` in an edge must match an existing node `name`
- deleting a node requires removing inbound and outbound references
- renaming a node requires updating every connection reference
- duplicate node names are dangerous

## Webhook Pattern

For request-response workflows, the clean default is:

- `Webhook`
- validation
- branch or route
- terminal `Respond to Webhook`

If `Webhook.parameters.responseMode` is `responseNode`, do not leave a terminal path that should answer the request without a `Respond to Webhook` node.

## Code Node Contract

n8n data flows as items. The safe return shape is:

```json
[
  {
    "json": {
      "field": "value"
    }
  }
]
```

For Code nodes:

- return items, not raw scalars
- keep the output shape predictable
- avoid hidden item-linking tricks if a plain transform works
- prefer reusable snippets from `assets/templates/code/` when they fit

## Minimal Patch Strategy

Prefer this order:

1. patch one branch, not the whole workflow
2. preserve existing node names
3. add one node at a time
4. validate JSON after the edit
5. give the user one import-and-test loop

## Do Not Do This

- do not invent credential IDs or secret values
- do not upgrade node versions speculatively
- do not add unsupported parameter shapes without local evidence
- do not leave broken JSON or dangling connections

## Templates In This Skill

Start from these assets when useful:

- `assets/templates/webhook_validate_route_response.json`
- `assets/templates/webhook_validate_single_action_response.json`
- `assets/templates/code/normalize_and_chunk_text.js`
- `assets/templates/code/simple_keyword_eval.js`
