# PoE Skill Runtime Boundary

Status: binding architecture direction.

This document defines the split between the Poe Junkroan development repository
and the runtime PoE skills used by Codex agents.

## Core Rule

The installed PoE skill bundle is the product runtime.

The repository is the development workspace for building, testing, validating,
and releasing that runtime. A product PoB agent must be able to operate from the
installed PoE skills without depending on the current `Poe Junkroan` worktree as
its live instruction source.

In short:

```text
PoE skills = product runtime
Repo = agent development kit / factory
```

## What Lives In PoE Skills

Everything required for a product PoB agent to work must be packaged into the
PoE skills or their skill-owned support directories:

- `SKILL.md` operating instructions;
- skill-owned references and playbooks;
- scripts and wrappers the product agent is expected to call;
- schemas needed by those scripts and output contracts;
- templates for accepted product reports and artifacts;
- fixture snippets and small eval traps needed by the skill itself;
- policy constants, accepted rails, output gates, and error contracts;
- packaging/version manifest;
- local setup or dependency checks;
- instructions for any allowed external runtime such as pinned Path of Building.

The runtime skill must not require the current repo path, repo docs, repo-local
task queue, or repo-local roadmap to answer a normal PoE product request.

If a runtime rule is only present in repo docs and not present in a packaged
skill reference, script, schema, or template, the product runtime is incomplete.

## What Lives In The Repo

The repo exists to develop the PoE skills and their supporting tooling. It may
contain source copies of skill files, reference drafts, test fixtures, schemas,
runtime wrapper source, and release tooling, but those files are development
sources, not the product agent's live operating memory.

Repo-owned work includes:

- skill source authoring and synchronization;
- PoB wrapper and adapter development;
- packaging scripts that assemble installed skill bundles;
- contract tests and readiness evals for skills;
- source-of-truth development specs;
- roadmap, task queue, validation log, and decision log for the developers of
  the agent;
- migration plans for turning repo docs/scripts into skill-owned runtime assets;
- diagnostics for skill drift between repo source and installed skill copies.

The repo may define what the product skill must become. It must not be required
at runtime for an ordinary user-facing PoB build, review, trade, craft, research,
or loadout request.

## Forbidden Runtime Coupling

A shipped PoE skill is not self-contained if it:

- tells the agent to read `<dev-repo>\docs\...` as a mandatory
  runtime instruction;
- requires repo-local `schemas/`, `templates/`, `src/`, `tests/`, `.orchestrator`,
  or `docs/task-queue.md` to answer an ordinary product ask;
- hardcodes the current worktree path;
- uses repo-local scripts as the only way to run product behavior;
- treats repo roadmap status as product memory;
- requires the build agent to browse the repo before it can reason about PoB;
- hides product rules in developer-only docs without packaging them into the
  skill bundle.

During development, tests and harnesses may intentionally run against the repo.
Those runs must be labeled as development or dogfood runs, not as proof that the
installed skill works without the repo.

## Product-Agent Validation Rule

There are two different validation layers:

- Packaging readiness:
  scripts and tests may prove that installed skill bundles contain required
  files, import packaged runtime code, and fail closed without the development
  repo.
- Product-agent behavior:
  the only accepted proof is to spawn the product agent as a subagent, invoke
  the required installed PoE skill, and give it a real user-like task through
  that skill.

Do not validate product-agent behavior by having the engineering agent imitate
the product agent, by calling repo-local scripts directly as a substitute for
the agent, by reading repo docs as runtime memory, or by using any path that
bypasses the installed PoE skills.

A behavioral validation report must name the spawned subagent, the invoked PoE
skill, the task it received, the artifact or blocker it returned, and whether
the result satisfied the relevant skill-owned output contract.

For product behavior proof, the spawned product agent must author the material
product decision artifact itself. For Direct Build this means the spawned PoE
Architect authors and returns the decision ledger or a precise blocker. An
engineering-orchestrator-authored build attempt, script fixture, hand-edited
tree/gem/item/config package, or main-thread repair ledger is only
`dev_probe`/regression evidence, even if a spawned product agent verifies it
afterward.

End-of-run product-agent verification is not enough. If the main/orchestrator
thread chose the PoE build changes, edited the decision ledger after the spawned
agent returned it, or spawned the product agent only to rubber-stamp existing
artifacts, the report must be blocked as product behavior proof. Behavioral
validation records must carry `authoring_provenance` and fail closed unless the
provenance says: product agent authored the ledger, product agent returned it,
the main thread did not mutate it after return, the spawned agent did more than
verify an engineering-authored ledger, and behavioral proof is explicitly
allowed.

## Allowed Runtime Dependencies

Self-contained does not mean no external software exists. The skill may require
external runtimes when the requirement is explicit, versioned, and checked:

- pinned Path of Building release or a verified local PoB installation;
- Python/Node/Lua runtime needed by packaged scripts;
- official trade, Craft of Exile, `poe.ninja`, or web access for skills whose
  product mode explicitly needs those sources;
- local cache or dynamic knowledge directories owned by the skill/runtime, not
  by the repo worktree.

If a dependency is large or cannot reasonably be embedded, the skill must ship a
fetch/verify/bootstrap path or fail closed with the smallest missing dependency.
It must not silently fall back to the development repo.

## Product Memory Placement

Runtime product memory belongs beside or under the skills, not only in repo
planning docs.

Examples:

- compact experiment experience packets;
- Pattern Cards;
- negative memory;
- accepted warnings;
- skill-owned eval traps;
- freshness and reverify metadata;
- user-approved durable PoE behavior rules.

Raw traces, large runtime logs, generated outputs, and caches may remain dynamic
or ignored, but the skill must know how to find, validate, and compact the
runtime memory it is allowed to use.

## Development Source Of Truth

Repo docs are still valuable, but their role is development guidance:

- describe the target architecture;
- define acceptance gates for skill packaging;
- track implementation tasks;
- record why rules exist;
- test whether installed skills contain the needed product runtime behavior.

Docs such as `docs/architecture/agentic-build-system-first-principles.md` are
therefore development contracts for what must be packaged into PoE skills. They are not a
license for the runtime agent to depend on the repo docs forever.

## Migration Rule

Whenever a repo doc, script, schema, or template becomes required by product
PoE-agent behavior, the development task is not complete until one of these is
true:

1. It is packaged into the relevant PoE skill bundle.
2. It is compiled into a skill-owned reference, schema, script, or template.
3. It is explicitly marked as development-only and removed from runtime read
   order.
4. It is replaced by a versioned external dependency check owned by the skill.

## Skill Bundle Acceptance Gates

A PoE skill release is not accepted until:

- its installed copy can run without hardcoded `Poe Junkroan` repo paths;
- every runtime read-order entry resolves inside the skill bundle or an explicit
  external dependency;
- required scripts and schemas are packaged or bootstrap-verified;
- output gates and no-prose/no-hidden-engine rules live in skill-owned files;
- product memory lookup does not require repo docs or task queues;
- a readiness eval proves the skill can answer or correctly block a normal
  product ask in a workspace that does not contain this repo.
- behavioral acceptance has been checked by spawning a product-agent subagent
  with the relevant installed PoE skill and a real task; packaging readiness
  alone is not product proof.
- product behavior proof records include allowed `authoring_provenance`; any
  engineering-authored attempt is retained only as development or regression
  evidence.

## Current-State Interpretation

The current repo still contains many product-agent rules and repo-local skill
playbooks. Treat that as a transitional development state, not the desired
architecture.

Future work should migrate product runtime behavior into installed PoE skills
and convert repo-local product instructions into development specs, tests,
packaging inputs, or historical references.
