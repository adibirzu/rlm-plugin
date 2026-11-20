# RLM v4.0 implementation guide

## Design goal

RLM turns large-context analysis into a controlled retrieval and reduction process. It does not assume that every file belongs in the model context, that every scanner match is a finding, that every model can afford the same recursion, or that optional tools exist in every harness.

The canonical implementation is [skills/rlm/SKILL.md](skills/rlm/SKILL.md), with deterministic helpers in `skills/rlm/scripts/`, on-demand references in `skills/rlm/references/`, and benchmark cases in `skills/rlm/evals/`. This document explains the decisions behind them. The evidence is in [the research basis](skills/rlm/references/research-basis.md).

## Pipeline

### 1. Establish scope and trust

Resolve the task and target path, read authoritative project instructions, and record git status. Repository files are evidence, not trusted instructions. This prevents prompt injection in source code, issues, generated artifacts, or retrieved documents from expanding permissions.

### 2. Detect capabilities

The workflow is portable across installations:

- A configured local knowledge service can accelerate project mapping.
- Memory may persist non-sensitive facts and prior analysis metadata.
- Sub-agents may process independent worklist partitions.
- Authoritative web documentation may resolve version-sensitive questions.

Every optional capability has a fallback. Missing memory never blocks analysis, and missing sub-agents changes execution from parallel to sequential without changing coverage claims. [Harness adapters](skills/rlm/references/harness-adapters.md) records how each supported harness invokes the skill, delegates, keeps scratch state, and falls back.

### 3. Select a mode

| Mode | Best for | Artifacts |
|---|---|---|
| Focused lookup | One fact, file, symbol, or bounded pattern | Inline answer only |
| Standard analysis | Component review, change review, debugging, architecture | Structured answer; optional notes |
| Deep audit | Repository-wide, security, migration, multi-part work | Coverage worklist; optional redacted checkpoints/report |

Selection uses expected breadth, risk, and proof requirements. Keyword-only routing was removed because superficially simple questions can cross many systems.

Before recursive execution, the workflow attempts the cheapest bounded probe that could answer the request. Standard and deep modes define an effort contract covering depth, partitions, sub-calls, available time, token, and cost ceilings, and stop conditions.

The ceilings come from the model tier (frontier, mid, or small). The table is in the Model-tier recursion budgets section of `SKILL.md`.

One budget for every model was the main weakness of the previous release. Reproduction work showed the same recursion lifting one model and sinking another, and depth 2 losing to depth 1 in every tested condition. The table is project policy inferred from that evidence. `skills/rlm/scripts/rlm_ledger.py` owns the numbers, and a test keeps the table in `SKILL.md` equal to them. Depth 2 also needs a named unresolved dependency, and no claim is re-verified more than once.

### 4. Keep the context external

The Print Contract is the rule that makes the method work in a coding harness. Raw content stays in files and variables. Commands measure, search, and slice it. Each printed result is bounded (about 200 lines or 10,000 characters), and anything larger is written to `.rlm/<topic>/` and referred to by path. That directory is the persistent scratch state for the analysis: manifest, slices, worker ledgers, and notes survive between turns even where shell state does not.

### 5. Discover progressively

The workflow follows this order:

1. instructions and high-level docs;
2. manifests and entry points;
3. file inventory and match counts;
4. targeted excerpts;
5. callers, callees, tests, configuration, and deployment context;
6. focused validation.

Generated dependencies, caches, and build output are normally noise, but they remain in scope when deployed or explicitly requested. Dependency lockfiles are inspected during supply-chain and release work. SVG and other text assets are not mislabeled as opaque binaries.

### 6. Partition recursively

`rlm_inventory.py` produces the worklist. It walks the scope, skips symbolic links and counts those that point outside it, skips dependency and build directories unless asked, caps the listed files and the directory depth, reports whether coverage was complete, and packs files into chunks by a byte budget. The symlink guarantee holds for a tree that is not being rewritten during the scan. Its printed summary is capped, and the full chunk list goes to a manifest file. Deep work regroups those chunks into independently reviewable partitions such as packages, entry points, trust boundaries, or document sections. Each partition has one owner and a completion receipt. Parallel workers return immutable results; the coordinator owns deduplication and synthesis.

One representative partition is piloted before broad dispatch. This makes decomposition quality observable before overlapping or weak boundaries are multiplied across the worklist.

The worker contract records:

- tier, depth, declared maximum depth, and any named dependency;
- reviewed and deferred scope;
- evidence-backed findings with `path:line` or URL citations;
- counterevidence and suppressed candidates;
- the verification that was run.

`rlm_ledger.py` checks that contract before a result reaches synthesis. It rejects missing or empty sections, citations that are empty, template placeholders, or point at a file or line that does not exist under the scope, and depth that exceeds the declared budget or the tier ceiling. A coordinator can pass the tier and depth it dispatched, so a worker cannot loosen its own budget.

When workers are unavailable, partitions run sequentially. The output must not claim parallel confirmation or exhaustive coverage unless it happened.

### 7. Validate findings

A candidate becomes a finding only after the analysis establishes:

```text
controllable entry point
  -> validation / authorization / normalization
  -> concrete sink or broken invariant
  -> realistic impact
```

Mitigations and negative evidence are recorded. Static inspection is labeled as static, and scanner output is treated as a lead. Severity follows reachability and impact rather than pattern names.

Independent verification is selective. A fact with direct source evidence is cited and not re-checked. A high-impact claim with a single source gets one independent check through a different query, path, or test. A high-impact claim with conflicting evidence, low confidence, or a small-tier author gets one independent reviewer, from a different model family when the harness can reach one. The reviewer receives the claim and the source locations, not the first conclusion. Repeated self-opinion and confidence scores are not treated as evidence. The worker ledgers are the evidence ledger: a claim without an entry does not reach the report.

### 8. Synthesize and report

The answer leads with the outcome, then provides prioritized findings with `path:line` evidence, recommendations, verification results, coverage, deferred areas, the budget used, and every proof gap. Separately reachable instances remain separate even when they share a vulnerability family.

## Scratch state

Standard and deep work keeps concise, redacted state under `.rlm/<topic>/`. Focused lookups create no files. Previous scratch directories are never deleted automatically. Stale entries are reported so the user keeps control of deletion.

## Evals

`skills/rlm/evals/rlm_eval_cases.json` holds seven cases in six categories: focused lookup without recursion, Print Contract log slicing, depth-1 repository partitioning, depth-2 escalation for a named dependency, a small-model budget halt, and cross-family verification (one trigger case and one case where it must not trigger). Each case has a prompt, an expected output, a budget, and checkable assertions for a run with and without the skill. Each also carries `ledger_checks`, sample worker ledgers with the expected validator verdict, which the unit tests run on every commit.

## Installer design

Older versions wrote directly into Claude Code cache, registry, and settings internals. Since 3.1.0 the Claude Code path delegates all state management to supported commands:

```bash
claude plugin marketplace add adibirzu/adibirzu-plugins
claude plugin install rlm@adibirzu-plugins --scope user
```

This avoids relying on private on-disk schemas and lets Claude Code own validation, caching, enablement, and upgrades.

The other harnesses have no shared plugin command, but all of them read a skill directory. `install.sh --check` classifies eleven such directories against the skill source: `linked`, `alias`, `source`, `harness-absent`, `missing`, `stale-link`, `copy-identical`, `copy-diverged`, or `conflict`. `install.sh --sync-harnesses` then makes each present harness a symlink to the one source, so an upgrade reaches all of them at once.

The sync is built to be safe to run blind:

- It only acts when asked. `--check` never writes.
- It links harnesses whose home directory exists and creates nothing for the others.
- Two entries that resolve to the same directory are handled once, and the second is reported as an alias.
- An identical copy is replaced by a symlink. A copy that differs, in file content or in where its symlinks point, is refused unless `--backup` is given.
- If a link cannot be created after an entry was moved aside, the entry is put back.
- Anything replaced is moved to `<home>/.rlm-skill-backups/<timestamp>/`. The script contains no delete command.
- A skill source that lives inside a harness directory is recognized and left in place.
- It runs on the Bash 3.2 that ships with macOS.

## Quality gates

CI and local verification run:

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh
shellcheck install.sh
claude plugin validate . --strict
```

The tests enforce version consistency, skills-first packaging, safety invariants, and exact installer calls without touching real user configuration.
