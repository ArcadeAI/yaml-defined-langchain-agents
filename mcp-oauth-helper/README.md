# MCP OAuth Helper

**Spec-compliant OAuth for any MCP server using the official MCP SDK.**

This helper mimics how the MCP Inspector handles OAuth - it works with **any** MCP server that requires OAuth, not just specific providers.

## How It Works

1. **Auto-detects OAuth**: When connecting to an MCP server returns 401
2. **Dynamic client registration**: No pre-registration needed (if server supports it)
3. **PKCE support**: Built-in security with code challenge
4. **Token storage**: Saves tokens to `~/.mcp-oauth-tokens.json`

## Usage

### 1. Test connection and perform OAuth flow

```bash
cd mcp-oauth-helper
node dist/index.js test https://mcp.linear.app/mcp
```

This will:
- Try to connect
- Detect if OAuth is needed (401 response)
- Discover OAuth metadata from server
- Open browser for authorization
- Save tokens automatically

### 2. Get saved token

```bash
node dist/index.js token https://mcp.linear.app/mcp
```

Returns the access token if one exists.

### 3. Use with Python agents

**Option A: Export token to environment**
```bash
# After running OAuth flow
export MCP_LINEAR_APP_ACCESS_TOKEN=$(node mcp-oauth-helper/dist/index.js token https://mcp.linear.app/mcp)

# Then run your agent
python main.py test-agents/test-linear-oauth.yaml "List issues"
```

**Option B: Let Python discover token**
The Python agent automatically checks for tokens in these patterns:
- `{DOMAIN}_ACCESS_TOKEN` (e.g., `MCP_LINEAR_APP_ACCESS_TOKEN`)
- `{DOMAIN}_TOKEN`
- `{SERVER_NAME}_ACCESS_TOKEN`
- `{SERVER_NAME}_TOKEN`

## How This Differs from Custom OAuth

**Traditional approach (provider-specific):**
```python
# Hardcoded for each provider
if provider == 'linear':
    auth_url = 'https://linear.app/oauth/authorize'
    # ... custom logic for Linear
elif provider == 'github':
    auth_url = 'https://github.com/login/oauth/authorize'
    # ... custom logic for GitHub
```

**MCP SDK approach (universal):**
```typescript
// Works with ANY MCP server
const transport = new StreamableHTTPClientTransport(url);
await client.connect(transport);
// SDK automatically:
// 1. Detects 401 with WWW-Authenticate headers
// 2. Discovers OAuth metadata from server
// 3. Handles authorization flow
// 4. Manages PKCE
// 5. Refreshes tokens
```

## Examples

### Linear
```bash
node dist/index.js test https://mcp.linear.app/mcp
```

### Any other MCP server with OAuth
```bash
node dist/index.js test https://your-mcp-server.com/mcp
```

The helper will:
1. Attempt connection
2. Catch 401 response
3. Discover OAuth configuration from server
4. Guide you through authorization
5. Save tokens for future use

## Token File Format

Tokens are saved to `~/.mcp-oauth-tokens.json`:

```json
{
  "https://mcp.linear.app/mcp": {
    "clientInfo": {
      "client_id": "auto-generated-id",
      "client_secret": null
    },
    "tokens": {
      "access_token": "your_token_here",
      "token_type": "Bearer",
      "expires_in": 3600
    },
    "updatedAt": "2024-01-15T10:30:00.000Z"
  }
}
```

## Integration with Python Agents

The Python agent system (`main.py`) automatically:

1. **Checks for Authorization header** in YAML config
2. **Looks for tokens in environment** if no header found
3. **Tries multiple naming patterns** for flexibility
4. **Uses discovered token** for MCP connection

### YAML Configuration

```yaml
mcpServers:
  linear:
    url: "https://mcp.linear.app/mcp"
    # No headers needed - token will be found automatically!

agents:
  linear_agent:
    instructions: |
      You help with Linear project management.
    tools: []  # Gets all tools from Linear MCP
```

### Workflow

```bash
# 1. One-time: Perform OAuth
cd mcp-oauth-helper
node dist/index.js test https://mcp.linear.app/mcp
# Browser opens -> Authorize -> Done!

# 2. Export token (optional, for convenience)
export MCP_LINEAR_APP_ACCESS_TOKEN=$(node dist/index.js token https://mcp.linear.app/mcp)

# 3. Run your agent
cd ..
python main.py test-agents/test-linear-oauth.yaml "What issues do I have?"
```

## Why TypeScript Instead of Python?

The official MCP SDK's OAuth implementation is in TypeScript and provides:
- ✅ Spec-compliant OAuth 2.1 with PKCE
- ✅ Automatic metadata discovery
- ✅ Dynamic client registration
- ✅ Works with **any** MCP server (not provider-specific)
- ✅ Maintained by MCP project (always up-to-date)

The Python MCP SDK doesn't yet have equivalent OAuth helpers, so we use the TypeScript version and bridge with environment variables/token files.

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Watch mode
npm run dev
```

