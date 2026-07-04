# RLM v3.1 examples

Invoke the installed skill as:

```text
/rlm:rlm <task> [path]
```

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

Checkpoints may be written under `.rlm/<date>-<topic>/` after confirming the directory is ignored. RLM does not delete older checkpoints automatically.

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
