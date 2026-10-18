# Risk and Authorization

Completing a task does not authorize publishing it, deleting data, spending money, changing permissions, or calling an external service. Authorization is scoped to a concrete action, target, and time.

## Approval matrix

| Category | Examples | Default | Required before action | Stop condition |
|---|---|---|---|---|
| Local delete or overwrite | Remove a directory, replace a database, bulk rewrite files | Deny | Exact path, object count, backup or rollback, explicit user approval | Target resolves outside the approved root or differs from the approved list |
| Git history | Reset, force-push, rebase shared history, delete branches | Deny | Exact repository, refs, recovery plan, explicit user approval | History or remote differs from the approved refs |
| Secrets and PII | Read `.env`, tokens, cookies, customer exports, private datasets | Deny by default | Demonstrated need, minimum fields, redaction plan, explicit user approval | Secret appears in output, logs, screenshots, or a public path |
| Network and third-party APIs | Outbound calls, scraping, webhook delivery, uploads | Deny | Destination, method, payload class, rate limit, data classification, explicit user approval | Destination, payload, or rate differs from the approved request |
| Dependency installation | System packages, global installs, unpinned downloads | Deny | Package, version, source, install scope, rollback, explicit user approval | Source changes, version is unpinned, or installation becomes system-wide without approval |
| CI and release | Workflow edits, release creation, artifact publication | Deny | Repository, workflow, target environment, artifact, explicit user approval | Branch, tag, environment, or artifact changes |
| Publish and upload | Git commit or push, package registry, website, file share | Deny | Repository or destination, commit range, visibility, content inventory, explicit user approval | New untracked file, private data, secret, or changed visibility |
| Permissions and identity | Roles, ACLs, OAuth scopes, account settings | Deny | Principal, resource, old and new permissions, expiry, explicit user approval | Principal or scope exceeds the approved change |
| Payments and financial actions | Purchases, refunds, transfers, billing changes | Deny | Amount, currency, counterparty, limit, explicit user approval | Amount, counterparty, or recurrence differs |
| Production environment | Deploy, migration, restart, feature flag change | Deny | Environment, service, revision, rollback, observation window, explicit user approval | Revision, service, or blast radius differs |
| Schema or state migration | Database migration, queue migration, state reclassification | Deny | Migration source and target, row estimate, backup, rollback, explicit user approval | Schema target, row count, or rollback plan differs |
| Bulk data change | Backfill, reclassification, mass update, export | Deny | Query, row estimate, sampling result, backup, explicit user approval | Row count, predicate, or destination differs materially |

## Approval record

Record each approval with:

- `action`
- `target`
- `scope`
- `reversible`
- `rollback`
- `approved_by`
- `approved_at`
- `expires_at` when applicable
- `evidence`

The exact field names may vary by host, but the information must be present and bound to the current task ID and revision.

## Approval rules

- Ask for the smallest concrete action, not a broad category such as "use the network" or "clean up files".
- Do not inherit approval from a previous task, a previous run, or a general statement such as "finish the job".
- Do not treat a sandbox permission as user intent. The sandbox may allow a command; the user still must authorize the action when this skill requires approval.
- Re-request approval when target, payload class, amount, visibility, environment, or blast radius changes.
- Prefer a mock, dry run, local fixture, or temporary directory when it can prove the behavior without the real side effect.
- Stop and report if the action cannot be performed within the approved scope.

## Public repository rules

- Use synthetic examples or fully de-identified data.
- Never commit secrets, tokens, cookies, customer material, private job descriptions, private datasets, or personal filesystem paths.
- A commit or push is an external publication action. Do not perform either unless the user explicitly requests that exact operation.
- Before publication, inventory staged files and inspect for private or generated data that should not be public.
