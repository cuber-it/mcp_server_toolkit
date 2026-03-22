# mcp_server_framework.gate

Session-based TOTP gate for MCP tool groups.

Protects sensitive MCP tools (shell access, vault, database) behind a
time-based one-time password (TOTP, RFC 6238). Compatible with any standard
authenticator app (Google Authenticator, Aegis, Vaultwarden TOTP, etc.).

## How it works

All groups start **locked** on every proxy restart. A valid TOTP code unlocks
a group for a configurable inactivity timeout (default: 2h). Any tool call
within the group resets the timer. After 5 consecutive wrong codes, the group
is locked out until proxy restart.

```
Proxy starts
  → all groups locked

User: gate_unlock(group="shell", code="482931")
  → TOTP verified → shell unlocked for 2h

User: shell_exec(command="ls -la")
  → check passes, timer reset → runs

2h inactivity
  → shell locked automatically

User: gate_lock()
  → all groups locked immediately (kill switch)
```

## Quick start

```python
from mcp_server_framework.gate import Gate

def register(mcp, config):
    gate = Gate(config.get("gate", {}))
    gate.register_tools(mcp)   # adds gate_unlock, gate_lock, gate_status

    @mcp.tool()
    @gate.protect("shell")     # inner decorator — see note below
    def shell_exec(command: str) -> str:
        """Execute a shell command."""
        import subprocess
        return subprocess.check_output(command, shell=True, text=True)
```

> **Decorator order**: `@gate.protect` must be the **inner** decorator,
> `@mcp.tool()` must be **outer**. This ensures FastMCP sees the correct
> function signature for schema generation.

## MCP tools registered

| Tool | Description |
|------|-------------|
| `gate_unlock(group, code)` | Unlock a group with TOTP code |
| `gate_lock(group="")` | Lock a group, or all groups if empty (kill switch) |
| `gate_status()` | Show status and remaining time per group |

## Configuration

### Minimal (env backend)

```yaml
gate:
  enabled: true
  secret_backend: env
  groups:
    shell:
      timeout: 7200          # inactivity timeout in seconds
      secret_ref: MCP_GATE_SECRET_SHELL   # name of environment variable
```

```bash
# systemd service or shell
export MCP_GATE_SECRET_SHELL=JBSWY3DPEHPK3PXP
```

### File backend

```yaml
gate:
  enabled: true
  secret_backend: file
  secret_file: ~/.mcp_gate_secrets   # default
  groups:
    shell:
      secret_ref: shell     # key in the file
    vault:
      secret_ref: vault
      timeout: 3600
```

```bash
# ~/.mcp_gate_secrets  (chmod 600)
shell=JBSWY3DPEHPK3PXP
vault=JBSWY3DPEHPK3PXQ
```

### Vaultwarden backend

```yaml
gate:
  enabled: true
  secret_backend: vaultwarden
  vaultwarden_url: https://v.example.com
  vaultwarden_token: ${VW_TOKEN}     # resolved from env at startup
  vaultwarden_cache_ttl: 3600        # 0 = no cache
  groups:
    shell:
      secret_ref: mcp-gate/shell     # Vaultwarden item name (secure note)
      timeout: 7200
```

Requires: `pip install requests`

### Disabled (tools work without authentication)

```yaml
gate:
  enabled: false
```

## Secret backends

| Backend | Class | Deps | Secret rotation |
|---------|-------|------|-----------------|
| `env` | `EnvBackend` | none | restart required |
| `file` | `FileBackend` | none | immediate |
| `vaultwarden` | `VaultwardenBackend` | `requests` | after cache TTL |

## Generating a secret

```python
from mcp_server_framework.gate.totp import generate_secret
print(generate_secret())   # → e.g. JBSWY3DPEHPK3PXP
```

Enter this Base32 string into your authenticator app as a manual TOTP entry.

## Security notes

- Secrets are **never** stored in config.yaml — only references (env var name, file key, Vaultwarden item name)
- All groups are locked on every proxy restart — no persistent unlock state
- Lockout after 5 consecutive failures per group (reset by proxy restart)
- Inactivity timeout resets on every successful tool call
- `gate_lock()` with no argument is the kill switch — locks everything immediately
