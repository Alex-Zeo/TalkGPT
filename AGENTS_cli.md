# CLI Module - Agent Documentation

## Module Overview
- Entry point and commands for transcription, batch, analyze, config, status, benchmark, doctor

## Commands
- `transcribe <input_path>`: single-file transcription with options
- `batch <input_dir>`: multi-file processing or enqueue to workers (future)
- `analyze speakers|quality`: run advanced analyses
- `config show|set|validate`: manage config
- `status system|jobs`: hardware and queue status
- `benchmark`: quick performance measurement
- `doctor`: preflight checks

## Configuration
- `config/cli.yaml` overrides; CLI flags take highest precedence

## Notes
- On Windows terminals, UTF-8 may require fallback; `utils.encoding.force_utf8_stdio` is used

