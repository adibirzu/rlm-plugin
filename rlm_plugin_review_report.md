# RLM plugin review report

**Review date:** 2026-07-04

**Reviewed version:** 3.0.0

**Resulting version:** 3.1.0

## Scope

The review covered the plugin manifest, workflow instructions, installer, documentation, repository hygiene, testability, CI, GitHub distribution, and the adibirzu marketplace entry. Static security checks covered destructive shell behavior, direct mutation of Claude Code internals, secret patterns, prompt-injection boundaries, external capability assumptions, and CI supply-chain controls.

This was a parent-agent static and test-backed review. It did not use the installed exhaustive multi-agent security-scan workflow, so it does not claim exhaustive vulnerability coverage or runtime validation of every Claude Code execution path.

## Confirmed findings and resolution

| Severity | Finding | Resolution |
|---|---|---|
| High | `install.sh` wrote directly to private cache, registry, and settings files and recursively deleted cache paths. These schemas are not a stable public interface. | Replaced with supported `claude plugin marketplace add`, `install`, and `uninstall` commands. |
| High | Repository content was not explicitly treated as untrusted, leaving the analysis workflow open to instruction-following from source files or retrieved text. | Added deterministic trust, scope, secret-redaction, and authorization boundaries to the skill. |
| Medium | The workflow assumed particular memory, agent, model, and task-output APIs existed. | Added capability detection and sequential/no-memory fallbacks; removed hard-coded model and tool names. |
| Medium | Checkpoint cleanup automatically used recursive deletion. | Removed automatic deletion. Stale checkpoints are reported for user-controlled cleanup. |
| Medium | Dependency lockfiles and SVG were blanket-excluded even when security or supply-chain analysis required them. | Classified text assets and lockfiles as reviewable evidence when relevant. |
| Medium | The canonical implementation lived only in legacy `commands/`. | Migrated to `skills/rlm/SKILL.md` while preserving the `/rlm:rlm` namespace. |
| Medium | The project had no automated tests or CI. | Added eight standard-library regression tests and a pinned GitHub Actions workflow. |
| Low | Documentation encoded optimistic token estimates and keyword-only mode selection. | Rewrote docs around scope-, risk-, and evidence-based focused, standard, and deep modes. |

## Verification

- Python regression tests cover manifest/version consistency, skills-first packaging, safety invariants, install, uninstall, help, and invalid argument behavior.
- `bash -n` and ShellCheck validate the installer.
- `claude plugin validate . --strict` validates the manifest and skill frontmatter.
- CI action revisions and the Claude Code npm package are pinned.
- Secret and internal-topology pattern scans found no reportable material in the changed files.

## Residual risks

- The skill is instruction-driven; real behavior still depends on the host model, enabled tools, permissions, and repository content.
- CI validates schema and invariants but does not launch a billable interactive Claude session.
- Marketplace installation should be smoke-tested after both repositories are pushed because the marketplace resolves the remote plugin repository.
