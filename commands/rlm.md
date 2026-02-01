---
description: Process arbitrarily long contexts using Recursive Language Model (RLM) techniques — enhanced for Claude Opus 4.5
disable-model-invocation: false
---

You are implementing **RLM v2.1** — the Recursive Language Model paradigm optimized for Claude Opus 4.5 with memory persistence, token-aware processing, and multi-agent orchestration.

## Core Paradigm

Context is an **external environment variable**, not prompt content. Never paste large content — reference by file path. Explore programmatically with tools. Decompose recursively through sub-agents.

## Principles

1. **Context as Variable**: Reference files by path. Never inline large content into prompts or sub-agent instructions.
2. **Token Budget Awareness**: Every Read/Grep result consumes conversation tokens. Use `limit`, `head_limit`, `offset` to control input size. Estimate: **1 line ≈ 40 tokens**; a 2000-line read ≈ 80K tokens.
3. **Memory Persistence**: Store key findings in `memory_store` so they survive conversation compaction and are available in future sessions. Store the final report path so it can be recalled.
4. **Intermediate File Storage**: Write intermediate results to `.rlm/` directory in the project root. This survives compaction and can be read back cheaply.
5. **Sub-agent Economy**: Each Task agent gets its own context. Keep sub-agent prompts under 500 words. Pass file paths + line ranges, never content. Use `model: "haiku"` for scanning tasks.
6. **Progressive Narrowing**: Start broad (Glob counts, Grep counts), narrow (Grep content on top hits), deep-dive (Read targeted sections). Never start with a full file read.

## Token Budget Management

Before starting, estimate the scope:

```
Files: Glob count → N files
Lines: Bash "wc -l" on key files or "find ... | xargs wc -l"
Estimated tokens: N_lines × 40
```

### Budget Rules

| Action | Token Cost | When to Use |
|--------|-----------|-------------|
| `Glob` | ~10 tokens/file in result | Always safe, use freely |
| `Grep` count mode | ~10 tokens/file | Use to size the problem |
| `Grep` files_with_matches | ~30 tokens/file | Use to find relevant files |
| `Grep` content, `head_limit: 50` | ~2K tokens | Use for targeted extraction |
| `Read` with `limit: 100` | ~4K tokens | Use for peeking |
| `Read` full file (500 lines) | ~20K tokens | Use only for critical files |
| `Task` sub-agent | 0 tokens in parent (own context) | Use for bulk analysis |

**Key rule**: If you need to process >200 lines from a file, delegate to a Task sub-agent. This keeps the main conversation context lean.

### Grep Discipline

Always use `head_limit` on Grep results to prevent flooding:
- `head_limit: 20` for discovery (which files match?)
- `head_limit: 50` for extraction (what are the matches?)
- `head_limit: 100` maximum for detailed analysis
- Use `output_mode: "count"` first to size the result set before fetching content

### Read Discipline

- **Peek**: `limit: 50-100` — understand file structure
- **Section**: `limit: 200, offset: N` — read specific area
- **Full file**: Only if file is <300 lines AND critical to the task
- **Large files**: ALWAYS delegate to sub-agent with line range

## Memory Integration

Use `memory_store` and `memory_recall` MCP tools to persist knowledge:

### What to Store

| When | What to Store | Memory Type | Importance |
|------|--------------|-------------|------------|
| After assessment | Project structure summary | `fact` | 7 |
| After each finding | Individual finding with location | `fact` | 8 |
| After synthesis | Executive summary of analysis | `fact` | 9 |
| After report | Report file path | `fact` | 8 |
| Architecture discovery | Module/service map | `entity` | 7 |
| Cross-reference | Key dependency relationships | `relationship` | 6 |

### Memory Recall

At the START of every `/rlm` invocation:
1. Call `memory_recall` with query about the project/directory being analyzed
2. If previous analysis exists, use it as starting context — don't re-analyze known structure
3. Focus new analysis on what's changed or wasn't covered

### Example Memory Flow

```
# Start: Check what we already know
memory_recall(query="RLM analysis of /path/to/project")

# During: Store findings as they emerge
memory_store(content="Project uses Python backend on port XXXX, React frontend via reverse proxy on port YYYY", type="fact", importance=7, tags=["rlm", "project-name", "architecture"])

# End: Store report location
memory_store(content="RLM report for project-name at /path/to/rlm_topic_report.md - found 10 issues, 3 critical", type="fact", importance=9, tags=["rlm", "project-name", "report"])
```

## Compaction Resilience

Claude Code compacts long conversations. Protect intermediate work:

1. **Write to `.rlm/` directory**: Create `<project>/.rlm/` and write intermediate findings there
   - `.rlm/scan_results.md` — Phase 2 exploration results
   - `.rlm/agent_findings.md` — Phase 3 sub-agent results (append each)
   - `.rlm/synthesis.md` — Phase 4 combined analysis
2. **Final report**: Write to `rlm_<topic>_report.md` in project root
3. **After compaction**: Read `.rlm/` files to recover context instead of re-analyzing
4. **Memory backup**: Key findings also in `memory_store` for cross-session persistence

## Strategies (7)

### 1. Peeking — Structure discovery
Read first 50-100 lines of entry points. Examine directory tree. Decide next strategy.

### 2. Grepping — Pattern filtering
`count` mode first → `files_with_matches` → `content` with `head_limit`. Chain broad → narrow.

### 3. Partition + Map — Parallel decomposition
Divide by file/directory/line-range. Launch parallel Task agents (single message, multiple calls). Each agent: focused prompt + file paths. Combine with dedup.

### 4. Summarization — Hierarchical reduction
Level 1 (haiku agents): file summaries → Level 2 (sonnet): group summaries → Level 3 (opus): global synthesis.

### 5. Iterative Refinement — Multi-pass
Pass 1: Broad scan → Pass 2: Deep dive on hot spots → Pass 3: Verify findings → Pass 4: Cross-validate.

### 6. Cross-Reference — Dependency tracing
Extract symbols → build dependency graph → trace usage chains → find orphans/cycles.

### 7. Adaptive Context Selection — Smart budgeting
Score files by relevance (grep count / line count). Read highest-scoring first. Skip zero-match files.

## Multi-Model Dispatch

| Sub-task | Model | Agent Type |
|----------|-------|------------|
| File listing, counting | `haiku` | `Explore` |
| Code analysis | `sonnet` | `Explore` or domain-specific |
| Security/quality review | default | `code-reviewer` or `security-compliance` |
| Complex multi-step | default | `general-purpose` |
| Final synthesis | default (opus) | Main conversation |

## Execution Pipeline

### Phase 1: Assessment
1. `memory_recall` — check for prior analysis of this project
2. `Glob` — count files by type
3. Classify task: search | analysis | audit | comparison | summarization
4. Select strategy combination from matrix below

### Phase 2: Exploration
1. Peek at entry points (`Read` with `limit: 50`)
2. `Grep` count mode to size relevant content
3. Write structure summary to `.rlm/scan_results.md`
4. `memory_store` project structure

### Phase 3: Decomposition
1. Launch parallel Task agents (haiku/sonnet for scanning, default for analysis)
2. Each agent writes its findings; main context receives summary only
3. Append sub-agent results to `.rlm/agent_findings.md`

### Phase 4: Synthesis
1. Read `.rlm/agent_findings.md` if context was compacted
2. Deduplicate, cross-reference, rank by severity
3. Assess confidence (High/Medium/Low)
4. Write to `.rlm/synthesis.md`

### Phase 5: Output
1. Write `rlm_<topic>_report.md` with structured findings
2. `memory_store` executive summary + report path
3. Present concise summary to user with key findings

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

## Output Format

```markdown
# RLM Analysis: <Title>

## Executive Summary
<2-3 sentences>

## Findings
### [CRITICAL/HIGH/MEDIUM/LOW] Title
- **Location**: file:line
- **Description**: What
- **Impact**: Why it matters
- **Confidence**: High/Medium/Low

## Statistics
<Files analyzed, patterns found, tokens consumed>

## Recommendations
<Prioritized actions>
```

## Best Practices

- **Start with counts**: Glob count + Grep count before any content reads
- **Delegate bulk reads**: >200 lines → Task sub-agent
- **Cap all Grep**: Always use `head_limit`
- **Write intermediate files**: `.rlm/` directory for compaction resilience
- **Store in memory**: Key findings survive across sessions
- **Parallel agents**: All independent agents in single message
- **Lean prompts**: Sub-agent prompts <500 words, file paths only
- **Report always**: Write `rlm_*_report.md` for non-trivial analyses

---

Based on "Recursive Language Models" (Zhang, Kraska, Khattab 2025) — arXiv:2512.24601
RLM Plugin v2.1.0 — Enhanced for Claude Opus 4.5
