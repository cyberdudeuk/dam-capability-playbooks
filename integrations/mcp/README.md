# Reference MCP server

A small [Model Context Protocol](https://modelcontextprotocol.io/) server that lets an MCP-compatible AI assistant use the DAM capability playbooks as tools. It is a reference for testing and adapting, not a supported service.

- Python standard library only; no packages to install.
- Speaks JSON-RPC 2.0 over standard input and output, one message per line.
- Reads the portal's published content (`data/playbooks.json`) and returns the page address each answer comes from.
- Sends nothing anywhere except one request for the content file, and only if you give it a web address.

## Tools

| Tool | What it does |
|---|---|
| `search_portal` | Search requirements, playbook steps, capabilities, delivery practices, sector supplements, tool categories and glossary terms |
| `get_capability` | One capability from the capability model, such as `CR-01` |
| `get_requirement` | One DAM Policy requirement, such as `DAM-R01`, with its strength and source |
| `get_practice` | One delivery and change practice, such as `CH-06` |
| `list_sector_rules` | The starter data quality rules for a sector supplement, or the list of supplements |

## Run it

Choose where the content comes from with one environment variable:

- `DAM_PLAYBOOKS_FILE`: a downloaded copy of `data/playbooks.json` (recommended inside a restricted network)
- `DAM_PLAYBOOKS_URL`: the full `https` address of `data/playbooks.json` on the portal or your own copy
- neither: `site/data/playbooks.json` in this repository, after `python tools/build.py`

Example configuration for an assistant that reads MCP servers from a JSON file:

```json
{
  "mcpServers": {
    "dam-playbooks": {
      "command": "python3",
      "args": ["integrations/mcp/server.py"],
      "env": {"DAM_PLAYBOOKS_FILE": "/path/to/playbooks.json"}
    }
  }
}
```

Check C-32 starts the server against every build, lists its tools, runs a search and confirms the server reports the portal's version.

## Before using it in your organisation

- Ask your security and information governance teams to approve it as you would any integration.
- Keep the prototype status and the attribution statement with any answer an assistant gives.
- GOV.UK remains the authority for anything the portal repeats.
