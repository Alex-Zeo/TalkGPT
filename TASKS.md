# TalkGPT Tasks (Backlog)

Prioritized tasks to close gaps between `AGENTS.md` and current implementation.

## Legend
- P0: Critical now
- P1: Important next
- P2: Nice-to-have

## P0

- Requirements
  - [ ] Add `GPUtil==1.4.0` to `requirements.txt` (used by `src/core/resource_detector.py`).
    - [ ] Edit `requirements.txt`, add `GPUtil==1.4.0` under utilities.
    - [ ] Verify import path: ensure `ResourceDetector` import guard remains optional.
    - [ ] Smoke test: run `python test_setup.py` to confirm hardware detection works when no GPU present.
    - [ ] DoD: Repo installs cleanly; `status system` prints GPU info when available without exceptions.

- Configs
  - [ ] Add `config/cli.yaml` minimal with CLI defaults (formats, log level, word_timestamps for enhanced flows).
    - [ ] Create `config/cli.yaml` mirroring a subset of `default.yaml` focused on CLI overrides (output.formats, logging.level, output.word_timestamps).
    - [ ] Document priority order in `AGENTS_cli.md` (CLI args > env TALKGPT_* > ~/.talkgpt/config.yaml > project `config/cli.yaml` > defaults).
    - [ ] DoD: `talkgpt config show --quiet` reflects `config/cli.yaml` when passed via `--config`.
  - [ ] Add `config/mcp.yaml` minimal with host/port and tool toggles.
    - [ ] Include server.host, server.port, tools.transcribe_audio.enabled and logging level.
    - [ ] DoD: MCP server can read `config/mcp.yaml` and start with these values.

- CLI Completeness
  - [ ] Replace placeholders in `src/cli/commands/analyze.py` with real implementations.
    - Speakers
      - [ ] Accept `input_path`, `output_path`, `format=json|rttm`.
      - [ ] Use `SpeakerAnalyzer.perform_diarization()`; map to summary dict; write JSON.
      - [ ] For `rttm`, call `SpeakerAnalyzer.save_diarization_result(..., format='rttm')`.
      - [ ] Return dict: counts, paths.
      - [ ] DoD: `talkgpt analyze speakers file.wav -o out.json --format json` produces a valid JSON with counts.
    - Quality
      - [ ] Accept `threshold` and propagate to `UncertaintyDetector`.
      - [ ] Write JSON with analysis, flagged segments, metrics.
      - [ ] DoD: `talkgpt analyze quality file.wav --threshold -1.0 -o out.json` works and returns metrics.
  - [ ] Replace placeholder in `src/cli/commands/benchmark.py` with a real benchmark.
    - [ ] Inputs: `--duration`, `--sample-files`.
    - [ ] Procedure: iterate samples (short), run file processing + transcribe first chunk only, collect processing_speed and timing; skip pyannote.
    - [ ] Output: JSON/console with average speed, CPU/RAM via psutil.
    - [ ] DoD: `talkgpt benchmark --duration 30` prints meaningful metrics without crashing on Windows.
  - [ ] Implement `config set --save` to persist to file (extend `ConfigManager.save_config`).
    - [ ] Implement saving to `config/local.yaml` or a user-specified output path.
    - [ ] Update CLI: `talkgpt config set key value --save` writes and confirms.
    - [ ] DoD: Re-running `config show` reflects saved changes.

- Docs
  - [ ] Create module docs (`AGENTS_*.md`).
    - [ ] `AGENTS_core.md`: responsibilities of file_processor, chunker, transcriber; public APIs.
    - [ ] `AGENTS_analytics.md`: timing_analyzer, uncertainty_detector, speaker_analyzer.
    - [ ] `AGENTS_utils.md`: config, logger, env_loader.
    - [ ] `AGENTS_cli.md`: command structure, options, examples.
    - [ ] `AGENTS_mcp.md`: planned server, tools, schemas (initial minimal tool).
    - [ ] `AGENTS_workers.md`: intended Celery tasks and topology (planned for P1).
    - [ ] DoD: Files exist with the standard sections (Overview, API, Config, Usage, Testing, Troubleshooting).
  - [ ] Add `scripts/generate_docs.py` to aggregate module docs into `AGENTS.md`.
    - [ ] Define markers in `AGENTS.md` (e.g., `<!-- START:GENERATED -->` / `<!-- END:GENERATED -->`).
    - [ ] Script concatenates module docs into the generated section.
    - [ ] DoD: Running the script updates `AGENTS.md` without destroying manual sections.

- MCP (minimal)
  - [ ] Implement `src/mcp/server.py` (HTTP MVP) exposing `POST /tools/transcribe_audio`.
    - [ ] Pydantic request: input_path, output_dir (optional), output_format list.
    - [ ] Response: output file paths, timings, basic stats.
    - [ ] Wire to `transcribe_single_file` (import directly, not shelling out).
  - [ ] Define request/response models in `src/mcp/schemas`.
    - [ ] `schemas/requests.py`: TranscribeAudioRequest.
    - [ ] `schemas/responses.py`: TranscribeAudioResponse.
  - [ ] `scripts/start_mcp_server.py` (uvicorn entry), respect `config/mcp.yaml`.
  - [ ] DoD: `uvicorn src.mcp.server:app` starts; `curl` to endpoint returns JSON with paths.

## P1

- Workers
  - [ ] Implement `src/workers/celery_app.py` + `task_manager.py` with tasks for `transcribe_file` and optional `transcribe_chunk`.
  - [ ] Add `talkgpt status jobs` to query worker/queue (Redis) and show counts.
    - [ ] Choose Redis broker/url via env; add to config.
    - [ ] Task: load model on worker init, process file paths, persist outputs.
    - [ ] CLI: `batch` gains `--queue` flag to enqueue tasks instead of inline processing.
    - [ ] Status: query Celery inspect or Redis keys for queued/active/completed counts.
    - [ ] DoD: With Redis + worker running, `talkgpt batch --queue` enqueues and `status jobs` shows activity.

- Deployment
  - [ ] Split requirements: `requirements-cli.txt`, `requirements-mcp.txt` from baseline.
  - [ ] Add `Dockerfile`, `Dockerfile.mcp`, `docker-compose.yml` with GPU/CPU notes.
    - [ ] Extract CLI-only and MCP-only dependencies from `requirements.txt`.
    - [ ] Dockerfile (CPU): install ffmpeg, pins for torch; build wheel cache; set OpenMP envs.
    - [ ] Dockerfile.mcp: minimal FastAPI/uvicorn image with only needed deps.
    - [ ] Compose: services for app, mcp server, redis; volumes for data.
    - [ ] DoD: `docker compose up` builds and runs; sample transcription succeeds.

- Tests
  - [ ] Seed `tests/unit/` for utils/core modules; `tests/cli/` for CLI smoke; `tests/mcp/` for MCP ping & tool.
  - [ ] Add basic fixtures (tiny audio, short speech sample).
  - [ ] Wire `pytest` in CI and local run.
    - [ ] Core unit tests: chunking boundaries, gap stats, config validators.
    - [ ] CLI smoke: `--help`, `status system --quiet`, `config show --quiet`.
    - [ ] MCP: start test app in thread, post to `/tools/transcribe_audio` with a fixture.
    - [ ] GitHub Actions: matrix (ubuntu-latest, windows-latest), cache pip, run pytest.
    - [ ] DoD: CI green; tests stable on Windows and Linux.

## P2

- Streaming mode
  - [ ] `talkgpt stream` (microphone capture + incremental transcription via faster-whisper with VAD).
    - [ ] Select audio lib (sounddevice/pyaudio) and add optional extra.
    - [ ] Implement simple VAD or use faster-whisper’s VAD options.
    - [ ] Print live transcript lines with timestamps; persist optional SRT.
    - [ ] DoD: `talkgpt stream` runs and prints live text on supported OS.

- Enhanced outputs
  - [ ] Unify legacy `analytics/enhanced_output.py` with `output/md_writer.py` path under a single interface.
    - [ ] Define a single OutputGenerator interface; keep compatibility for both paths.
    - [ ] Deprecate duplicate code; ensure tests cover outputs.
    - [ ] DoD: One code path, same file outputs as before.

- Documentation polish
  - [ ] Expand `AGENTS.md` with current repo tree and generated API signatures.
    - [ ] Update file tree snapshot to actual repo; include function/class indexes from module docs.
    - [ ] DoD: `AGENTS.md` accurately reflects the codebase and APIs.

## Quality Gates

- `python test_setup.py` passes on Windows without GPU.
- `talkgpt status system` shows device and recommendations.
- `talkgpt transcribe input.wav -o out --enhanced-analysis` produces enhanced markdown and JSON.
- MCP `transcribe_audio` returns file paths for outputs.
 - Docker images build; compose up succeeds; Celery path validated in local run.

## Notes

- Maintain Windows-first environment guards (OpenMP vars) at all entry points.
- Keep pyannote optional; ensure graceful fallbacks where not installed.


