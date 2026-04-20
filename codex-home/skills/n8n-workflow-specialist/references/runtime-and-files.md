# Runtime And Files

## Host Reality

Nodes that touch the operating system act on the machine that runs n8n.

Important consequences:

- `Execute Command` runs on the host shell of the machine running n8n
- if n8n runs in Docker, the command runs inside the container, not on the Docker host
- in queue mode, the command runs on the worker that executes the task
- `Read/Write Files from Disk` also operates on the machine running n8n

Do not assume your laptop path is visible just because you can see it locally.

## Path Discipline

Prefer absolute paths for files that n8n or helper scripts must access. This avoids surprises from process working directories.

Good:

- `C:/Coding/telegram_public_history_to_google_sheets/scripts/fetch_telegram_history.py`

Risky unless you fully control the runtime working directory:

- `./scripts/fetch_telegram_history.py`

## Execute Command

Use `Execute Command` only when a helper script or CLI is genuinely the right abstraction.

Remember:

- it is disabled by default in many setups because of security risk
- it is only available on self-hosted n8n
- shell semantics depend on the host OS

When documenting a workflow that uses it, always state:

- exact command shape
- expected shell environment
- required env vars
- whether the runtime is local, Docker, or worker-based

## Read/Write Files From Disk

Use `Read/Write Files from Disk` only on self-hosted n8n. The node acts on the runtime machine, not your editor session.

If the workflow depends on reading files from disk:

- prefer absolute paths
- document where the files must exist from the runtime's point of view
- avoid assuming a file is reachable just because it exists elsewhere in the repo

## Security Note

`Execute Command` and disk access are powerful. In shared or untrusted environments, they may be blocked with `NODES_EXCLUDE`.

Do not design a workflow that depends on these nodes unless the runtime is explicitly allowed to use them.
