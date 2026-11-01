import argparse
import os
import re
import logging
from pathlib import Path
from typing import Any, Union

logger = logging.getLogger("kenning_reach")
logger.setLevel(logging.INFO)

# ── Cypher Query Loading ─────────────────────────────────────

_CYPHER_DIR = Path(__file__).parent / "_cypher"
_CYPHER_CACHE: dict[str, str] = {}


def load_cypher(name: str, **replacements: str) -> str:
    """Load a Cypher query from _cypher/{name}.cypher.

    Caches file contents on first load. Template placeholders use
    __name__ convention (e.g. __label__, __rel_type__) to avoid
    collision with Cypher's {prop: $param} syntax.

    Args:
        name: Query filename without .cypher extension
        **replacements: Template substitutions (key → __key__ in file)
    """
    if name not in _CYPHER_CACHE:
        path = _CYPHER_DIR / f"{name}.cypher"
        _CYPHER_CACHE[name] = path.read_text()
    query = _CYPHER_CACHE[name]
    for key, value in replacements.items():
        query = query.replace(f"__{key}__", value)
    return query


# ── Utilities ────────────────────────────────────────────────

def format_namespace(namespace: str) -> str:
    """Format namespace by ensuring it ends with a hyphen if not empty."""
    if namespace:
        if namespace.endswith("-"):
            return namespace
        else:
            return namespace + "-"
    else:
        return ""
    
def _is_write_query(query: str) -> bool:
    """Check if the query is a write query."""
    return (
        re.search(r"\b(MERGE|CREATE|INSERT|SET|DELETE|REMOVE|ADD)\b", query, re.IGNORECASE)
        is not None
    )


def _value_sanitize(d: Any, list_limit: int = 128) -> Any:
    """
    Sanitize the input dictionary or list.

    Sanitizes the input by removing embedding-like values,
    lists with more than 128 elements, that are mostly irrelevant for
    generating answers in a LLM context. These properties, if left in
    results, can occupy significant context space and detract from
    the LLM's performance by introducing unnecessary noise and cost.

    Sourced from: https://github.com/neo4j/neo4j-graphrag-python/blob/main/src/neo4j_graphrag/schema.py#L88

    Parameters
    ----------
    d : Any
        The input dictionary or list to sanitize.
    list_limit : int
        The limit for the number of elements in a list.

    Returns
    -------
    Any
        The sanitized dictionary or list.
    """
    if isinstance(d, dict):
        new_dict = {}
        for key, value in d.items():
            if isinstance(value, dict):
                sanitized_value = _value_sanitize(value)
                if (
                    sanitized_value is not None
                ):  # Check if the sanitized value is not None
                    new_dict[key] = sanitized_value
            elif isinstance(value, list):
                if len(value) < list_limit:
                    sanitized_value = _value_sanitize(value)
                    if (
                        sanitized_value is not None
                    ):  # Check if the sanitized value is not None
                        new_dict[key] = sanitized_value
                # Do not include the key if the list is oversized
            else:
                new_dict[key] = value
        return new_dict
    elif isinstance(d, list):
        if len(d) < list_limit:
            return [
                _value_sanitize(item) for item in d if _value_sanitize(item) is not None
            ]
        else:
            return None
    else:
        return d


def process_config(args: argparse.Namespace) -> dict[str, Union[str, int, None]]:
    """
    Process the command line arguments and environment variables to create a config dictionary. 
    This may then be used as input to the main server function.
    If any value is not provided, then a warning is logged and a default value is used, if appropriate.

    Parameters
    ----------
    args : argparse.Namespace
        The command line arguments.

    Returns
    -------
    config : dict[str, str]
        The configuration dictionary.
    """

    config = dict()

    # parse uri
    if args.db_url is not None:
        config["neo4j_uri"] = args.db_url
    else:
        if os.getenv("NEO4J_URL") is not None:
            config["neo4j_uri"] = os.getenv("NEO4J_URL")
        else:
            if os.getenv("NEO4J_URI") is not None:
                config["neo4j_uri"] = os.getenv("NEO4J_URI")
            else:
                logger.warning("Warning: No Neo4j connection URL provided. Using default: bolt://localhost:7687")
                config["neo4j_uri"] = "bolt://localhost:7687"
    
    # parse username
    if args.username is not None:
        config["neo4j_user"] = args.username
    else:
        if os.getenv("NEO4J_USERNAME") is not None:
            config["neo4j_user"] = os.getenv("NEO4J_USERNAME")
        else:
            logger.warning("Warning: No Neo4j username provided. Using default: neo4j")
            config["neo4j_user"] = "neo4j"
    
    # parse password
    if args.password is not None:
        config["neo4j_password"] = args.password
    else:
        if os.getenv("NEO4J_PASSWORD") is not None:
            config["neo4j_password"] = os.getenv("NEO4J_PASSWORD")
        else:
            logger.warning("Warning: No Neo4j password provided. Using default: password")
            config["neo4j_password"] = "password"
    
    # parse database
    if args.database is not None:
        config["neo4j_database"] = args.database
    else:
        if os.getenv("NEO4J_DATABASE") is not None:
            config["neo4j_database"] = os.getenv("NEO4J_DATABASE")
        else:
            logger.warning("Warning: No Neo4j database provided. Using default: neo4j")
            config["neo4j_database"] = "neo4j"
    
    # parse transport
    if args.transport is not None:
        config["transport"] = args.transport
    else:
        if os.getenv("NEO4J_TRANSPORT") is not None:
            config["transport"] = os.getenv("NEO4J_TRANSPORT")
        else:
            logger.warning("Warning: No transport type provided. Using default: stdio")
            config["transport"] = "stdio"
    
    # parse server host
    if args.server_host is not None:
        if config["transport"] == "stdio":
            logger.warning("Warning: Server host provided, but transport is `stdio`. The `server_host` argument will be set, but ignored.")
        config["host"] = args.server_host
    else:
        if os.getenv("NEO4J_MCP_SERVER_HOST") is not None:
            if config["transport"] == "stdio":
                logger.warning("Warning: Server host provided, but transport is `stdio`. The `NEO4J_MCP_SERVER_HOST` environment variable will be set, but ignored.")
            config["host"] = os.getenv("NEO4J_MCP_SERVER_HOST")
        elif config["transport"] != "stdio":
            logger.warning("Warning: No server host provided and transport is not `stdio`. Using default server host: 127.0.0.1")
            config["host"] = "127.0.0.1"
        else:
            logger.info("Info: No server host provided and transport is `stdio`. `server_host` will be None.")
            config["host"] = None
     
    # parse server port
    if args.server_port is not None:
        if config["transport"] == "stdio":
            logger.warning("Warning: Server port provided, but transport is `stdio`. The `server_port` argument will be set, but ignored.")
        config["port"] = args.server_port
    else:
        if os.getenv("NEO4J_MCP_SERVER_PORT") is not None:
            if config["transport"] == "stdio":
                logger.warning("Warning: Server port provided, but transport is `stdio`. The `NEO4J_MCP_SERVER_PORT` environment variable will be set, but ignored.")
            config["port"] = int(os.getenv("NEO4J_MCP_SERVER_PORT"))
        elif config["transport"] != "stdio":
            logger.warning("Warning: No server port provided and transport is not `stdio`. Using default server port: 8000")
            config["port"] = 8000
        else:
            logger.info("Info: No server port provided and transport is `stdio`. `server_port` will be None.")
            config["port"] = None
    
    # parse server path
    if args.server_path is not None:
        if config["transport"] == "stdio":
            logger.warning("Warning: Server path provided, but transport is `stdio`. The `server_path` argument will be set, but ignored.")
        config["path"] = args.server_path
    else:
        if os.getenv("NEO4J_MCP_SERVER_PATH") is not None:
            if config["transport"] == "stdio":
                logger.warning("Warning: Server path provided, but transport is `stdio`. The `NEO4J_MCP_SERVER_PATH` environment variable will be set, but ignored.")
            config["path"] = os.getenv("NEO4J_MCP_SERVER_PATH")
        elif config["transport"] != "stdio":
            logger.warning("Warning: No server path provided and transport is not `stdio`. Using default server path: /mcp/")
            config["path"] = "/mcp/"
        else:
            logger.info("Info: No server path provided and transport is `stdio`. `server_path` will be None.")
            config["path"] = None
    
    # parse allow origins
    if args.allow_origins is not None:
        # Handle comma-separated string from CLI
     
        config["allow_origins"] = [origin.strip() for origin in args.allow_origins.split(",") if origin.strip()]

    else:
        if os.getenv("NEO4J_MCP_SERVER_ALLOW_ORIGINS") is not None:
            # split comma-separated string into list
            config["allow_origins"] = [
                origin.strip() for origin in os.getenv("NEO4J_MCP_SERVER_ALLOW_ORIGINS", "").split(",") 
                if origin.strip()
            ]
        else:
            logger.info(
                "Info: No allow origins provided. Defaulting to no allowed origins."
            )
            config["allow_origins"] = list()

    # parse allowed hosts for DNS rebinding protection
    if args.allowed_hosts is not None:
        # Handle comma-separated string from CLI
        config["allowed_hosts"] = [host.strip() for host in args.allowed_hosts.split(",") if host.strip()]
      
    else:
        if os.getenv("NEO4J_MCP_SERVER_ALLOWED_HOSTS") is not None:
            # split comma-separated string into list
            config["allowed_hosts"] = [
                host.strip() for host in os.getenv("NEO4J_MCP_SERVER_ALLOWED_HOSTS", "").split(",") 
                if host.strip()
            ]
        else:
            logger.info(
                "Info: No allowed hosts provided. Defaulting to secure mode - only localhost and 127.0.0.1 allowed."
            )
            config["allowed_hosts"] = ["localhost", "127.0.0.1"]

    # namespace configuration
    if args.namespace is not None:
        logger.info(f"Info: Namespace provided for tools: {args.namespace}")
        config["namespace"] = args.namespace
    else:
        if os.getenv("NEO4J_NAMESPACE") is not None:
            logger.info(f"Info: Namespace provided for tools: {os.getenv('NEO4J_NAMESPACE')}")
            config["namespace"] = os.getenv("NEO4J_NAMESPACE")
        else:
            logger.info("Info: No namespace provided for tools. No namespace will be used.")
            config["namespace"] = ""

    # parse read timeout
    if args.read_timeout is not None:
        config["read_timeout"] = args.read_timeout
    else:
        if os.getenv("NEO4J_READ_TIMEOUT") is not None:
            config["read_timeout"] = int(os.getenv("NEO4J_READ_TIMEOUT"))
        else:
            logger.info("Info: No read timeout provided. Using default: 30 seconds")
            config["read_timeout"] = 30

    # parse schema sample size
    if args.schema_sample_size is not None:
        config["schema_sample_size"] = args.schema_sample_size
    else:
        if os.getenv("NEO4J_SCHEMA_SAMPLE_SIZE") is not None:
            config["schema_sample_size"] = int(os.getenv("NEO4J_SCHEMA_SAMPLE_SIZE"))
        else:
            logger.info("Info: No schema sample size provided. Using default: 1000")
            config["schema_sample_size"] = 1000

    # parse stateless_http (streamable-http transport only)
    # Default False: stateful mode issues Mcp-Session-Id, required by OpenWebUI
    # and compatible with n8n / Claude Code.
    if os.getenv("NEO4J_MCP_STATELESS_HTTP") is not None:
        config["stateless_http"] = os.getenv("NEO4J_MCP_STATELESS_HTTP", "false").lower() == "true"
    else:
        config["stateless_http"] = False

    return config