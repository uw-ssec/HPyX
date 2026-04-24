---
description: Produce a comprehensive "brain dump" analysis of a codebase for future LLM use
argument-hint: "[codebase-name] (defaults to current repo name)"
---

Perform a comprehensive codebase analysis and produce a master knowledge document
that a future LLM can use to implement features, fix bugs, and refactor safely.

## Output location

- `{codebase-name}` = `$ARGUMENTS` if provided, else the current repo directory name.
- Write all output under `docs/codebase-analysis/{codebase-name}/`. Create the
  directory if it doesn't exist.
- Master document: `docs/codebase-analysis/{codebase-name}/CODEBASE_KNOWLEDGE.md`
- Diagrams, schemas, supplemental files: `docs/codebase-analysis/{codebase-name}/assets/`
- All file references in documentation must be **relative paths from the repo root**.

## Role

You are a **senior software architect** and **documentation specialist**. Explore
this codebase directly using available tools (file browsing, search, read-file,
repo indexing). Discover, read, and analyze only the necessary files to fully
understand the system — do not expect the full codebase to be pasted in.

## Tool usage guidelines

1. **Explore before reading**: map the structure (tree, search, listings) before opening files.
2. **Prioritize reads**: entry points, core modules, configs, DB models, major features first.
3. **Chunk intelligently**: open only what you can analyze in context; segment large files.
4. **Iterate & refine**: after each phase, decide the next most valuable files to read.
5. **State tracking**: emit/update a `STATE BLOCK` after each major phase so you can resume.

## Meta-execution rules

1. **Internal thinking first**: reason internally; expose only clean final findings.
2. **Phase-by-phase isolation**: fully complete each phase before the next.
3. **Output consistency**: reuse terminology and definitions across phases.
4. **Maximum specificity**: always reference actual file paths, class/function names, relationships.
5. **Self-containment**: the final document must stand alone — a reader without repo access
   should still understand the application.

## Phases

### Phase 1 – Initial context scan
- Explore repo structure (directories, files, languages).
- Identify: purpose/domain/users, tech stack and frameworks, architecture type.
- Decide which files to read first; read and summarize.

**Deliverable**: high-level overview — what the app is and does, main features,
business purpose of each feature, and how features relate at a high level.

### Phase 2 – System architecture deep dive
- Map all major components and interactions.
- Document: data flow (user → backend → DB → response), third-party integrations,
  cross-cutting concerns (security, logging, caching, auth).
- Identify architectural patterns and conventions.

**Deliverable**: architecture diagrams (Mermaid), component maps, data-flow descriptions.

### Phase 3 – Feature-by-feature analysis
For **each feature**:
1. Purpose and higher-level business need.
2. Technical walkthrough: entry points (routes/UI), controllers/services, models/DB,
   side effects (emails, jobs, webhooks).
3. Interactions with other features and shared modules.
4. Edge cases and hidden dependencies.

**Deliverable**: detailed per-feature breakdown, cross-feature interaction map,
explanation of how features combine to serve broader business goals.

### Phase 4 – Nuances, subtleties & gotchas
- Non-obvious design decisions and likely rationale.
- Performance optimizations or bottlenecks.
- Security implications.
- Hardcoded business rules.
- Tricky or counterintuitive code explained clearly.

**Deliverable**: "Things You Must Know Before Changing Code" section.

### Phase 5 – Technical reference & glossary
- Glossary of domain terms.
- Key classes, modules, functions with summaries.
- Database schema diagrams and relationships.
- Internal/external APIs with examples.

### Phase 6 – Final knowledge document assembly
Merge all findings into:
1. High-level overview
2. Mid-level technical notes
3. Deep reference section

Ensure clear articulation of features and business purposes, feature-to-feature
interactions, technical references for all components, diagrams, cross-references,
and completeness. Save as `docs/codebase-analysis/{codebase-name}/CODEBASE_KNOWLEDGE.md`.

## Final output requirements

- Clear, explicit language — no vague statements.
- Organized headings and bullet lists.
- Text-friendly diagrams (Mermaid, ASCII, descriptive).
- Tie every claim to a file, function, or feature.
- Produce a ready-to-use master knowledge document under `docs/codebase-analysis/{codebase-name}/`.

## Large-codebase chunking controller (appendix)

### A. Token & state discipline
- ~60% tokens for reading, ~40% for writing.
- After each phase/major section emit a `STATE BLOCK`:
  `INDEX_VERSION`, `FILE_MAP_SUMMARY` (top ~50 files), `OPEN_QUESTIONS`,
  `KNOWN_RISKS`, `GLOSSARY_DELTA`.
- If near the token limit, output `CONTINUE_REQUEST` with the latest `STATE BLOCK`.

### B. File index & prioritization (Pass 0)
1. Explore the file tree; classify: code, tests, configs, migrations, infra, docs.
2. Score importance:
   - `+` entry points, high-coupling modules, heavily tested modules, runtime-critical configs, feature modules
   - `–` vendor deps, build artifacts, large binaries
3. Emit `FILE INDEX`: `(#) PRIORITY | PATH | TYPE | LINES | HASH8 | NOTES`.

### C. Chunking strategy
- Target ~600–1200 tokens per chunk.
- Split on function/class boundaries.
- Label chunks as `CHUNK_ID = PATH#START-END#HASH8`.
- Include local headers in each chunk note.

### D. Iterative passes
- Pass 1: mapping (breadth-first)
- Pass 2: backbone deep dive
- Pass 3: feature catalog
- Pass 4: cross-cutting concerns
- Pass 5: synthesis

### E. Tests-first shortcuts
- Start from E2E/integration tests to identify features quickly.

### F. Dependency graph heuristics
- Build import/call maps; prioritize by in/out degree.

### G. Diagram rules
- Use **Mermaid** for architecture, sequence, ER diagrams.
- Keep each diagram under ~250 tokens.

### H. Stable anchors & cross-refs
- Use `[[F:path#line-range#hash]]` for file references.
- Preserve anchors when updating.

### I. Handling opaque/generated code
- Record source maps, generators, API surface.

### J. Missing artifacts & assumptions
- Maintain an `ASSUMPTIONS` table with confidence levels.

### K. Output hygiene
- Every section must be actionable.
- End sections with: Decisions/Findings, Open Questions, Next Steps.

### L. Continuation protocol
If the context limit is reached:
1. Output `CONTINUE_REQUEST`, latest `STATE BLOCK`, and `NEXT_READ_QUEUE` (ordered list of CHUNK_IDs).
2. Resume by re-ingesting the `STATE BLOCK` and continuing.

---

ARGUMENTS (codebase name, optional): $ARGUMENTS
