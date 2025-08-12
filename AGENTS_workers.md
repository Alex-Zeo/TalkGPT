# Workers Module - Agent Documentation

## Module Overview
- Celery worker integration for queued transcription jobs backed by Redis.

## API Reference
- `src/workers/celery_app.py`: Celery app (broker from `REDIS_URL`)
- `src/workers/task_manager.py`: tasks
  - `transcribe_file_task(input_path, output_dir?, enhanced_analysis?, formats?, language?) -> dict`

## CLI Integration
- `status jobs` queries worker state via Celery inspect
- Future: `batch --queue` to enqueue jobs instead of inline processing

## Configuration
- Broker: `REDIS_URL` env, default `redis://localhost:6379/0`

## Notes
- Ensure ffmpeg is available in the worker image/environment

