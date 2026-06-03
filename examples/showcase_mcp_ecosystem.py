from __future__ import annotations

from showcase_common import (
    capability_node,
    config_source_node,
    mcp_server_node,
    showcase_client,
    tool_node,
    trace_id,
)


def main() -> None:
    client = showcase_client("mcp")
    trace = trace_id("mcp_ecosystem")

    agent = client.agent(
        id="showcase.mcp-agent",
        name="MCP Coordinator Agent",
        role="integrator",
        metadata={"team": "showcase", "domain": "mcp registry"},
    )
    config = config_source_node(
        "Claude Desktop Config",
        "~/.config/Claude/claude_desktop_config.json",
    )
    filesystem_server = mcp_server_node(
        "Filesystem MCP",
        "stdio://mcp-filesystem",
        transport="stdio",
        version="1.4.2",
        config_source="Claude Desktop Config",
        config_path="~/.config/Claude/claude_desktop_config.json",
    )
    search_server = mcp_server_node(
        "Search MCP",
        "http://localhost:8765/mcp",
        transport="http",
        version="0.9.0",
        config_source="Claude Desktop Config",
        config_path="~/.config/Claude/claude_desktop_config.json",
    )
    file_tool = tool_node("file_system", capabilities=["read", "write", "list"])
    search_tool = tool_node("web_search", capabilities=["search", "summarize"])

    client.emit(
        "mcp.config.discovered",
        config,
        {
            "source": "Claude Desktop Config",
            "config_path": "~/.config/Claude/claude_desktop_config.json",
            "server": "Filesystem MCP",
            "transport": "stdio",
            "endpoint": "stdio://mcp-filesystem",
            "version": "1.4.2",
        },
        target=filesystem_server,
        trace_id=trace,
    )
    client.emit(
        "mcp.config.discovered",
        config,
        {
            "source": "Claude Desktop Config",
            "config_path": "~/.config/Claude/claude_desktop_config.json",
            "server": "Search MCP",
            "transport": "http",
            "endpoint": "http://localhost:8765/mcp",
            "version": "0.9.0",
        },
        target=search_server,
        trace_id=trace,
    )

    for server, capability, category, description in [
        (
            filesystem_server,
            "read_project_file",
            "filesystem",
            "Read repository files for agent context.",
        ),
        (
            filesystem_server,
            "write_report",
            "filesystem",
            "Persist generated reports and artifacts.",
        ),
        (
            search_server,
            "web_search",
            "research",
            "Search web sources and return summarized results.",
        ),
    ]:
        client.emit(
            "mcp.capability.discovered",
            server,
            {
                "server": server["name"],
                "capability": capability,
                "category": category,
                "description": description,
                "version": server["metadata"].get("version"),
            },
            target=capability_node(server["name"], capability, category, description),
            trace_id=trace,
        )

    client.emit(
        "tool.connected",
        file_tool,
        {"tool": "file_system", "server": "Filesystem MCP"},
        target=filesystem_server,
        trace_id=trace,
    )
    client.emit(
        "tool.connected",
        search_tool,
        {"tool": "web_search", "server": "Search MCP"},
        target=search_server,
        trace_id=trace,
    )

    with agent.task("Map available MCP tools", trace_id=trace):
        with agent.tool("web_search"):
            print("MCP Coordinator Agent inspects declared search capability metadata")
        with agent.tool("file_system"):
            print("MCP Coordinator Agent records filesystem capability metadata")

    print("OpenMesh showcase completed: MCP ecosystem metadata")
    print(f"trace_id={trace}")


if __name__ == "__main__":
    main()
