# MCP (Model Context Protocol) — Revision Notes

Personal quick-reference from building `zedex-tools-server`: wrapping existing Zedex
business-API tools as an MCP server, from local dev through to a working Claude Desktop
connection. Revisit this before touching the project again after a break.

## 1. Core architecture

- **Host → Client → Server.** Host = the app (Claude Desktop, Claude Code). A client is
  the host's connection to one server. One host can hold many client↔server connections
  at once.
- **Three primitives:**
  - **Tools** — model-controlled actions (`@mcp.tool()`). The model decides when to call them.
  - **Resources** — app-controlled, read-only data (`@mcp.resource()`), more like a GET endpoint.
  - **Prompts** — user-selected message templates (`@mcp.prompt()`).

## 2. Building a tool — what actually becomes the schema

- **Tool name** = the function name.
- **Tool description** (what the model reads) = the **docstring** — must be a real
  triple-quoted string, not a `#` comment (comments never reach MCP).
- **Parameter schema** = the **type hints**, not the docstring text. The SDK builds a
  JSON schema from them and rejects bad-typed calls before your function runs.
- Per-arg descriptions: `Annotated[str, Field(description="...")]`.

## 3. SDK version — v1 (`FastMCP`) vs v2 (`MCPServer`)

The single biggest source of stale-tutorial confusion. Check `pyproject.toml`:
`mcp[cli]>=2.x` → you're on v2.

| | v1 | v2 |
|---|---|---|
| Import | `from mcp.server.fastmcp import FastMCP` | `from mcp.server import MCPServer` |
| Module | `mcp.server.fastmcp.*` | `mcp.server.mcpserver.*` |
| Context | `ctx.fastmcp` | `ctx.mcp_server` |
| Base exception | `FastMCPError` | `MCPServerError` |

`ToolError` keeps its name, just moves: `mcp.server.mcpserver.exceptions.ToolError`.
Decorator usage (`@mcp.tool()` etc.) is identical in both. This is a **hard rename** —
the old v1 import path is fully removed in v2, not deprecated.

`MCPServer(name, instructions="...")` — a real constructor kwarg (confirmed against
source). Maps to the protocol's `InitializeResult.instructions` field: a hint the host
*may* surface to the model about how to use this server. Not a hard system-prompt
override — if you ever build your own custom host, your own code still owns the real
system prompt.

## 4. Error handling — three tiers

1. **`ToolError`** — model-recoverable (bad args, not found). Must be **`raise`d, not
   `return`ed** — `return ToolError(...)` just hands back the exception object as a weird
   normal result.
2. **`MCPError`** — protocol-level rejection, no retry helps. You rarely raise this by
   hand; the SDK generates it automatically when input doesn't match your declared
   type/Pydantic model — a good reason to model inputs properly instead of loose
   `dict`/`list`.
3. **Unhandled exception** — a real crash. Client sees a bland "Error executing tool
   `<name>`", no detail. Full traceback goes to **server-side logs only**. Correct
   behavior for genuine infra failures (backend down) — no amount of retrying with
   different arguments fixes those.

Decision rule: *"Could a smarter model have avoided this? Yes → `ToolError`. No →
`MCPError` / let it crash."* Still fine to catch an infra failure and raise a clear
`ToolError` purely for a readable message — just be honest that's for clarity, not
because the model can "fix" it.

## 5. stdio transport — stdout is not yours

With stdio transport, **stdout carries the JSON-RPC protocol itself**. `print(...)`
inside a tool writes to stdout too — it gets silently lost or corrupts the stream,
never shows up as a usable log. **Always log to stderr** (Python's `logging` module
does this by default) — stderr passes straight through to the terminal that spawned
the server, since it isn't part of the protocol channel.

## 6. Pydantic models for tool inputs — not just outputs

- A bare `list`/`dict` type hint produces a schema with no real validation keyword on
  its contents (equivalent to "accept anything") — flagged by some clients as a
  portability risk.
- A real Pydantic model gets you free `MCPError`-tier rejection of malformed calls
  before your function body runs.
- **Gotcha:** once typed as a Pydantic model, your function receives *model instances*,
  not plain dicts. If existing backend code expects dicts (`x["field"]`, `x.get(...)`),
  convert first: `backend_fn([item.model_dump() for item in items])`. Passing model
  instances straight through crashes with `TypeError: '<Model>' object is not
  subscriptable` — an unhandled crash, not a clean validation error, because it happens
  *after* validation already passed.

## 7. Real bugs hit on this project (memorable ones)

- **Self-recursion via name shadowing** — importing `find_customer` then defining
  `def find_customer(...)` in the same file overwrites the import; the tool calls
  itself forever until the recursion limit kills it (looks like a multi-minute hang,
  then a crash). Fix: alias every backend import, e.g. `as _find_customer`, and use the
  alias inside the wrapper body — every single time, no exceptions.
- **`return ToolError(...)` instead of `raise`** — silent no-op error signaling. Easy to
  repeat across every tool wrapper if copy-pasted.
- **Model instances passed into dict-shaped legacy code** — see §6's gotcha.
  `TypeError: 'X' object is not subscriptable`.
- **Refactoring one side of a call without the other** — changed a backend function's
  signature (from 4 positional args to 1 dict) but didn't update the caller →
  `TypeError: create_or_update_bill() takes 1 positional argument but 4 were given`.
  Whenever a backend function's signature changes, grep for every call site immediately.
- **`inputSchema.properties.X.items` empty-schema warning** — from an untyped
  `list` parameter. Fixed by typing it `list[SomeModel]`.

## 8. Local vs. remote — what actually needs to move

MCP doesn't relocate tool code, it wraps it in a protocol layer.
- **stdio** (local subprocess) — what `mcp dev` and Claude Desktop use. Zero cloud
  needed; fine for a personal demo or someone willing to run your repo themselves.
- **Streamable HTTP** — needed only if someone else must connect without running
  anything locally. In that case the backend must also be reachable from wherever the
  MCP server is hosted.
- Cloud deployment is a requirement of "shareable without local setup," not of MCP itself.

## 9. Connecting to Claude Desktop (this machine's specifics)

- Config lives at the sandboxed path this install actually uses (MSIX-packaged apps
  redirect the usual `%APPDATA%\Claude\` path there transparently):
  `AppData\Local\Packages\Claude_<hash>\LocalCache\Roaming\Claude\...`
- On this build, Settings → Developer → Local MCP servers → **Edit config** opens one
  **consolidated** preferences file (also holds Cowork prefs, folder grants, UI state) —
  not a dedicated `mcpServers`-only file like older public docs describe. Add
  `"mcpServers"` as a top-level sibling key to `"preferences"`, don't touch anything else.
- Entry shape: `{"command": "uv", "args": ["run", "--directory", "<project path>",
  "python", "main.py"]}`.
- **Editing the file alone isn't enough** — fully quit the app from the system tray
  (not just close the window) and reopen it before expecting the change to show up.
- Claude Code CLI has a cleaner path for its own config: `claude mcp add-json <name>
  '<json>'`, and `claude mcp add-from-claude-desktop` imports Desktop's entries the
  other direction. Neither of these apply to Desktop itself — Desktop has no CLI.
- `.mcpb` files / Settings → Extensions are a *different, unrelated* feature — a
  packaging format for distributing a *finished* MCP server as a one-click install.
  Irrelevant while actively developing a server by hand.

## 10. Debugging a stdio server

`pdb.set_trace()` / `breakpoint()` don't work here — same stdin/stdout conflict as §5.
Use `debugpy` instead (separate TCP port, doesn't touch the protocol channel):

```python
if os.environ.get("MCP_DEBUG"):
    import debugpy
    debugpy.listen(5678)
    debugpy.wait_for_client()
```

Attach from VS Code/Cursor with an `"attach"` launch config pointing at
`localhost:5678`, run the Inspector with `MCP_DEBUG=1` set, then attach and set real
breakpoints in the editor.

## 11. General debugging habit for this project

A generic "Error executing tool `<name>`" with **no detail** = tier-3 crash, real cause
is in server logs / needs a debugger — not a code-reading guess. A **specific** message
(a Pydantic "Field required" list, a `TypeError` with an arg count) is gold — read it
literally, it almost always names the exact line and mismatch. Always confirm a fresh
process (Inspector restart, or full Desktop quit+reopen) before trusting that a fix
didn't work — edited files on disk do nothing until the process reloads them.
