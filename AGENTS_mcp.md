# MCP Module - Agent Documentation

## Module Overview
- Minimal HTTP-based MCP-like server exposing a `transcribe_audio` tool for agents.

## API Reference
- `POST /tools/transcribe_audio`
  - Request: `{ input_path, output_dir?, formats?, enhanced_analysis?, language? }`
  - Response: `{ input_file, output_directory, output_files, processing_time, processing_speed }`

## Configuration
- `config/mcp.yaml` (server host/port, logging level, tool toggles)

## Usage
- Local: `uvicorn src.mcp.server:app --host 0.0.0.0 --port 8000`
- Script: `python scripts/start_mcp_server.py`

## Notes
- Intended to evolve to JSON-RPC/WebSockets; current MVP uses HTTP JSON

