# RLM v2.1 Implementation Guide

## Architecture Overview

```
/rlm invocation
    |
    v
Phase 1: Assessment
    ├── memory_recall (prior analysis?)
    ├── Glob (file count by type)
    ├── Task classification
    └── Strategy selection
    |
    v
Phase 2: Exploration
    ├── Read with limit (peek)
    ├── Grep count mode (sizing)
    ├── Write .rlm/scan_results.md
    └── memory_store (project structure)
    |
    v
Phase 3: Decomposition
    ├── Parallel Task agents (haiku/sonnet)
    │   ├── Each agent processes bounded scope
    │   └── Results collected as summaries
    └── Append to .rlm/agent_findings.md
    |
    v
Phase 4: Synthesis
    ├── Read .rlm/agent_findings.md (if compacted)
    ├── Deduplicate + cross-reference
    ├── Confidence assessment
    └── Write .rlm/synthesis.md
    |
    v
Phase 5: Output
    ├── Write rlm_*_report.md
    ├── memory_store (summary + report path)
    └── Present concise findings to user
```

## Token Budget System

### Why Token Management Matters

The main conversation has a finite context window. Every tool result (Read, Grep, sub-agent output) consumes tokens. Without discipline, an RLM analysis can fill the context with intermediate data, leaving no room for synthesis.

### Token Cost Reference

| Tool Call | Approximate Tokens | Example |
|-----------|-------------------|---------|
| `Glob("**/*.py")` on 50 files | ~500 | File discovery |
| `Grep(count mode)` on 50 files | ~500 | Sizing |
| `Grep(files_with_matches)` 20 results | ~600 | File filtering |
| `Grep(content, head_limit:50)` | ~2,000 | Targeted content |
| `Read(limit:50)` | ~2,000 | Quick peek |
| `Read(limit:200)` | ~8,000 | Section read |
| `Read(full, 500-line file)` | ~20,000 | Full file |
| `Read(full, 2000-line file)` | ~80,000 | Dangerous — use sub-agent |
| `Task(sub-agent)` result | ~500-2,000 | Summary returned |

### Budget Strategy

**Target**: Keep main conversation under 100K tokens during RLM execution.

```
Budget allocation:
- Assessment: ~5K tokens (Globs + Grep counts)
- Exploration: ~15K tokens (3-4 peeks + targeted greps)
- Decomposition: ~10K tokens (sub-agent summaries only)
- Synthesis: ~5K tokens (internal reasoning)
- Output: ~5K tokens (report to user)
Total: ~40K tokens (well within budget)
```

### Token-Saving Patterns

**Pattern 1: Count before content**
```
# Bad: Grep content on unknown result set — could return 10K lines
Grep(pattern="TODO", output_mode="content")

# Good: Count first, then fetch bounded content
Grep(pattern="TODO", output_mode="count")        # → 847 matches in 42 files
Grep(pattern="TODO", output_mode="content", head_limit=30)  # → top 30 matches
```

**Pattern 2: Delegate bulk reads**
```
# Bad: Read 2000-line file in main context (80K tokens!)
Read("/path/to/large_file.py")

# Good: Delegate to sub-agent (0 tokens in parent)
Task(subagent_type="Explore", model="haiku",
     prompt="Read /path/to/large_file.py and summarize all function signatures and their purposes")
# Returns ~500 token summary
```

**Pattern 3: Progressive narrowing**
```
# Bad: Read all files immediately
for f in files: Read(f)

# Good: Narrow first
Grep(pattern="authenticate", output_mode="files_with_matches")  # → 5 files
# Now only read the 5 relevant files
```

## Memory Integration

### MCP Memory Tools

The plugin uses two MCP tools:
- `memory_store(content, type, importance, tags)` — Persist a finding
- `memory_recall(query, limit, max_tokens)` — Retrieve past findings

### Memory Lifecycle

```
Session 1: /rlm "review project" ~/project
  → memory_store("~/project is a Flask+React app with 120 files...", type="fact", tags=["rlm","project"])
  → memory_store("Report at ~/project/rlm_review_report.md — 5 critical findings", type="fact", tags=["rlm","project","report"])

Session 2: /rlm "check security" ~/project
  → memory_recall("RLM analysis of ~/project")
  → Gets back: "Flask+React app, 120 files, previous report at rlm_review_report.md"
  → Skips structure analysis, goes straight to security grep patterns
  → Reads previous report for context on what was already found
```

### What to Store (Decision Tree)

```
Is this a structural fact about the project?
  → Yes: memory_store(type="fact", importance=7)
  Example: "Uses Clean Architecture with Repository Pattern"

Is this a critical finding?
  → Yes: memory_store(type="fact", importance=8-9)
  Example: "CRITICAL: .dockerignore excludes production backend files"

Is this about how components relate?
  → Yes: memory_store(type="relationship", importance=6)
  Example: "nginx proxies to Flask backend on port 5001"

Is this the final report location?
  → Yes: memory_store(type="fact", importance=8)
  Example: "RLM report at /path/rlm_topic_report.md"
```

## Compaction Resilience System

### The Problem

Claude Code automatically summarizes long conversations to stay within context limits. When this happens, intermediate RLM results (sub-agent findings, grep outputs) are lost. The synthesis phase has nothing to work with.

### The Solution: `.rlm/` Checkpoint Files

```
project/
├── .rlm/
│   ├── scan_results.md      ← Phase 2 output
│   ├── agent_findings.md    ← Phase 3 output (appended per agent)
│   └── synthesis.md         ← Phase 4 output
├── rlm_topic_report.md      ← Phase 5 final report
└── ...project files...
```

### How It Works

1. **Phase 2**: Write exploration results to `.rlm/scan_results.md`
2. **Phase 3**: After each sub-agent returns, append its findings to `.rlm/agent_findings.md`
3. **If compaction occurs**: Read `.rlm/agent_findings.md` to recover all sub-agent results
4. **Phase 4**: Write synthesis to `.rlm/synthesis.md`
5. **Phase 5**: Generate report from synthesis

### Checkpoint Format

```markdown
# .rlm/agent_findings.md

## Agent: Backend Analysis (sonnet)
- Found 3 issues in deploy scripts
- BYPASS_AUTH=true in scripts/deployment/deploy.sh:80
- Dead code pattern: set -e + $? check in 3 files
...

## Agent: Frontend Analysis (sonnet)
- OrdersAudit.tsx:24 hardcodes localhost:5001
- environmentConfig.ts:72 uses localhost fallback
...

## Agent: Docker Pipeline (haiku)
- .dockerignore excludes enhanced_*.py (7 patterns)
- nginx.conf missing worker_processes directive
...
```

## Sub-Agent Orchestration

### Agent Type Selection

| Analysis Type | Agent Type | Model |
|---------------|-----------|-------|
| File inventory | `Explore` | `haiku` |
| Code pattern search | `Explore` | `haiku` |
| Python code review | `python-engineer` | default |
| TypeScript review | `typescript-engineer` | default |
| Security audit | `security-compliance` | default |
| General code review | `code-reviewer` | default |
| Architecture analysis | `Explore` | `sonnet` |
| Cross-file tracing | `general-purpose` | default |

### Prompt Economy

Sub-agent prompts should be under 500 words. Structure:

```
You are analyzing [scope] for [task].

Files to examine:
- /path/to/file1.py (lines 1-200)
- /path/to/file2.py (focus on class AuthHandler)

Look for:
1. [Specific thing 1]
2. [Specific thing 2]

Return a concise summary of findings with file:line references.
Do NOT read files outside the listed scope.
```

### Parallel Launch Pattern

Always launch independent agents in a single message:

```
# Single message with 3 parallel Task calls:
Task(subagent_type="Explore", model="haiku", prompt="Inventory all .py files in backend/")
Task(subagent_type="Explore", model="haiku", prompt="Inventory all .tsx files in src/")
Task(subagent_type="Explore", model="haiku", prompt="List all deploy scripts and their purposes")
```

## Strategy Implementation Details

### Peeking
```
1. Glob for entry points (package.json, main.py, Dockerfile, etc.)
2. Read first 50 lines of each (limit:50)
3. Examine directory tree (Bash: ls -la, or Glob for top-level)
4. Decision: which deeper strategy applies?
Token cost: ~5K
```

### Grepping
```
1. Derive patterns from task description
2. Grep count mode → size the problem
3. If <100 matches: Grep content with head_limit:50
4. If >100 matches: partition by file, delegate to sub-agents
Token cost: ~2-5K
```

### Partition+Map
```
1. Identify partition boundaries (by directory or by file groups)
2. Allocate ~5-15 files per agent
3. Launch all agents in parallel (single message)
4. Each agent: reads its files, extracts findings, returns summary
5. Collect summaries, merge, dedup
Token cost: ~10K (summaries only)
```

### Summarization
```
Level 1: haiku agents summarize individual files (1-2 sentences each)
Level 2: sonnet agent summarizes groups of file summaries
Level 3: opus synthesizes into executive summary
Token cost: ~8K (progressive reduction)
```

### Iterative Refinement
```
Pass 1: Grep count + files_with_matches → identify hot spots (~3K tokens)
Pass 2: Sub-agents deep-dive on hot spots → findings (~5K tokens)
Pass 3: Targeted Read on flagged locations → verify (~5K tokens)
Pass 4: Cross-validate against tests/docs → confidence (~3K tokens)
Total: ~16K tokens
```

### Cross-Reference
```
Step 1: Grep for exports/definitions → symbol table
Step 2: Grep for imports/usages → reference table
Step 3: Sub-agent matches references to definitions
Step 4: Report orphans, cycles, violations
Token cost: ~10K
```

### Adaptive Context Selection
```
Step 1: Grep count mode per file → relevance score
Step 2: Sort files by score descending
Step 3: Read top N files within token budget
Step 4: Skip zero-score files
Token cost: ~2K (counting) + variable (reads)
```

## Error Recovery

| Error | Recovery |
|-------|----------|
| Sub-agent empty result | Broaden search patterns, check file paths |
| Too many files (>500) | Apply Adaptive Context Selection first |
| Context filling up | Delegate more to sub-agents, increase head_limit discipline |
| Compaction during analysis | Read `.rlm/` checkpoint files to recover |
| Conflicting findings | Launch verification sub-agent with targeted reads |
| Memory recall empty | First analysis of this project — proceed normally |

## Adding the Plugin to .gitignore

If using `.rlm/` in a git repository, add to `.gitignore`:

```
# RLM intermediate files
.rlm/
```

## References

- Original Paper: [Recursive Language Models (Zhang et al., 2025)](https://arxiv.org/abs/2512.24601)
- Claude Code MCP Memory: `memory_store`, `memory_recall`, `memory_forget`
- Task tool agent types: Explore, general-purpose, code-reviewer, backend-engineer, frontend-engineer, python-engineer, typescript-engineer, security-compliance
