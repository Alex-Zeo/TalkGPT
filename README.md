# TalkGPT

AI-powered, modular transcription and analytics pipeline built around faster-whisper (CTranslate2) with smart chunking, speed-optimized preprocessing, optional speaker/uncertainty analysis, rich logging, a friendly CLI, and an MCP server for agent workflows.

## Highlights

- Cross-platform CPU/GPU with automatic resource detection
- Speed-optimized preprocessing (silence trimming, atempo speed-up)
- Smart chunking with configurable overlap for accuracy at boundaries
- Parallel processing with configurable worker count
- Advanced analytics: speaker overlap, timing/cadence, uncertainty
- Production-grade logging (console + per-file rotating logs)
- Flexible outputs: SRT, JSON, TXT, CSV
- Clean CLI and optional MCP server for AI-agent integrations

## Architecture Overview

Core modules and responsibilities:

- Core: file processing, chunking, transcription (faster-whisper)
- Analytics: timing/cadence windows, overlap detection, uncertainty flags
- Utils: configuration management, logging setup, environment loading
- CLI: user-facing commands for transcription, batch, analyze, config, status, benchmark
- MCP: lightweight HTTP MCP-like server exposing tools for agents
- Workers: Celery integration for queued jobs (optional/extendable)

Directory structure (truncated to major components):

```
TalkGPT/
  config/                  # YAML config (defaults, CLI, MCP, production)
  docs/                    # Docs (API, CLI, deployment, examples, mcp)
  scripts/                 # Utilities (generate docs, start MCP server)
  src/
    analytics/             # Timing, uncertainty, speaker diarization
    cli/                   # CLI main and commands
    core/                  # File processing, chunking, transcriber
    mcp/                   # MCP server, handlers, tools, schemas
    output/                # Markdown writer and output helpers
    post/                  # Segmenter, cadence, overlap, assembler
    utils/                 # Config, logging, encoding, env loader
    workers/               # Celery app and task manager
  tests/                   # Unit, CLI, MCP tests
  AGENTS*.md               # In-repo architecture and module docs
```

For deeper, module-by-module details see `AGENTS.md` and the per-module docs (`AGENTS_core.md`, `AGENTS_cli.md`, `AGENTS_utils.md`, `AGENTS_workers.md`, `AGENTS_mcp.md`, `AGENTS_analytics.md`).

## Requirements

- Python 3.9–3.11 (recommend 3.10)
- FFmpeg available on PATH
- Optional GPU: CUDA 12.x recommended for speed; CPU-only is supported

Dependency pins (summarized):

- torch/torchaudio aligned with CUDA; ctranslate2 per CUDA matrix
- faster-whisper 1.1.1
- pyannote.audio 3.2.x (optional, for speaker overlap)
- pydub, librosa, ffmpeg-python, rich, tqdm

See `AGENTS.md` Dependencies and Compatibility Matrix for exact pins and rationale.

## Quick Start

1) Create environment

```bash
python -m venv .venv
# PowerShell (Windows)
.\.venv\Scripts\Activate.ps1
# bash/zsh (macOS/Linux)
source .venv/bin/activate
```

2) Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-cli.txt  # CLI extras
```

3) Verify setup

```bash
python -c "from faster_whisper import WhisperModel; import torch; m=WhisperModel('large-v3', device='cuda' if torch.cuda.is_available() else 'cpu', compute_type='float16' if torch.cuda.is_available() else 'int8'); print(m)"
```

4) First transcription

```bash
# Single file → default outputs (e.g., SRT/JSON/TXT)
python -m src.cli.main transcribe path/to/audio.wav --output ./results

# Or using the convenience script if wired in your environment
# talkgpt transcribe path/to/audio.wav --output ./results
```

FFmpeg tip (Windows): install from https://ffmpeg.org, then add `ffmpeg.exe` to PATH.

## CLI Usage

All commands support `--help` for options.

```bash
# Single file transcription
talkgpt transcribe input.wav --output results/ --format srt,json --speed-multiplier 1.6

# Batch folder processing
talkgpt batch ./audio --output ./results --workers 4

# Real-time/streaming (where supported)
talkgpt stream --input-device microphone --output-format live

# Configuration
talkgpt config show
talkgpt config set processing.speed_multiplier 2.0
talkgpt config validate

# Status and benchmarking
talkgpt status system
talkgpt benchmark --duration 60 --sample-files ./tests/fixtures

# Analytics
talkgpt analyze speakers input.wav --output speaker_report.json
talkgpt analyze quality input.wav --confidence-threshold 0.85
```

Global options (examples): `--config`, `--log-level`, `--workers`, `--gpu/--cpu`, `--profile`.

## Configuration

Configuration is layered (highest → lowest):

1. CLI flags
2. Environment variables `TALKGPT_*`
3. User file `~/.talkgpt/config.yaml`
4. Project file `./config/*.yaml`
5. Built-in defaults

Common keys:

- `processing.speed_multiplier` (default 1.5)
- `processing.chunk_size` (seconds, default 30)
- `processing.overlap_duration` (seconds, default 5)
- `processing.max_workers` (auto by default)
- `transcription.model_size` (e.g., large-v3)
- `transcription.compute_type` (float16, int8_float16, etc.)
- `output.formats` ([srt, json, txt, csv])

Files:

- `config/default.yaml`, `config/production.yaml`, `config/cli.yaml`, `config/mcp.yaml`

## Logging

Implemented via `src/utils/logger.py` with Rich console and per-file rotating logs.

- Levels: DEBUG, INFO (default), WARNING, ERROR
- Console is concise; detailed per-input logs saved alongside outputs
- Multiprocessing-safe pattern to avoid handler duplication
- Recommend `--log-level DEBUG` for investigations

Best practices:

- Use INFO for lifecycle events; WARNING for recoverable issues; ERROR for exceptions
- Avoid noisy DEBUG in hot loops unless diagnosing a specific problem
- Log file paths and timings; never log secrets or large payloads

## Advanced Analytics

Optional analysis steps can mark speaker overlaps, compute timing/cadence windows, and flag uncertain segments. Enable via CLI flags or config; see `AGENTS_analytics.md` for API-level details.

## MCP Server (for agents)

Start a minimal HTTP server exposing a `transcribe_audio` tool to agents.

```bash
# Development
uvicorn src.mcp.server:app --host 0.0.0.0 --port 8000

# Or convenience script
python scripts/start_mcp_server.py
```

Key endpoint:

- `POST /tools/transcribe_audio` → `{ input_path, output_dir?, formats?, enhanced_analysis?, language? }`

Server configuration: `config/mcp.yaml`.

## Docker

Container builds are provided for the pipeline and MCP server.

```bash
# Build core image
docker build -t talkgpt:core -f Dockerfile .

# Build MCP image
docker build -t talkgpt:mcp -f Dockerfile.mcp .

# Compose (example)
docker compose up -d
```

Ensure the image includes FFmpeg and the correct Torch/CT2 wheels for your target CUDA or CPU-only environment.

## Development

Run tests:

```bash
pytest -q
```

Helpful scripts:

```bash
python scripts/generate_docs.py     # aggregates module AGENTS docs
python scripts/start_mcp_server.py  # runs the MCP server
```

Coding standards:

- Prefer simple, maintainable solutions; avoid duplication (reuse utilities)
- Follow logging and error-handling patterns from `src/utils/logger.py`
- Keep files focused; refactor if files grow overly large

## Troubleshooting

- FFmpeg not found: install and ensure it is on PATH
- GPU not detected: verify NVIDIA drivers + CUDA; otherwise run CPU mode (`--cpu`)
- PyTorch/CT2 wheel mismatch: align with the CUDA compatibility matrix in `AGENTS.md`
- Windows console encoding: use UTF-8; see `src/utils/encoding.py`

## Security & Privacy

- Never commit API keys or secrets; prefer environment variables
- Avoid logging sensitive data
- Pin model weights to a specific snapshot/commit for reproducibility (see `AGENTS.md`)

## License

TBD. Add your project license here.


