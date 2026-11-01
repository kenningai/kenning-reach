#!/usr/bin/env python3
"""Regenerate TOOL_DESCRIPTIONS.md from server.py — the strings an LLM sees.

    uv run python scripts/gen_tool_descriptions.py
"""
import asyncio, os, sys, textwrap
from unittest.mock import AsyncMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from kenning_reach.server import create_mcp_server  # noqa: E402

ORDER = ["navigate_genesis", "open_envisioning", "advance_frame", "actualize", "measure", "time_travel",
         "create_entities", "create_relations", "delete_entities", "delete_relations",
         "search_memories", "find_memories_by_name", "list_allowed_types", "list_allowed_relation_types",
         "get_neo4j_schema", "read_neo4j_cypher", "gds_create_projection", "gds_drop_projection",
         "gds_pagerank", "gds_betweenness", "gds_louvain", "gds_wcc"]

async def main():
    mcp = create_mcp_server(AsyncMock())
    tools = {t.name: t for t in await mcp.list_tools()}
    out = ["# Tool Descriptions (LLM-visible surface)", "",
           f"Generated from `src/kenning_reach/server.py` by `scripts/gen_tool_descriptions.py`. For each of the {len(tools)} tools: the docstring (the `description` field in the MCP tool schema) followed by every parameter's `Field(description=...)` string (the `inputSchema` property descriptions). These are the strings an LLM sees when the server advertises its tools.", "", "---", ""]
    names = [n for n in ORDER if n in tools] + sorted(n for n in tools if n not in ORDER)
    for i, name in enumerate(names, 1):
        t = tools[name]
        out += [f"## {i}. {name}", "", "**Docstring:**", ""]
        out += ["> " + l if l.strip() else ">" for l in textwrap.dedent(t.description or "").strip().splitlines()]
        props = (t.parameters or {}).get("properties", {})
        out += ["", "**Parameters:**", ""] if props else ["", "**Parameters:** none", ""]
        for pn, ps in props.items():
            out.append(f"- `{pn}`: {ps.get('description', '')}")
        out += ["", "---", ""]
    open(os.path.join(os.path.dirname(__file__), "..", "TOOL_DESCRIPTIONS.md"), "w").write("\n".join(out))
    print(f"wrote TOOL_DESCRIPTIONS.md for {len(names)} tools")

asyncio.run(main())
