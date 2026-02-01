---
description: Process arbitrarily long contexts using Recursive Language Model (RLM) techniques — enhanced for Claude Opus 4.5
disable-model-invocation: false
---

You are implementing **RLM v3.0** — the Recursive Language Model paradigm optimized for Claude Opus 4.5 with dual execution modes, memory persistence, git-aware incremental analysis, token-aware processing, and multi-agent orchestration.

## Core Paradigm

Context is an **external environment variable**, not prompt content. Never paste large content — reference by file path. Explore programmatically with tools. Decompose recursively through sub-agents.

## Principles

1. **Context as Variable**: Reference files by path. Never inline large content into prompts or sub-agent instructions.
2. **Token Budget Awareness**: Every Read/Grep result consumes conversation tokens. Use `limit`, `head_limit`, `offset` to control input size. Estimate: **1 line ≈ 40 tokens**; a 2000-line Read ≈ 80K tokens.
3. **Memory Persistence**: Use `memory_store`/`memory_recall` MCP tools. Store findings, report paths, project structure. Recall prior analysis at start of every invocation.
4. **Compaction Resilience**: Write intermediate results to timestamped `.rlm/<date>/` directory. These survive conversation compaction.
5. **Sub-agent Economy**: Each Task agent gets its own context window. Keep prompts <500 words. Pass file paths + line ranges, never content. Use `model: "haiku"` for scanning.
6. **Progressive Narrowing**: Glob counts → Grep counts → Grep content (capped) → targeted Read. Never start with full file reads.

---

## Phase 0: Mode Detection

**FIRST**: Determine execution mode from the task description.

### Quick Scan Mode
**Triggers**: Task starts with "find", "where is", "list", "show me", "how many", "which files", "what is"
**Pipeline**: Phase 1 (lite) → Phase 2 → direct answer. No checkpoints, no report file, no sub-agents unless needed.
**Token budget**: ~5-10K tokens total.
**Rules**:
- Skip memory_store (only memory_recall)
- Skip `.rlm/` checkpoints
- Use Grep directly (with head_limit)
- Return inline answer, no report file
- Only escalate to Deep Audit if initial Grep reveals >100 matches or complexity

### Deep Audit Mode
**Triggers**: Task contains "review", "audit", "analyze", "compare", "summarize", "check", "security", "refactor", "assess", "examine", or is a complex multi-part request.
**Pipeline**: Full Phase 0-5 with all checkpoints, memory, sub-agents, and report file.
**Token budget**: ~30-60K tokens total.

If uncertain, default to Deep Audit.

---

## Directory Pruning Defaults

**ALWAYS** exclude these directories from Glob and Grep operations unless the user explicitly asks to include them:

```
.git, node_modules, .venv, venv, __pycache__, .pytest_cache,
dist, build, .next, .nuxt, .cache, .parcel-cache,
coverage, .nyc_output, .tox, .eggs, *.egg-info,
vendor (if not primary code), bower_components, jspm_packages
```

Apply via Grep `glob` parameter or by scoping Glob patterns to `src/`, `lib/`, `app/`, `backend/`, `frontend/` etc.

When using Glob, prefer specific patterns like `src/**/*.ts` over `**/*.ts` to naturally exclude dependency directories.

---

## Binary File Skip List

**NEVER** attempt to Read or Grep these file extensions:

```
Images: .jpg, .jpeg, .png, .gif, .bmp, .ico, .svg, .webp, .tiff
Fonts: .woff, .woff2, .ttf, .otf, .eot
Compiled: .pyc, .pyo, .class, .o, .so, .dylib, .dll, .exe, .wasm
Archives: .zip, .tar, .gz, .bz2, .xz, .rar, .7z, .jar, .war
Media: .mp3, .mp4, .wav, .avi, .mov, .flv, .webm
Data: .sqlite, .db, .bin, .dat, .pkl, .npy, .h5, .parquet
Maps: .map (source maps)
Locks: package-lock.json, yarn.lock, pnpm-lock.yaml, Pipfile.lock, poetry.lock
```

When using Grep, apply `type` parameter (e.g., `type: "py"`, `type: "ts"`, `type: "js"`) to automatically filter to text source files.

---

## Git-Aware Incremental Analysis

**At the start of Deep Audit mode**, check for incremental analysis opportunity:

### Step 1: Check Memory for Prior Analysis
```
memory_recall(query="RLM analysis of <project-path>")
```
If prior analysis exists, extract: last commit SHA, report path, project structure.

### Step 2: Check Git Status
```
Bash: git -C <project-path> log --oneline -1   → current HEAD SHA
Bash: git -C <project-path> diff --name-only <last-sha>..HEAD  → changed files
```

### Step 3: Decide Mode
- If **no prior analysis** or **>50% files changed**: Full analysis (all phases)
- If **<50% files changed**: Incremental mode — analyze only changed files + their direct importers
- If **0 files changed**: Report "No changes since last analysis at <report-path>"

### Step 4: Store Current Commit
After analysis, store:
```
memory_store(content="RLM analysis of <path> at commit <SHA>. Report: <report-path>. Files: <count>. Findings: <count>",
             type="fact", importance=8, tags=["rlm", "<project-name>", "commit"])
```

### Incremental Report Format
When running incrementally, use differential output:
```markdown
## Changes Since Last Analysis (commit abc123..def456)
### New Issues (3)
...
### Resolved Issues (1)
...
### Unchanged Issues (5)
(see previous report at rlm_topic_report.md)
```

---

## CLAUDE.md Awareness

In Phase 1, check if target directory contains a `CLAUDE.md` file:

```
Glob: <project-path>/CLAUDE.md
```

If found, read it (`limit: 200`) and extract:
- Project type and tech stack
- Key directories and their purposes
- Build/test commands
- Known patterns and conventions

Use this to **inform strategy selection** — skip structure discovery if CLAUDE.md already describes it. This saves an entire Peek phase worth of tokens.

---

## Token Budget Management

### Budget Rules

| Action | Token Cost | When to Use |
|--------|-----------|-------------|
| `Glob` | ~10 tokens/file | Always safe, use freely |
| `Grep` count mode | ~10 tokens/file | Size the problem first |
| `Grep` files_with_matches | ~30 tokens/file | Find relevant files |
| `Grep` content, `head_limit: 50` | ~2K tokens | Targeted extraction |
| `Read` with `limit: 100` | ~4K tokens | Peeking |
| `Read` full file (500 lines) | ~20K tokens | Only critical files <300 lines |
| `Task` sub-agent | 0 tokens in parent | Bulk analysis (>200 lines) |

**Key rule**: >200 lines from a file → delegate to Task sub-agent.

### Grep Discipline
- `head_limit: 20` for discovery
- `head_limit: 50` for extraction
- `head_limit: 100` maximum
- Always use `output_mode: "count"` first to size result set

### Read Discipline
- **Peek**: `limit: 50-100`
- **Section**: `limit: 200, offset: N`
- **Full file**: Only if <300 lines AND critical
- **Large files**: ALWAYS delegate to sub-agent

### Adaptive Sub-Agent Budgets

Before launching a sub-agent, estimate its scope:
```
Agent scope = number_of_files × avg_lines_per_file
If agent scope > 50K lines: split into 2+ smaller agents
If agent scope > 500 files: split by directory
```

Target: each sub-agent handles 5-15 files or 5-30K lines. Never assign a single agent more than 500 files.

---

## Background Scanning (Large Repos)

If Phase 1 Glob count reveals **>500 files**:

1. Launch inventory agents with `run_in_background: true`:
```
Task(subagent_type="Explore", model="haiku", run_in_background=true,
     prompt="List all source files in <path>/src with line counts. Group by directory.")
```

2. Continue Phase 1 assessment in main conversation while agents run.

3. Collect results with `TaskOutput` or `Read` on the output_file before Phase 3.

This reduces wall-clock time by overlapping inventory with assessment.

---

## Memory Integration

### Memory Recall (Start of Every Invocation)
```
memory_recall(query="RLM analysis of <project-path>", max_tokens=2000)
```
If results found: use prior structure, skip redundant discovery, check for incremental mode.

### What to Store

| When | Content | Type | Importance |
|------|---------|------|------------|
| After Phase 1 | Project structure + tech stack | `fact` | 7 |
| After findings | Critical findings with locations | `fact` | 8 |
| After report | Executive summary + report path + commit SHA | `fact` | 9 |
| Architecture | Module/service relationships | `relationship` | 6 |

### Memory Tags
Always tag with: `["rlm", "<project-directory-name>"]` plus topic tags.

---

## Compaction Resilience: Timestamped Checkpoints

Create `.rlm/<YYYY-MM-DD>/` directory in project root for each analysis:

```
project/
├── .rlm/
│   ├── 2026-02-01/
│   │   ├── scan_results.md      ← Phase 2 output
│   │   ├── agent_findings.md    ← Phase 3 output (append per agent)
│   │   └── synthesis.md         ← Phase 4 output
│   └── 2026-01-25/              ← previous run (auto-cleanup if >7 days old)
├── rlm_topic_report.md          ← Phase 5 final report
└── .gitignore                   ← should contain .rlm/
```

### Cleanup Rule
Before creating new checkpoint directory, delete `.rlm/` subdirectories older than 7 days:
```
Bash: find <project>/.rlm -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +
```

### Recovery After Compaction
If conversation was compacted mid-analysis, read checkpoint files to resume:
```
Read: <project>/.rlm/<date>/agent_findings.md
```

### Auto-Gitignore Check
After creating `.rlm/`, check if `.gitignore` exists and contains `.rlm/`. If not, append it:
```
Bash: grep -q "^\.rlm/$" <project>/.gitignore 2>/dev/null || echo ".rlm/" >> <project>/.gitignore
```

---

## Sub-Agent FINAL Protocol

All sub-agents MUST return findings in this structured format. Include this instruction in every sub-agent prompt:

```
Return your findings in this EXACT format:

## FINDINGS: <count>

### [CRITICAL/HIGH/MEDIUM/LOW] <Title>
- **File**: <path>:<line>
- **Evidence**: <what you found>
- **Impact**: <why it matters>

(repeat for each finding)

## SUMMARY
<1-2 sentence summary of analysis>

Do NOT include reasoning, exploration steps, or intermediate thoughts in the output.
Only report confirmed findings with evidence.
```

This ensures:
- Machine-parseable sub-agent results
- Clean deduplication across agents
- No intermediate reasoning leaking into findings
- Consistent severity classification

---

## Strategies (7)

### 1. Peeking — Structure discovery
Read first 50-100 lines of entry points. Examine directory tree. Decide next strategy.

### 2. Grepping — Pattern filtering
`count` mode first → `files_with_matches` → `content` with `head_limit`. Chain broad → narrow. Use `type` parameter to filter to source files.

### 3. Partition + Map — Parallel decomposition
Divide by file/directory/line-range. Launch parallel Task agents (single message, multiple calls). Apply adaptive budgets (max 500 files / 50K lines per agent). Combine with dedup.

### 4. Summarization — Hierarchical reduction
Level 1 (haiku agents): file summaries → Level 2 (sonnet): group summaries → Level 3 (opus): global synthesis.

### 5. Iterative Refinement — Multi-pass
Pass 1: Broad scan → Pass 2: Deep dive on hot spots → Pass 3: Verify findings → Pass 4: Cross-validate.

### 6. Cross-Reference — Dependency tracing
Extract symbols → build dependency graph → trace usage chains → find orphans/cycles.

### 7. Adaptive Context Selection — Smart budgeting
Score files by relevance (grep count / line count). Read highest-scoring first. Skip zero-match files. Skip binary extensions.

---

## Multi-Model Dispatch

| Sub-task | Model | Agent Type |
|----------|-------|------------|
| File inventory, counting | `haiku` | `Explore` |
| Code analysis, patterns | `sonnet` | `Explore` or domain-specific |
| Security/quality review | default | `code-reviewer` / `security-compliance` |
| Complex multi-step | default | `general-purpose` |
| Final synthesis | default (opus) | Main conversation |

Domain-specific agents: `python-engineer`, `typescript-engineer`, `frontend-engineer`, `backend-engineer`

---

## Execution Pipeline

### Quick Scan Pipeline (5-10K tokens)

1. `memory_recall` — check for known project structure
2. `Grep` with `head_limit: 50` — find matches for query
3. `Read` with `limit: 100` — examine top hits
4. Return inline answer with `file:line` citations
5. Done. No checkpoints, no report file.

### Deep Audit Pipeline (30-60K tokens)

#### Phase 1: Assessment
1. `memory_recall` — check for prior analysis + last commit SHA
2. Check for `CLAUDE.md` — read if exists (`limit: 200`)
3. Git check — is incremental mode possible?
4. `Glob` — count files by type (exclude pruned directories)
5. If >500 files: launch background inventory agents
6. Classify task: search | analysis | audit | comparison | summarization
7. Select strategy combination from matrix

#### Phase 2: Exploration
1. Peek at entry points (`Read` with `limit: 50`)
2. `Grep` count mode to size relevant content (exclude binary types)
3. Create `.rlm/<YYYY-MM-DD>/` directory
4. Write structure summary to `.rlm/<date>/scan_results.md`
5. `memory_store` project structure

#### Phase 3: Decomposition
1. Calculate adaptive budgets (max 500 files / 50K lines per agent)
2. Launch parallel Task agents with FINAL protocol in prompts
3. Collect results — each agent returns structured findings
4. Append each agent's findings to `.rlm/<date>/agent_findings.md`
5. If sub-agent returns empty: retry with broader scope or escalate model (haiku → sonnet)

#### Phase 4: Synthesis
1. Read `.rlm/<date>/agent_findings.md` (if context was compacted)
2. Parse structured findings from all agents
3. Deduplicate by file:line location
4. Cross-reference and validate
5. Rank by severity: CRITICAL > HIGH > MEDIUM > LOW
6. Assess confidence: High (multi-agent confirmed) / Medium (single agent) / Low (inferred)
7. Write to `.rlm/<date>/synthesis.md`

#### Phase 5: Output
1. Write `rlm_<topic>_report.md` with structured findings
2. If incremental: use differential format (new/resolved/unchanged)
3. `memory_store` executive summary + report path + commit SHA
4. Clean up old checkpoints (>7 days)
5. Auto-add `.rlm/` to `.gitignore` if needed
6. Present concise summary to user

---

## Strategy Selection Matrix

| Task Type | Primary | Secondary |
|-----------|---------|-----------|
| "Find X" | Grepping | Peek |
| "Analyze X" | Partition+Map | Iterative Refinement |
| "Summarize X" | Summarization | Peek |
| "Audit X" | Iterative Refinement | Cross-Reference |
| "Compare X vs Y" | Partition+Map | Cross-Reference |
| "Debug X" | Grepping | Iterative Refinement |
| "Review X" | Iterative Refinement | Partition+Map |

---

## Output Formats

### Quick Scan Output
Inline answer with file:line citations. No report file.

### Deep Audit Output
```markdown
# RLM Analysis: <Title>
**Date**: YYYY-MM-DD | **Commit**: <sha> | **Mode**: Full/Incremental | **Files Analyzed**: N

## Executive Summary
<2-3 sentences>

## Findings
### [CRITICAL/HIGH/MEDIUM/LOW] Title
- **Location**: file:line
- **Description**: What
- **Impact**: Why it matters
- **Confidence**: High/Medium/Low

## Statistics
Files scanned: N | Findings: N | Critical: N | High: N

## Recommendations
<Prioritized actions>
```

### Incremental Output
```markdown
# RLM Incremental Analysis: <Title>
**Date**: YYYY-MM-DD | **Commit Range**: abc123..def456 | **Changed Files**: N

## New Issues (N)
...
## Resolved Issues (N)
...
## Unchanged Issues (N)
(see full report: rlm_topic_report.md)
```

---

## Best Practices

- **Start with counts**: Glob count + Grep count before content reads
- **Prune directories**: Always exclude .git, node_modules, venv, dist, build
- **Skip binaries**: Never read .jpg, .png, .pyc, .zip, .lock files
- **Delegate bulk reads**: >200 lines → Task sub-agent
- **Cap all Grep**: Always use `head_limit`
- **Adaptive budgets**: Max 500 files / 50K lines per sub-agent
- **FINAL protocol**: All sub-agents use structured output format
- **Timestamped checkpoints**: `.rlm/<date>/` for compaction resilience
- **Memory persistence**: Store findings + commit SHA for incremental mode
- **Parallel agents**: All independent agents in single message
- **Background agents**: >500 files → background inventory
- **CLAUDE.md first**: Read project docs before structure discovery
- **Auto-gitignore**: Ensure `.rlm/` is in .gitignore

---

Based on "Recursive Language Models" (Zhang, Kraska, Khattab 2025) — arXiv:2512.24601
RLM Plugin v3.0.0 — Enhanced for Claude Opus 4.5
