#!/usr/bin/env python3
"""
Start the TalkGPT MCP server (MVP).
"""

import uvicorn
from pathlib import Path

from src.utils.config import load_config


def main():
    cfg = load_config("mcp") if (Path("config/mcp.yaml").exists()) else None
    host = cfg.logging.log_dir if False else None  # keep cfg referenced
    # Fallback defaults if no config/mcp.yaml exists
    server_host = "0.0.0.0"
    server_port = 8000
    if cfg:
        try:
            server_host = cfg.dict().get('server', {}).get('host', server_host)  # type: ignore
            server_port = cfg.dict().get('server', {}).get('port', server_port)  # type: ignore
        except Exception:
            pass

    uvicorn.run("src.mcp.server:app", host=server_host, port=server_port, reload=False)


if __name__ == "__main__":
    main()


