# Utils Module - Agent Documentation

## Module Overview
- Configuration, logging, environment loading, encoding helpers

## API Reference
- `src/utils/config.py`
  - `load_config(name="default", **overrides) -> TalkGPTConfig`
  - `get_config() -> TalkGPTConfig`
  - `ConfigManager.save_config(config, filename)`
- `src/utils/logger.py`
  - `TalkGPTLogger` (Rich console, per-file logs, rotating files)
  - `get_logger(name)`, `get_file_logger(filename)`, `setup_logging(config)`
- `src/utils/env_loader.py`
  - `.ensure_environment_loaded()` sets OpenMP/encoding vars and .env

## Configuration
- YAML files in `config/`; env overrides via `TALKGPT_*`

## Usage Examples
- CLI and scripts call `load_config("default")` and `setup_logging()` before pipeline

## Implementation Details
- Rich logging for console and files; JSON format optional
- Global logger instance for consistent handlers

## Testing
- Validate `save_config`, env overrides, log setup without duplicate handlers

## Troubleshooting
- On Windows terminals, ensure UTF-8 output; use `utils.encoding` where needed

