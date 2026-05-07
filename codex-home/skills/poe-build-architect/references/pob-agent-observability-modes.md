# PoB Agent Observability Modes

Status: skill-owned runtime policy.

This policy defines what PoB product agents should emit by default, when they
must produce fuller internal process packets, and what the orchestrator audits.
It is not a tracing engine, optimizer, or user-facing prose report system.

## Normal Mode

Normal Mode is the default for ordinary product runs.

Always-on decision artifact:

- emit a compact Action Cost/Value Ledger for material decisions;
- keep the ledger structured and machine-readable;
- include selected/rejected/blocked rows, resource cost, alternatives
  considered, expected surfaces, evidence refs or missing-evidence accounting,
  and verdict reason.

User-facing output:

- show a short summary and artifact refs;
- do not paste full process packets by default;
- do not expose internal scratch, long hypothesis logs, or full trace packets as
  the normal answer.

Normal Mode does not require full Intake, Hypothesis, Measurement, Decision
Review, or Failure packets unless one of the Debug Mode triggers fires.

## Debug Mode

Debug Mode is conditional. Enable it only when the run needs audit depth because
the compact ledger is not enough to explain or repair behavior.

Triggers:

- failed proof;
- unstable decision family;
- repeated bad choice;
- high-cost or high-impact action;
- missing evidence;
- runtime, import, producer, materializer, or verifier blocker;
- explicit orchestrator request.

Required internal packets:

- Intake Packet;
- Pre-PoB Hypothesis Packet;
- Action Cost/Value Ledger;
- Measurement Packet;
- Decision Review Packet;
- Failure Packet, when applicable.

These packets are internal artifacts. They may be referenced in the final answer
by locator or summary, but they are not pasted as user-facing prose unless the
operator explicitly requests a trace review.

## Trace Sampling Mode

Trace Sampling Mode is periodic process audit. It exists to find behavioral
errors in PoB subagents, not to burden every ordinary run.

Use it for sampled runs, regression investigations, or orchestrator-selected
audits. Do not enable it on every normal run.

Configurable policy level:

- default sampling: off for ordinary single-run product answers;
- enable when the orchestrator labels a run as trace-sampled;
- enable for selected regression batches after a repeated behavioral failure;
- record sampled trace artifacts separately from user-facing output.

## Orchestrator Audit Surface

The orchestrator does not inspect hidden model reasoning. It audits artifacts:

- were 2-3 alternatives considered before PoB;
- was resource cost recorded;
- were expected surfaces named before measurement;
- did measured evidence appear when a measured claim was made;
- did the agent record the failed or bad hypothesis instead of silently replacing
  it with a new probe;
- did user-facing output stay compact unless Debug Mode or Trace Sampling Mode
  was explicitly enabled.

If these artifacts are missing, the blocker is missing observability evidence,
not "the model did not think hard enough."
