# Storage And State

## Choose The Right State Surface

For small to moderate structured workflow data, prefer the simplest built-in option that fits.

## Data Tables

Use Data Tables when you need:

- queryable rows
- visible tabular state in the UI
- internal storage for artifacts, audit rows, or small reference datasets

Important points:

- Data Tables are project-scoped
- they are suitable for light to moderate storage
- self-hosted instances default to a 50 MB total size limit unless reconfigured
- direct programmatic access from Code nodes is not supported; use the Data Table node or API

## Workflow Static Data

Use workflow static data only for tiny state such as:

- last processed timestamp
- last seen ID
- tiny checkpoint markers

Caveats:

- it is not available when testing workflows in the editor
- it only persists when the workflow is active and triggered for real
- it is considered experimental and should stay small

Do not use it for anything that should be visible, queryable, or reviewed in bulk.

## Variables

Use n8n variables when you need reusable read-only values exposed through expressions or Code nodes.

Important points:

- variables are strings
- project-scoped variables are available only on supported plans and versions
- `env` exposes environment variables for the instance
- `vars` exposes user-created variables

Do not base a portable workflow on variables unless you know the target instance supports them.

## External Systems

Use external storage when:

- the dataset is large
- relational querying matters
- the state must survive outside n8n cleanly
- the project already has a clear source of truth elsewhere

Good examples:

- PostgreSQL
- Google Sheets
- dedicated vector stores
- external secret stores
