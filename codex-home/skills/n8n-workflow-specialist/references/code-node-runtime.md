# Code Node Runtime

## When To Use A Code Node

Use a Code node for small-to-medium in-workflow transforms where keeping logic on the canvas is still readable.

Prefer a helper script instead when you need:

- file system access
- shell access
- heavy third-party libraries
- logic reused outside n8n
- long code that would make the workflow hard to review

## Language Choice

Default to JavaScript unless the current project already depends on native Python in Code nodes.

Why:

- JavaScript is the most portable default in n8n
- Python support in modern n8n depends on task runners
- older Python examples may refer to legacy Pyodide behavior

If a workflow uses Python in Code nodes, document the exact runtime assumption.

## Runtime Constraints

The Code node is not a full host shell.

Important constraints:

- do not assume direct file system access from the Code node
- do not assume direct HTTP access from the Code node
- use dedicated nodes such as `HTTP Request` or `Read/Write Files from Disk` when that is the real need
- if the project truly needs OS-level behavior, use an external helper through `Execute Command` on self-hosted n8n

## Task Runners

Modern native Python support and secure Code-node execution rely on task runners.

Practical implications:

- self-hosted instances may differ in whether task runners are configured
- queue mode may require runner setup on each worker, not just the main instance
- hardened setups may isolate runners more aggressively than local dev setups

If a workflow depends on Code-node runtime features beyond plain JavaScript transforms, include that assumption in handoff notes.

## Built-In Methods And Variables

Prefer n8n's built-in methods and variables instead of re-implementing context plumbing manually.

But remember:

- some built-ins exist in expressions but not in the Code node
- some examples online assume a different language or older runtime
- do not promise a method is available unless local evidence or docs confirm it

## Item Linking Trap

When a Code node changes item cardinality, downstream references can break unless item linking is preserved.

High-risk cases:

- creating brand new items
- returning a different number of items than came in
- merging or splitting items manually

If later nodes rely on `$("Node Name").item`-style access, be careful. Prefer simpler transforms when possible. If manual linking is required, return `pairedItem` metadata correctly.

## Environment Access

Do not assume Code nodes can freely read environment variables in every instance.

If the workflow depends on environment access from inside the Code node, state that explicitly and verify the instance configuration supports it.

## Worker Handoff Notes

When a task includes non-trivial Code-node work, return:

- node names edited
- language used
- run mode used
- any task-runner assumption
- whether item linking was preserved manually
- whether a helper script would be a safer next refactor
