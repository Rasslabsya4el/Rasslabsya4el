---
name: universal-humanizer
description: Universal prose humanizer for Codex. Use when the user explicitly invokes `$universal-humanizer`, `universal humanizer`, `humanize`, `de-slop`, `remove AI voice`, or asks to rewrite text so it sounds natural, specific, deliberate, and less AI-generated. Use for rewriting, editing, or reviewing prose across docs, messages, blog posts, specs, and marketing copy. Do not use for code generation, factual research, or cases where the user wants a rigid template preserved verbatim.
---

# Purpose

Turn generic or AI-sounding prose into writing that sounds like a real person made deliberate choices.

The goal is not to add fake personality at random. The goal is to keep the meaning, keep the intended register, and remove patterns that make the text feel generated, padded, or mechanically polished.

# Core Principles

1. Preserve meaning first.
2. Keep the intended audience and register.
3. Replace vagueness with specifics whenever the source supports it.
4. Prefer direct sentences over ornamental phrasing.
5. Remove AI tells without making the text sloppy or inaccurate.
6. Do not invent facts, anecdotes, feelings, or citations.

# When To Use

Use this skill for:

- polishing emails, docs, posts, landing pages, comments, specs, and essays;
- removing AI-sounding phrasing from user-provided text;
- rewriting text to sound more human without changing the underlying point;
- line-editing text that feels padded, generic, salesy, or over-explained;
- reviewing prose and calling out suspicious AI patterns before publication.

Do not use this skill for:

- code changes;
- legal text that must preserve formulaic wording;
- source material that must stay verbatim;
- research tasks where the main problem is missing evidence rather than weak prose.

# The Editing Workflow

1. Identify the target voice.
   - Who is speaking?
   - Who is the audience?
   - What level of formality is appropriate?
   - Should the result sound neutral, sharp, warm, technical, or persuasive?
2. Diagnose the AI patterns.
3. Rewrite for specificity, rhythm, and directness.
4. Run a final de-slop pass.
5. Check that the meaning, evidence, and tone still match the original intent.

If the user only says "humanize this", default to:

- preserve meaning;
- keep the same broad tone;
- reduce filler;
- remove em dashes;
- remove stock AI phrasing;
- keep formatting unless it is part of the problem.

# What To Remove Or Rewrite

## 1. Filler Openers And Meta-Commentary

Cut throat-clearing and stage directions.

Watch for patterns like:

- "Here is the thing"
- "It is worth noting that"
- "Let us break this down"
- "In this section"
- "In conclusion"

Say the point directly.

## 2. Formulaic Structures

Break patterns that feel pre-fabricated:

- "Not X, but Y"
- stacked three-item lists;
- rhetorical question followed by a dramatic fragment;
- repeated contrast structures;
- repeated short punch lines for fake emphasis.

Two concrete points usually read better than three padded ones.

## 3. AI Vocabulary And Inflated Diction

Prefer ordinary words when they carry the meaning better.

Be suspicious of terms like:

- delve
- robust
- leverage
- utilize
- nuanced
- landscape
- ecosystem
- paradigm
- game-changer
- streamline
- highlight
- underscore
- pivotal
- vibrant
- tapestry

Do not ban a word just because it appears on a list. Replace it when it feels generic, inflated, or stacked with other AI-ish wording.

## 4. "Serves As" And Other Copula Dodges

Prefer plain statements over decorative substitutions.

- "serves as" -> often just "is"
- "stands as" -> often just "is"
- "represents" -> use only when real representation is the point

## 5. Vague Authority And Empty Significance

Replace weak claims with sourced or concrete ones.

Watch for:

- "experts say"
- "observers note"
- "many believe"
- "this is important"
- "the implications are significant"
- "this reflects a broader shift"

If the source text does not support a stronger claim, trim the sentence instead of inventing support.

## 6. Promotional Or Breathless Tone

Remove ad copy unless the user explicitly wants ad copy.

Watch for:

- "groundbreaking"
- "stunning"
- "must-visit"
- "rich cultural heritage"
- "renowned"
- "breathtaking"
- "in the heart of"

Prefer concrete details over hype.

## 7. Passive Or Actorless Writing

Name the actor when the sentence gets vague or evasive.

- "mistakes were made" -> who made them?
- "the culture shifted" -> who changed behavior?
- "the feature was improved" -> by what change?

Use passive voice only when the actor truly does not matter.

## 8. Rhythm That Feels Too Even

Vary sentence length and structure. Avoid paragraphs where every sentence lands with the same cadence.

Do not over-correct into chaos. The text should feel written, not random.

## 9. Em Dashes And Other Formatting Tells

Remove em dashes by default unless the user explicitly wants them.

Also avoid:

- bold-first bullet spam;
- decorative unicode markers;
- signposted endings like "In summary";
- excessive italics or quote-mark emphasis.

## 10. Repetition Disguised As Depth

Cut repeated restatements, especially when the paragraph says the same idea three ways with slightly different wording.

# How To Add Real Human Texture

Human writing does not only remove bad patterns. It also makes choices.

Use these levers carefully:

- choose concrete nouns and verbs;
- prefer one clear observation over a vague abstract claim;
- allow uneven rhythm when it helps;
- keep a real point of view when the format allows it;
- admit uncertainty when certainty is not warranted;
- keep transitions light instead of over-signposting.

Do not fabricate personality. If the source is formal, keep it formal. If the source is technical, keep it technical.

# Output Modes

## Rewrite Mode

Default when the user pastes text and asks to humanize it.

Return:

1. the rewritten text;
2. a short note only if a tradeoff matters.

## Review Mode

Use when the user asks for diagnosis, review, or "what sounds AI here".

Return:

- the main problem patterns you found;
- a tightened rewrite or representative examples.

## Compare Mode

Use when the user asks for a before/after style result.

Return:

- short diagnosis;
- revised version.

# Quality Bar

Before finishing, check:

- Did I preserve the actual meaning?
- Did I remove em dashes unless requested?
- Did I cut filler instead of merely swapping synonyms?
- Did I reduce generic abstractions?
- Did I avoid making the prose artificially quirky?
- Does the final text sound like a person with intent rather than a template?

# Response Style

- Be concise.
- Edit directly.
- Do not lecture unless the user asked for explanation.
- If the prose is already strong, say so and make only small changes.
