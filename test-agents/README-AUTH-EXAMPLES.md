# MCP Server Authentication Examples

This directory contains example configurations demonstrating different authentication methods for connecting to MCP servers.

## Quick Reference

| File | Auth Method | Use Case |
|------|-------------|----------|
| `test-query-param-auth.yaml` | Query Parameters | API key in URL |
| `test-multi-auth-servers.yaml` | Multiple Methods | Mixed authentication |
| `test-oauth-server.yaml` | OAuth Token | Pre-authorized bearer token |

## Authentication Methods Supported

### 1. Header-Based Authentication

**Most common method** - API keys or tokens in HTTP headers:

```yaml
mcpServers:
  my_server:
    url: "https://api.example.com/mcp"
    headers:
      Authorization: "Bearer ${API_KEY}"
```

**Examples:**
- Bearer tokens: `Authorization: Bearer ${TOKEN}`
- API keys: `X-API-Key: ${KEY}`
- Custom headers: `X-Custom-Auth: ${VALUE}`

### 2. Query Parameter Authentication

**Alternative method** - API key embedded in the URL:

```yaml
mcpServers:
  my_server:
    url: "https://api.example.com/mcp?api_key=${API_KEY}"
```

**Benefits:**
- Simpler configuration (no headers needed)
- Works with services that only accept URL auth
- Can combine multiple query params

**Examples:**
- Single param: `?api_key=${KEY}`
- Multiple params: `?api_key=${KEY}&user_id=${USER}`
- Mixed: `?key=${KEY}&version=v1&format=json`

### 3. No Authentication

**Local development** or open servers:

```yaml
mcpServers:
  local:
    url: "http://localhost:3000/mcp"
```

No headers or query params needed!

### 4. OAuth Token (Server-Level)

**Pre-authorized access** - requires manual OAuth flow:

```yaml
mcpServers:
  oauth_server:
    url: "https://oauth-server.com/mcp"
    headers:
      Authorization: "Bearer ${OAUTH_TOKEN}"
```

**Setup Required:**
1. Visit OAuth provider's authorization page
2. Complete OAuth flow → get access token
3. Store token in `.env` file
4. Reference in config with `${OAUTH_TOKEN}`

**Note:** This is different from tool-level OAuth (which is automatic).

### 5. Hybrid Authentication

**Both headers and query params:**

```yaml
mcpServers:
  hybrid:
    url: "https://api.example.com/mcp?client_id=${CLIENT_ID}"
    headers:
      X-Session-Token: "${SESSION_TOKEN}"
```

Some servers require multiple forms of authentication.

## Environment Variable Substitution

All authentication values support `${VAR_NAME}` syntax:

```bash
# .env file
API_KEY=sk_live_abc123
USER_ID=user_456
OAUTH_TOKEN=oauth2_xyz789
```

```yaml
# In your YAML config
mcpServers:
  server:
    url: "https://api.com/mcp?key=${API_KEY}&user=${USER_ID}"
    headers:
      Authorization: "Bearer ${OAUTH_TOKEN}"
```

**Features:**
- Works in both `url` and `headers` fields
- Multiple variables in same string
- Falls back to literal string if not found in environment

## OAuth: Tool-Level vs Server-Level

### Tool-Level OAuth (Automatic ✅)

**What it is:**
- Individual tools require user authorization
- Example: Gmail.SendEmail needs Gmail OAuth permission

**How it works:**
1. Agent tries to call a tool
2. Tool returns "authorization required" with URL
3. System shows: `🔒 Authorization required: https://...`
4. User clicks URL, authorizes in browser
5. User types `continue` in terminal
6. Tool call succeeds

**Configuration:** None needed! Fully automatic.

### Server-Level OAuth (Manual 🔧)

**What it is:**
- The MCP server itself requires OAuth to connect
- Can't even discover tools without authorization

**How it works:**
1. Visit server's OAuth portal manually
2. Complete authorization flow
3. Get access token
4. Add token to `.env` file
5. Reference in YAML config

**Configuration:** Required (see `test-oauth-server.yaml`)

## Testing Your Configuration

### Test with Debug Mode

```bash
python main.py --debug test-agents/test-query-param-auth.yaml "test request"
```

Look for these messages:
- `[MCP] Connecting to server_name at URL` - Connection attempt
- `[MCP] Found X tools from server_name` - Success!
- `⚠️  server_name requires authorization` - Auth needed

### Common Error Messages

**401 Unauthorized / 403 Forbidden:**
```
⚠️  my_server requires authorization: 401 Client Error: Unauthorized
```
**Solution:** Check your API key/token in `.env` file

**Connection Refused:**
```
⚠️  Failed to connect to my_server: Connection refused
```
**Solution:** Verify the URL is correct and server is running

**Missing Environment Variable:**
```
[MCP] Connecting to my_server at https://api.com/mcp?key=${API_KEY}
```
Notice `${API_KEY}` wasn't substituted? Add it to `.env` file.

## Running the Examples

### 1. Query Parameter Authentication

```bash
# Setup
echo "API_KEY=your_key_here" >> .env
echo "USER_ID=your_user_id" >> .env

# Run
python main.py test-agents/test-query-param-auth.yaml "Hello"
```

### 2. Multiple Servers

```bash
# Setup (example values)
echo "ARCADE_API_KEY=arc_..." >> .env
echo "ARCADE_USER_ID=user_..." >> .env
echo "SERVICE_API_KEY=service_key" >> .env
echo "CUSTOM_API_KEY=custom_key" >> .env

# Run
python main.py test-agents/test-multi-auth-servers.yaml "What tools do you have?"
```

### 3. OAuth Server

```bash
# Setup - YOU must get the OAuth token first!
# 1. Visit https://your-oauth-server.com/authorize
# 2. Complete OAuth flow
# 3. Copy the access token
echo "OAUTH_MCP_TOKEN=your_oauth_token" >> .env

# Run
python main.py test-agents/test-oauth-server.yaml "Test OAuth connection"
```

## Best Practices

1. **Never commit credentials** - Always use `.env` file
2. **Use descriptive variable names** - `GITHUB_TOKEN` not `TOKEN1`
3. **Test with debug mode** - Easier to spot auth issues
4. **Check expiration** - OAuth tokens expire, refresh as needed
5. **One server at a time** - Test each server connection individually first
6. **Document requirements** - Add comments in YAML about what tokens are needed

## Need Help?

- Server won't connect? Try `--debug` flag
- Tool requires OAuth? System handles it automatically
- Server requires OAuth? See `test-oauth-server.yaml` for setup
- Query params not working? Check env var substitution with `--debug`

