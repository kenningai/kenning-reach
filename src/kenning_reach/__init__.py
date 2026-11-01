from . import server
import asyncio
import argparse
import logging
import os

import fastmcp

from .utils import process_config

logger = logging.getLogger("kenning_reach")
logger.setLevel(logging.INFO)

def main():
    """Main entry point for the package."""
    parser = argparse.ArgumentParser(description='Kenning Reach — category-1 conscious experience substrate (MCP server)')
    parser.add_argument('--db-url', default=None, help='Neo4j connection URL')
    parser.add_argument('--username', default=None, help='Neo4j username')
    parser.add_argument('--password', default=None, help='Neo4j password')
    parser.add_argument("--database", default=None, help="Neo4j database name")
    parser.add_argument("--namespace", default=None, help="Tool namespace prefix")
    parser.add_argument("--transport", default=None, help="Transport type (stdio, sse, streamable-http)")
    parser.add_argument("--server-host", default=None, help="HTTP host (default: 127.0.0.1)")
    parser.add_argument("--server-port", type=int, default=None, help="HTTP port (default: 8000)")
    parser.add_argument("--server-path", default=None, help="HTTP path (default: /mcp/)")
    parser.add_argument("--allow-origins", default=None, help="Comma-separated list of allowed CORS origins")
    parser.add_argument("--allowed-hosts", default=None, help="Comma-separated list of allowed hosts for DNS rebinding protection")
    parser.add_argument("--read-timeout", type=int, default=None, help="Read query timeout in seconds (default: 30)")
    parser.add_argument("--schema-sample-size", type=int, default=None, help="Schema sample size for APOC meta schema (default: 1000)")

    args = parser.parse_args()

    # FastMCP asks PyPI for a newer release every time it draws the startup
    # banner. Off unless the operator sets FASTMCP_CHECK_FOR_UPDATES.
    if "FASTMCP_CHECK_FOR_UPDATES" not in os.environ:
        fastmcp.settings.check_for_updates = "off"

    config = process_config(args)
    asyncio.run(server.main(**config))


# Optionally expose other important items at package level
__all__ = ["main", "server"]
