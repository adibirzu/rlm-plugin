# Changelog

All notable changes to the RLM Plugin are documented in this file.

## [3.1.0] - 2026-07-04

### Added
- Canonical `skills/rlm/SKILL.md` workflow with focused, standard, and deep analysis modes
- Explicit prompt-injection, secret-redaction, authorization, and scope boundaries
- Portable fallbacks when memory, local knowledge, network access, or sub-agents are unavailable
- Standard-library regression tests for packaging, safety invariants, version consistency, and installer behavior
- GitHub Actions CI for unit tests, shell syntax, ShellCheck, secret-pattern checks, and strict Claude plugin validation

### Changed
- Replaced private cache/registry mutation in `install.sh` with supported `claude plugin` marketplace/install/uninstall commands
- Migrated the canonical workflow from legacy `commands/` to the skills-first plugin layout
- Reworked mode selection to consider scope and risk rather than keyword matching alone
- Made deep-audit checkpoints opt-in and non-destructive; stale checkpoints are never automatically removed
- Kept dependency lockfiles and text-based assets available to security and supply-chain analysis
- Updated documentation and examples to use the namespaced `/rlm:rlm` invocation

### Removed
- Hard-coded model names and assumptions about specific agent, memory, and task-output APIs
- Automatic checkpoint deletion and direct writes to Claude Code internal state files

## [3.0.0] - 2026-02-01

### Added
- **E1: Dual Execution Modes** — Quick Scan (~5K tokens) for simple queries; Deep Audit (~30-60K tokens) for comprehensive analysis
- **E2: Smart Directory Pruning** — Auto-excludes .git, node_modules, dist, build, __pycache__, and 15+ noise directories
- **E3: Git-Aware Incremental Analysis** — Stores commit SHA in memory; on re-analysis, diffs against prior commit and analyzes only changed files
- **E4: Timestamped Checkpoints** — Uses `.rlm/<YYYY-MM-DD>/` directories with auto-cleanup of entries older than 7 days
- **E5: CLAUDE.md Awareness** — Reads project-level CLAUDE.md to skip redundant structure discovery
- **E6: FINAL Output Protocol** — Structured sub-agent output format for reliable deduplication and severity classification
- **E7: Background Scanning** — Repos with >500 files use `run_in_background: true` for inventory agents
- **E8: Adaptive Sub-Agent Budgets** — Auto-splits work when scope exceeds 500 files or 50K lines per agent
- **E9: Binary File Filtering** — Skips 30+ binary extensions from Read and Grep operations
- Mode escalation (Quick Scan -> Deep Audit when >100 matches detected)
- Strategy selection matrix mapping task types to optimal strategies
- Multi-model dispatch table (haiku for scanning, sonnet for analysis, opus for synthesis)

### Changed
- Complete rewrite of core skill file (commands/rlm.md) — now 460 lines with all 9 enhancements
- Restructured execution pipeline into Phase 0-5 for Deep Audit
- README rewritten with full feature documentation
- IMPLEMENTATION.md rewritten with dual-mode architecture diagrams
- EXAMPLES.md rewritten with Quick Scan, Deep Audit, incremental, and escalation examples

## [2.1.1] - 2026-02-01

### Fixed
- Removed 5 project-specific references (paths, ports, filenames) from example files
- Fixed version mismatch in EXAMPLES.md (was v2.0, now v2.1)
- Added JSON validation and backup to install.sh before modifying settings.json

## [2.1.0] - 2026-02-01

### Added
- Memory integration via MCP tools (memory_store/memory_recall)
- Token budget management system with per-tool cost estimates
- Compaction resilience via .rlm/ checkpoint files
- Portable install.sh with install/uninstall support
- Git repository initialization
- Duplicate settings key cleanup (rlm@local removed)

### Changed
- Enhanced skill file with memory lifecycle, token discipline, Grep/Read limits
- Updated README with migration instructions (tarball + git methods)
- Added IMPLEMENTATION.md with detailed architecture documentation

## [2.0.0] - 2026-01-31

### Added
- Enhanced strategies from RLM paper (7 strategies)
- Multi-model orchestration (haiku/sonnet/opus dispatch)
- Sub-agent parallel launch patterns
- Progressive narrowing pipeline

### Changed
- Upgraded from basic RLM to paper-aligned implementation

## [1.0.0] - 2026-01-31

### Added
- Initial RLM plugin for Claude Code
- Basic peeking, grepping, partition+map, summarization strategies
- Task sub-agent spawning for recursive decomposition
