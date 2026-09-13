# Zedex Tools MCP Server

An MCP (Model Context Protocol) server that wraps an existing Zedex business-tools
API — customer lookup, product search, and bill creation/updates — so any MCP-aware
AI client (Claude Desktop, Claude Code, MCP Inspector) can operate it directly
through natural conversation, instead of each client needing a bespoke integration.

## Why this exists

This is a hands-on learning project: taking a Python business-API codebase that an
LLM was already calling in an ad-hoc way, and rebuilding it properly on top of the
MCP spec — all three primitives (Tools, Prompts, Resources), the three-tier error
model, typed inputs, and a real local-dev → Claude Desktop/Code workflow. The goal
was to actually understand *why* MCP is built the way it is, not just wire up a demo.

## What MCP is, briefly

MCP standardizes how an AI client talks to a server that exposes capabilities to a
model. A **Host** (Claude Desktop, Claude Code) holds a **Client** connection to
each **Server** it talks to. A server can expose three kinds of things:

| Primitive | Who decides to use it | Purpose |
|---|---|---|
| **Tools** | The model | Actions the model can call mid-conversation (`@mcp.tool()`) |
| **Resources** | The app / user | Read-only reference data, more like a GET endpoint (`@mcp.resource()`) |
| **Prompts** | The user | Reusable message templates picked to kick off a task (`@mcp.prompt()`) |

This server uses all three — not just Tools — which is the main thing this project
set out to actually understand rather than skip past.

## What this server exposes

### Tools (model-invoked actions)

| Tool | What it does | Annotations |
|---|---|---|
| `find_customer(search)` | Look up a Zedex customer by name or ID | read-only, idempotent |
| `get_lookups()` | Fetch valid colors, categories, gauges, companies | read-only, idempotent |
| `search_product(products)` | Search products against one or more typed criteria | read-only, idempotent |
| `get_bill(id_or_invoice_number)` | Fetch a bill by ID or invoice number | read-only, idempotent |
| `create_or_update_bill(bill_data)` | Create a new bill, or update an existing one by `billId` | write — not marked idempotent, on purpose |

Every tool input is a typed Pydantic model (`ProductQuery`, `CreateUpdateBill` /
`BillItem`) rather than a bare `dict`/`list`, so malformed calls are rejected by the
protocol layer before the function body ever runs. Read-only tools are explicitly
annotated as such — this is what lets a client reason about which calls are safe to
repeat versus which ones (like creating a bill) genuinely need user confirmation
every time.

### Prompts (user-selected starting templates)

| Prompt | Parameters | What it kicks off |
|---|---|---|
| `start_new_bill` | `customer_search`, `product_request` | Finds the customer, validates the requested products against current lookups, shows a table for confirmation before anything is created |
| `audit_bill` | `bill_id` | Fetches a bill and flags any line items whose pricing/values look stale against current lookups — read-only |

These only run when explicitly selected (via the "+" attach menu in Claude Desktop,
or `/mcp__zedex-tools__<name>` in Claude Code) — they're deliberately *not* the same
mechanism as the server-level agent instructions below, since a prompt only applies
on the turn it's picked, not automatically for the whole conversation.

### Resources (read-only reference data)

| Resource URI | Contents |
|---|---|
| `zedex://lookups` | Current valid product categories, colors, gauges, and companies |

Exposed as a Resource rather than only a Tool so a client can attach it once per
conversation as ambient context, instead of the model re-deciding to call
`get_lookups` on every single turn.

### Server-level instructions

The server sets `MCPServer(name, instructions=SYSTEM_MESSAGE)` with the Zedex
Billing Agent's core rules baked in — how shared vs. product-specific values are
applied, when to auto-correct vs. ask for clarification, the confirm-before-create
workflow, and domain-specific formats (e.g. `18/5` = size/quantity). This is a hint
the host *may* surface to the model on every turn, distinct from a Prompt, which
only activates when a user picks it.

## Project structure

```
zedex-tools-server/
├── main.py                  # MCP server: tools, prompts, resource, instructions
├── models.py                 # Pydantic input models (ProductQuery, BillItem, CreateUpdateBill)
├── tools/
│   └── zedex_calling.py       # Thin HTTP layer over the existing Zedex API
├── pyproject.toml
└── MCP_REVISION_NOTES.md     # Personal build-log / concept notes from developing this
```

## Running it locally

```bash
uv sync
uv run mcp dev main.py   # opens MCP Inspector — test tools, prompts, and resources
```

No cloud deployment needed for local development — `stdio` transport runs the
server as a local subprocess. Cloud/HTTP transport only becomes necessary if someone
else needs to connect without running this repo themselves.

**Claude Desktop** — add an entry under a top-level `"mcpServers"` key in the local
MCP config, pointing `command`/`args` at `uv run --directory <path> python main.py`,
then fully restart the app.

**Claude Code** — `claude mcp add-json zedex-tools '<config>'`, then use tools
normally or invoke a prompt with `/mcp__zedex-tools__start_new_bill`.

## Status

Working: all five tools, both prompts, the lookups resource, and server-level
instructions are live and tested via Inspector, Claude Desktop, and Claude Code.

Next: a structural (not just docstring-based) confirm step for bill *updates* —
returning a diff of added/changed/removed line items before anything is written —
and eventually auth + remote transport if this needs to be usable without running
the repo locally.

---

Built while learning MCP hands-on — happy to talk through any of the design
decisions above with anyone building something similar.
