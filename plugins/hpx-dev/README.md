# hpx-dev

Claude Code development toolkit for [HPyX](https://github.com/uw-ssec/HPyX) — HPX Python bindings built with Nanobind. Provides deep HPX knowledge, binding patterns, build system guidance, benchmarking, and code review for contributors.

- **Version:** 0.1.0
- **License:** BSD-3-Clause
- **Repository:** https://github.com/uw-ssec/HPyX

## What's Included

This plugin ships three subagents and six auto-activating skills. There are no slash commands, hooks, or MCP servers.

### Agents (`agents/`)

| Agent | When to use |
|---|---|
| `hpx-api-explorer` | Search `vendor/hpx/` to discover HPX C++ APIs and signatures suitable for Python binding. |
| `binding-reviewer` | Review C++/Python binding code (`src/*.cpp`, `src/hpyx/`) for GIL safety, type correctness, and pattern adherence. |
| `benchmark-engineer` | Write, run, and analyze `pytest-benchmark` performance tests (HPX vs NumPy, thread scaling, regression checks). |

Invoke via the `Agent` tool — agents are selected automatically based on task context, or can be requested by name.

### Skills (`skills/`)

Skills auto-activate when their trigger phrases appear in conversation.

| Skill | Triggers on topics like |
|---|---|
| `hpx-architecture` | HPX components, parallel algorithms, futures, AGAS, execution policies, `vendor/hpx` |
| `nanobind-patterns` | Writing Nanobind bindings, type conversions, ndarray bindings, `src/*.cpp` patterns |
| `add-binding` | Scaffolding a new end-to-end HPX binding (C++ + header + Python wrapper + tests + CMake) |
| `gil-management` | Python 3.13 free-threading, `gil_scoped_acquire/release`, thread safety, callback segfaults |
| `build-system` | CMake, scikit-build-core, pixi, `nanobind_add_module`, build/link/RPATH errors |
| `benchmarking` | `pytest-benchmark`, `benchmarks/` directory, thread scaling, HPX vs Python/NumPy comparisons |

Three of the skills (`hpx-architecture`, `nanobind-patterns`, `benchmarking`) ship reference documents in a `references/` subdirectory for deeper context.

## Installation

From the HPyX repository root, this plugin lives at `plugins/hpx-dev/`. With Claude Code's plugin support, point at the directory:

```bash
# From the Claude Code UI or settings, add a local plugin source pointing at:
# /absolute/path/to/HPyX/plugins/hpx-dev
```

Or reference it through a marketplace / plugin registry entry that resolves to this directory.

Once the plugin is enabled, the agents and skills register automatically — no restart required beyond a new Claude Code session.

## Directory Layout

```
hpx-dev/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   ├── hpx-api-explorer.md
│   ├── binding-reviewer.md
│   └── benchmark-engineer.md
└── skills/
    ├── hpx-architecture/
    │   ├── SKILL.md
    │   └── references/
    ├── nanobind-patterns/
    │   ├── SKILL.md
    │   └── references/
    ├── add-binding/SKILL.md
    ├── gil-management/SKILL.md
    ├── build-system/SKILL.md
    └── benchmarking/
        ├── SKILL.md
        └── references/
```

## Contributing

Contributions follow the HPyX project conventions. When modifying plugin components:

- Keep agent and skill frontmatter valid (see existing files for the expected shape).
- Use kebab-case for directory and file names.
- Run the `plugin-dev:plugin-validator` agent after changes to catch regressions.

## License

BSD-3-Clause — see the root HPyX repository for the full license text.
