"""Unified entry point for SafeSearch module.

Usage:
    python -m src.safe_search --mode api    → Start FastAPI server on port 8000
    python -m src.safe_search --mode mcp    → Start MCP stdio server
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="SafeSearch — 语义搜索与避雷推荐")
    parser.add_argument(
        "--mode",
        choices=["api", "mcp"],
        default="api",
        help="Run mode: 'api' for REST server, 'mcp' for MCP stdio server",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="API server host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port (default: 8000)",
    )
    args = parser.parse_args()

    if args.mode == "api":
        import uvicorn

        uvicorn.run(
            "src.safe_search.api:app",
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        from .mcp_server import main as mcp_main

        mcp_main()


if __name__ == "__main__":
    main()
