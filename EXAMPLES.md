# RLM v3.0 Skill Examples

## Quick Scan Mode Examples

### Example 1: Find Specific Pattern
```
/rlm "find all TODO comments" src/
```
**Mode**: Quick Scan (keyword: "find")
**Pipeline**: Grep count → Grep content (head_limit:50) → inline answer
**Tokens**: ~3K

### Example 2: Locate a Definition
```
/rlm "where is the authentication middleware defined?" .
```
**Mode**: Quick Scan (keyword: "where is")
**Pipeline**: Grep files_with_matches → Read top hit (limit:100) → answer with file:line
**Tokens**: ~5K

### Example 3: Count Files
```
/rlm "how many test files are there?" .
```
**Mode**: Quick Scan (keyword: "how many")
**Pipeline**: Glob count → inline answer
**Tokens**: ~1K

---

## Deep Audit Mode Examples

### Example 4: Full Project Review
```
/rlm "Do a full review of the project, check deployment pipeline issues, and fix them. Create a report." ~/projects/my-app
```
**Mode**: Deep Audit (keyword: "review")
**Strategy**: Iterative Refinement + Partition+Map

**What RLM Does**:
1. **Phase 0**: Deep Audit mode detected
2. **Phase 1**: memory_recall → check CLAUDE.md → git check → Glob count
3. **Phase 2**: Peek Dockerfile, deploy scripts, configs. Grep for error patterns
4. **Phase 3**: Launch parallel agents:
   - `code-reviewer` (sonnet): review deploy scripts
   - `Explore` (haiku): inventory backend files
   - `Explore` (haiku): inventory frontend files
5. **Phase 4**: Collect FINAL-format findings, dedup, rank
6. **Phase 5**: Write `rlm_deployment_report.md`, store in memory

### Example 5: Security Audit
```
/rlm "audit for OWASP top 10 vulnerabilities" backend/
```
**Mode**: Deep Audit (keyword: "audit")
**Strategy**: Iterative Refinement + Cross-Reference

**What RLM Does**:
1. **Pass 1 — Scan** (haiku agents):
   - Grep for SQL patterns (type: "py")
   - Grep for auth patterns
   - Grep for input handling patterns
   - Grep for hardcoded secrets
2. **Pass 2 — Analyze** (sonnet agents):
   - `security-compliance`: analyze SQL injection vectors
   - `code-reviewer`: review auth flows
3. **Pass 3 — Verify**: targeted Read on flagged locations
4. **Output**: Severity-ranked security report

### Example 6: Incremental Re-Analysis
```
/rlm "review what changed since the last analysis" .
```
**Mode**: Deep Audit, Incremental
**What happens**:
1. `memory_recall` → finds prior analysis at commit abc123
2. `git diff abc123..HEAD` → 5 files changed
3. Analyzes only those 5 files + their importers
4. Compares findings to stored prior findings
5. Produces differential report:
```markdown
## Changes Since Last Analysis (abc123..def456)
### New Issues (2)
### Resolved Issues (1)
### Unchanged Issues (5)
```

### Example 7: Architecture Analysis
```
/rlm "analyze the architecture, map module dependencies, identify coupling issues" src/
```
**Mode**: Deep Audit (keyword: "analyze")
**Strategy**: Cross-Reference + Partition+Map

**What RLM Does**:
1. CLAUDE.md check → learns project is React + TypeScript
2. Grep for `import`/`export` patterns (type: "ts")
3. Sub-agents extract symbol tables per directory
4. Build dependency graph from symbol tables
5. Report: coupling metrics, circular deps, god modules

### Example 8: Large Monorepo (>500 Files)
```
/rlm "review code quality across the entire repository" ~/projects/large-monorepo
```
**Mode**: Deep Audit with Background Scanning

**What RLM Does**:
1. Glob reveals 2,500 files
2. **Background agents** (haiku): inventory src/, lib/, packages/
3. Directory pruning: skips node_modules, dist, .git (removes ~15K files from scope)
4. Binary filtering: skips .png, .jpg, .woff, .map (removes ~500 files)
5. **Adaptive budgets**: splits remaining 2K files into 8 agents (~250 files each)
6. Each agent uses FINAL protocol for structured output
7. Synthesis deduplicates across 8 agent outputs

---

## Mode Escalation Example

### Quick Scan Escalates to Deep Audit
```
/rlm "find all hardcoded URLs" src/
```
1. Starts as Quick Scan (keyword: "find")
2. Grep count reveals 847 matches across 142 files
3. **Escalates** to Deep Audit (>100 matches detected)
4. Partition+Map: splits 142 files into parallel agents
5. Each agent extracts URLs with context
6. Synthesis categorizes: production URLs, localhost, external APIs

---

## CLAUDE.md Optimization Example

```
/rlm "summarize what this codebase does" ~/projects/new-repo
```

**Without CLAUDE.md**: Full Peek phase (read 10+ files to understand structure) → ~15K tokens
**With CLAUDE.md**: Read CLAUDE.md (200 lines, ~4K tokens) → skip structure discovery → save ~10K tokens

---

## Best Practices

### 1. Use Quick Scan for Simple Queries
**Good**: `/rlm "find all TODO comments" src/`
**Overkill**: `/rlm "audit all TODO comments for security implications" src/`

### 2. Provide Context Paths
**Good**: `/rlm "analyze auth" ~/project/src/auth`
**Wasteful**: `/rlm "analyze auth"` (scans entire working directory)

### 3. Use Incremental for Repeated Analysis
**Good**: `/rlm "review what changed" .` (analyzes only diff)
**Wasteful**: `/rlm "full review" .` (re-analyzes everything)

### 4. Specify Output Requirements
**Good**: "Create a report with findings ranked by severity"
**Vague**: "Find problems"

## Troubleshooting

**Issue**: Quick Scan returns too few results
**Solution**: Add "analyze" or "review" to trigger Deep Audit mode

**Issue**: Analysis misses files in node_modules
**Solution**: Directory pruning excludes node_modules by default. Specify "include node_modules" in task.

**Issue**: Report is empty
**Solution**: Check that target path exists and contains source files matching expected extensions.

**Issue**: Incremental mode doesn't work
**Solution**: Requires git repository and prior RLM analysis stored in memory. First run is always full.
