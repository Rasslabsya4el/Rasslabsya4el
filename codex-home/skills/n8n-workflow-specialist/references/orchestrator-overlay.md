# Orchestrator Overlay

## Purpose

This file augments the active orchestrator role. It does not replace the role's dispatch, acceptance, or reporting contract.

## Use This Overlay For

- scoping n8n workflow implementation tasks
- splitting workflow JSON work from helper-script work
- defining import and validation expectations
- making sure workers return n8n-specific handoff notes

## Useful Task Categories

When decomposing work, classify the task as one or more of:

- workflow JSON patch
- helper script or CLI support
- payload fixtures or test evidence
- runtime or credential setup
- reviewer-facing docs or demo artifacts

That makes it easier to separate ownership cleanly.

## What A Good n8n Worker Task Should Pin Down

Add these details when relevant:

- workflow JSON path
- node names or branch to edit
- what must stay untouched
- expected input payload
- expected output payload
- validator command
- import and smoke-test steps
- credential or env prerequisites

## If The Task Is "Write A Script"

Even if the work product is a script rather than JSON, keep the n8n integration contract explicit:

- how n8n will call it
- what args or env vars it expects
- what stdout or artifacts it returns
- which workflow path it supports

## Required n8n-Specific Handoff Notes

Ask workers to include, when relevant:

- edited node names
- exact validation command
- import steps
- exact smoke-test command or payload
- credentials or env assumptions
- path assumptions relative to the runtime
