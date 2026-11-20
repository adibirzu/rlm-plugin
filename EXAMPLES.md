# RLM v4.0 examples

Invoke the installed skill in Claude Code as:

```text
/rlm:rlm <task> [path]
```

Other harnesses use their own skill syntax, for example `$rlm <task>` in Codex and `/rlm <task>` in Gemini CLI, Cursor, and Grok. The examples below use the Claude Code form.

## Focused lookup

Find a definition without creating checkpoints or a report:

```text
/rlm:rlm "where is request authentication enforced?" src/
```

Count or list a bounded pattern:

```text
/rlm:rlm "list the public API routes and their handlers" backend/
```

If the evidence crosses several subsystems, RLM escalates based on observed scope rather than the wording alone.

## Standard analysis

Review one component with its callers, tests, and configuration:

```text
/rlm:rlm "review authorization for object-level access and identify missing negative tests" src/api/documents/
```

Trace a runtime flow:

```text
/rlm:rlm "trace uploaded files from validation through storage and download" .
```

Review a branch against a known baseline:

```text
/rlm:rlm "compare this branch with main; report correctness regressions and missing tests" .
```

RLM verifies the comparison ref and reads enough unchanged context to understand the diff.

## Deep audit

Run a repository-wide review with explicit coverage limits:

```text
/rlm:rlm "audit security, reliability, tests, packaging, and documentation; implement confirmed fixes" .
```

Audit a large monorepo by independently reviewable surfaces:

```text
/rlm:rlm "review every deployed service for authentication, authorization, and secret handling" services/
```

When sub-agents are available, independent partitions may run in parallel. Otherwise the same worklist runs sequentially. The result states what was reviewed, deferred, or not runtime-validated.

## Optional capability behavior

### Memory unavailable

RLM continues without persistence. It can still use git history or an explicit ref for incremental review.

### Sub-agents unavailable

RLM processes worklist partitions sequentially and does not claim parallel confirmation.

### Local knowledge unavailable

RLM falls back to repository instructions, manifests, documentation, and source discovery.

## Security review

```text
/rlm:rlm "audit this plugin for prompt injection, unsafe tool use, destructive actions, secret exposure, and supply-chain risk" .
```

Repository content is treated as untrusted evidence. Lockfiles, manifests, CI configuration, and text-based assets stay in scope when relevant. Potential secrets are redacted rather than repeated.

## Long-running work

For a deep audit where recovery artifacts are useful:

```text
/rlm:rlm "perform a full architecture review; keep concise redacted checkpoints so the work can resume after compaction" .
```

Scratch state is written under `.rlm/<topic>/` after confirming the directory is ignored. RLM does not delete older checkpoints automatically.

## Large logs and documents

```text
/rlm:rlm "logs/app-2026-11-18.log is about 400 MB; find when the payment errors started and the first distinct error" logs/
```

RLM counts and filters the log with commands, prints only bounded excerpts, and keeps larger slices under `.rlm/<topic>/`.

## Small or local models

```text
/rlm:rlm "you are a small local model; review src/ for unsafe deserialization within the small-tier budget" src/
```

The small tier takes its partitions from the inventory script, makes at most four sub-calls, never goes to depth 2, and reports unreviewed chunks as deferred when the budget is spent.

## Independent verification

```text
/rlm:rlm "confirm whether sessions survive logout in services/auth; get an independent check before reporting it" services/auth/
```

A high-impact claim with conflicting evidence gets one independent reviewer, from a different model family when the harness can reach one.

## Helper scripts

Build a worklist without loading any file content:

```bash
python3 skills/rlm/scripts/rlm_inventory.py services/ --manifest .rlm/audit/manifest.json
```

Validate a worker result against the scope it reviewed:

```bash
python3 skills/rlm/scripts/rlm_ledger.py .rlm/audit/worker-01.md --root services/ --tier mid --depth 1
```

## Harness installation

```bash
./install.sh --check --json
./install.sh --sync-harnesses
./install.sh --sync-harnesses --backup
```

The first command reports drift without writing. The second links the skill into every harness that is present. The third also moves differing local copies to `~/.rlm-skill-backups/`.

## Better requests

Provide a narrow scope when possible:

```text
/rlm:rlm "review token verification and session renewal" src/auth/
```

State the baseline for change reviews:

```text
/rlm:rlm "review changes since v2.4.0 for backward compatibility" .
```

State whether fixes are authorized:

```text
/rlm:rlm "find deployment blockers and explain them; do not modify files" deploy/
/rlm:rlm "find deployment blockers, add regression tests, and fix confirmed issues" deploy/
```
