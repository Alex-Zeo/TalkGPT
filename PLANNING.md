# TalkGPT Planning (Living Document)

This plan aligns the architecture in `AGENTS.md` with the current repository reality and outlines a path to production readiness.

## Objectives

- Close gaps between the spec in `AGENTS.md` and the codebase
- Deliver a robust CLI-first pipeline with optional MCP/server and workers
- Keep logging, config, and Windows compatibility first-class

## Current State (High-Level)

- Core pipeline implemented and usable via CLI:
  - Preprocessing (`src/core/file_processor.py`), chunking (`src/core/chunker.py`), transcription (`src/core/transcriber.py`) with enhanced analysis mode (gap/cadence/overlap via `src/post/*`, `src/analytics/*`).
  - Logging system in `src/utils/logger.py` (Rich console + rotating file handlers + per-file logs).
  - Config system in `src/utils/config.py` with `config/default.yaml`, `config/production.yaml`.
  - CLI entry `src/cli/main.py` with commands: `transcribe`, `batch`, `config`, `status`, `analyze`, `benchmark` (some analysis/benchmark subcommands are placeholders).
  - Diagnostic scripts present (`debug_pipeline.py`, test_*.py) and an advanced pipeline script (`advanced_transcription.py`).

- Not implemented/placeholder vs AGENTS.md:
  - Workers: Celery/Redis worker pool (no `src/workers/*` implementation; no jobs API wired to CLI status).
  - MCP server: `src/mcp/` skeleton only; no server, handlers, tools, or schemas implemented.
  - Docs: Module-level `AGENTS_{module}.md` files and docs-generation script absent.
  - Packaging/deployment: Dockerfiles and multi-requirements files (`requirements-*.txt`) not present.
  - Configs: `config/cli.yaml`, `config/mcp.yaml` not present.
  - Some CLI features (`analyze`, `benchmark`, job monitoring) are placeholders.

## Gap Analysis (Spec → Repo)

1) Workers & Concurrency
- Spec: Celery worker pool, job queue, `status` and `jobs` commands reflect live workers.
- Repo: No Celery app, no task definitions, `status jobs` is placeholder.

2) MCP Server (Model Context Protocol)
- Spec: FastAPI JSON-RPC WebSocket server with tools and schemas; config in `config/mcp.yaml`.
- Repo: Empty `src/mcp/{handlers,tools,schemas}`; no server, no config.

3) CLI Features
- Spec: Rich analysis commands, benchmark, streaming; robust `config` mgmt.
- Repo: `analyze` and `benchmark` are placeholders; no streaming; `config set --save` not persisting.

4) Documentation & Discoverability
- Spec: `AGENTS_{module}.md` files + `scripts/generate_docs.py` to sync → `AGENTS.md`.
- Repo: Missing module docs and generator; `AGENTS.md` has idealized file tree that diverges from repo.

5) Deployment & Reproducibility
- Spec: Multiple requirement sets, Dockerfiles, docker-compose, MCP deployment guides.
- Repo: Single `requirements.txt`, no Dockerfiles, no compose.

6) Config Surface
- Spec: Additional `cli.yaml`, `mcp.yaml`.
- Repo: Only `default.yaml`, `production.yaml`.

7) Tests & Validation
- Spec implies unit/integration/CLI/MCP tests under `tests/` with fixtures.
- Repo: Basic top-level test scripts; `tests/` namespace empty.

8) Minor library pin & runtime consistency
- `ResourceDetector` tries `GPUtil` but it’s not pinned in `requirements.txt`.
- Some options in config vs code defaults differ but are resolved by YAML at runtime; document and standardize.

## Milestones & Scope

M0: Hygiene and Foundations (P0)
- Add missing dep pin(s) (GPUtil).
- Create `config/cli.yaml`, `config/mcp.yaml` minimal templates.
- Tighten CLI error paths; ensure Windows-safe console encoding in all code paths.
- Convert placeholder `analyze`/`benchmark` to minimal working implementations (keep scope narrow).

M1: Documentation & Discoverability (P0)
- Add `AGENTS_core.md`, `AGENTS_analytics.md`, `AGENTS_utils.md`, `AGENTS_cli.md`, `AGENTS_mcp.md`, `AGENTS_workers.md`.
- Implement `scripts/generate_docs.py` to aggregate module docs into `AGENTS.md` actual state (auto-generated section).

M2: MCP Minimal Viable Server (P0)
- Implement `src/mcp/server.py` (FastAPI + WebSocket), a minimal `transcribe_audio` tool wired to CLI command surface, JSON schemas in `src/mcp/schemas`.
- Provide `config/mcp.yaml` and a `scripts/start_mcp_server.py`.

M3: Workers (P1)
- Implement `src/workers/celery_app.py`, `src/workers/task_manager.py`, define `transcribe_chunk` and `transcribe_file` tasks, and bridge CLI batch to queue.
- Update `status jobs` to read queue state.

M4: Packaging & Deploy (P1)
- Introduce `requirements-cli.txt`, `requirements-mcp.txt`; add Dockerfiles (`Dockerfile`, `Dockerfile.mcp`) and `docker-compose.yml`.
- Basic CI workflow for lint/test.

M5: Testing & Benchmarks (P1)
- Seed `tests/` with unit tests for core modules, sanity CLI tests, an MCP smoke test; add synthetic audio fixtures.
- Turn placeholder `benchmark` into a real measurement harness reading sample files.

## Risks & Mitigations

- pyannote.audio model gating (HF token): Ensure graceful fallback remains; document token usage.
- Windows FFmpeg availability: keep preflight `doctor` and file processor checks; add error guidance.
- GPU/CT2/Torch matrix: keep pins in `requirements.txt`; add a README section mapping OS/GPU to the right wheels.

## Acceptance Criteria per Milestone

- M0: `python test_setup.py` and `python test_cli.py` pass; `talkgpt status system` runs on Windows.
- M1: Running `python scripts/generate_docs.py` updates `AGENTS.md` with an accurate repo tree and exported public APIs.
- M2: `talkgpt-mcp start --config config/mcp.yaml` serves a `transcribe_audio` tool; a sample JSON request returns a stub or real transcript file paths.
- M3: `talkgpt batch` can enqueue to Celery (optional flag); `status jobs` reflects queue state.
- M4: `docker build` succeeds for app and MCP; running compose starts services; sample transcribe works.
- M5: `pytest -q` green; `talkgpt benchmark --duration 30` produces metrics.

## Immediate Next Steps (P0)

1) Add GPUtil to `requirements.txt` (for optional GPU info).
2) Check in minimal `config/cli.yaml` and `config/mcp.yaml`.
3) Flesh out `src/cli/commands/analyze.py` and `src/cli/commands/benchmark.py` with functional implementations.
4) Create module `AGENTS_*.md` files and the `scripts/generate_docs.py` scaffold.
5) Draft `src/mcp/server.py` with one tool (`transcribe_audio`) wrapping the existing CLI path.


