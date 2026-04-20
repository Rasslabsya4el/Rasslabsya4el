# Credentials And Promotion

## Export Hygiene

Treat exported workflow JSON as potentially sensitive operational metadata.

Important facts:

- exported workflow JSON includes credential names and IDs
- IDs are not secrets, but credential names can still reveal systems or environments
- imports from cURL can leave authentication headers in node parameters

Before sharing workflow JSON outside the working context, remove or anonymize anything that should not travel.

## Do Not Invent Credentials

Do not fabricate:

- credential IDs
- credential names
- secret values

If a workflow needs credentials, leave the workflow structurally correct and make the rebinding step explicit.

## Promotion Between Instances

An imported workflow is not the whole environment.

Between dev, staging, and prod, you usually need to recreate or rebind:

- credentials
- variable values
- external secret connections
- file paths visible to the runtime
- any local env vars used by helper scripts or nodes

## Source Control Reality

n8n source control and environments can help promotion, but Git does not carry secret values.

Useful rule:

- workflow definitions can move through Git
- credential values still need instance-specific setup
- variables may require manual setup or environment-specific configuration
- Data Table schemas may move, but row data should be treated separately

## Recommended Handoff Contract

For every workflow that touches credentials or deployment assumptions, include:

- which node names require credentials
- which credential type each node expects
- whether import requires UI rebinding
- which env vars or variables must exist
- which secrets must stay outside JSON
- whether the export is sanitized or still instance-specific

## Prefer Explicit Rebinder Notes

Good handoff note:

- `Google Sheets credential must be rebound in nodes A and B after import`

Weak handoff note:

- `Set up creds somehow`
