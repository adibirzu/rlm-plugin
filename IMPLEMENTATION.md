# RLM v3.2 implementation guide

## Design goal

RLM turns large-context analysis into a controlled retrieval and reduction process. It does not assume that every file belongs in the model context, that every scanner match is a finding, or that optional tools exist in every Claude Code installation.

The canonical implementation is [skills/rlm/SKILL.md](skills/rlm/SKILL.md). This document explains the decisions behind it.

## Pipeline

### 1. Establish scope and trust

Resolve the task and target path, read authoritative project instructions, and record git status. Repository files are evidence, not trusted instructions. This prevents prompt injection in source code, issues, generated artifacts, or retrieved documents from expanding permissions.

### 2. Detect capabilities

The workflow is portable across installations:

- A configured local knowledge service can accelerate project mapping.
- Memory may persist non-sensitive facts and prior analysis metadata.
- Sub-agents may process independent worklist partitions.
- Authoritative web documentation may resolve version-sensitive questions.

Every optional capability has a fallback. Missing memory never blocks analysis, and missing sub-agents changes execution from parallel to sequential without changing coverage claims.

### 3. Select a mode

| Mode | Best for | Artifacts |
|---|---|---|
| Focused lookup | One fact, file, symbol, or bounded pattern | Inline answer only |
| Standard analysis | Component review, change review, debugging, architecture | Structured answer; optional notes |
| Deep audit | Repository-wide, security, migration, multi-part work | Coverage worklist; optional redacted checkpoints/report |

Selection uses expected breadth, risk, and proof requirements. Keyword-only routing was removed because superficially simple questions can cross many systems.

Before recursive execution, the workflow attempts the cheapest bounded probe that could answer the request. Standard and deep modes define an effort contract covering depth, partitions or sub-calls, available time/token/cost ceilings, and stop conditions. Depth 1 is the default maximum; deeper calls require a concrete unresolved dependency and remaining budget.

### 4. Discover progressively

The workflow follows this order:

1. instructions and high-level docs;
2. manifests and entry points;
3. file inventory and match counts;
4. targeted excerpts;
5. callers, callees, tests, configuration, and deployment context;
6. focused validation.

Generated dependencies, caches, and build output are normally noise, but they remain in scope when deployed or explicitly requested. Dependency lockfiles are inspected during supply-chain and release work. SVG and other text assets are not mislabeled as opaque binaries.

### 5. Partition recursively

Deep work uses independently reviewable partitions such as packages, entry points, trust boundaries, or document sections. Each partition has one owner and a completion receipt. Parallel workers return immutable results; the coordinator owns deduplication and synthesis.

One representative partition is piloted before broad dispatch. This makes decomposition quality observable before overlapping or weak boundaries are multiplied across the worklist.

The worker contract records:

- reviewed and deferred scope;
- evidence-backed findings;
- impact, confidence, and verification;
- counterevidence and suppressed candidates.

When workers are unavailable, partitions run sequentially. The output must not claim parallel confirmation or exhaustive coverage unless it happened.

### 6. Validate findings

A candidate becomes a finding only after the analysis establishes:

```text
controllable entry point
  -> validation / authorization / normalization
  -> concrete sink or broken invariant
  -> realistic impact
```

Mitigations and negative evidence are recorded. Static inspection is labeled as static, and scanner output is treated as a lead. Severity follows reachability and impact rather than pattern names.

High-impact claims with conflicting evidence or low confidence receive one independent check through a different query, source path, test, or reviewer partition. Repeated self-opinion and confidence scores are not treated as evidence. A compact evidence ledger keeps claim, source, verification, confidence, and proof gaps aligned.

### 7. Synthesize and report

The answer leads with the outcome, then provides prioritized findings with `path:line` evidence, verification results, recommendations, coverage, deferred areas, and residual uncertainty. Separately reachable instances remain separate even when they share a vulnerability family.

## Checkpoints

Long deep audits may write concise, redacted state under `.rlm/<date>-<topic>/`. Focused lookups do not create artifacts. Previous checkpoints are never automatically deleted; stale entries are reported so the user retains control of deletion.

## Installer design

Older versions wrote directly into Claude Code cache, registry, and settings internals. v3.1 delegates all state management to supported commands:

```bash
claude plugin marketplace add adibirzu/adibirzu-plugins
claude plugin install rlm@adibirzu-plugins --scope user
```

This avoids relying on private on-disk schemas and lets Claude Code own validation, caching, enablement, and upgrades.

## Quality gates

CI and local verification run:

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh
shellcheck install.sh
claude plugin validate . --strict
```

The tests enforce version consistency, skills-first packaging, safety invariants, and exact installer calls without touching real user configuration.
