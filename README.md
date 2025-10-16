# YAML-Driven Agent System

A powerful yet simple multi-agent system using LangChain and LangGraph. Define everything in YAML - no coding required!

## Key Features

- **Pure YAML Configuration**: Define agents, tools, and routing in YAML
- **Hierarchical Agent Teams**: Multi-level supervisor architecture with department specialization  
- **MCP Client Integration**: Connect to any MCP gateway for tool access (including Arcade's MCP gateways)
- **Automatic Tool Discovery**: Agents automatically discover and use tools from MCP servers
- **Smart OAuth Handling**: Built-in authorization flow with proper interrupt handling
- **Flexible Routing**: From simple single agents to complex multi-department workflows
- **Phoenix Observability**: Built-in tracing and monitoring with Phoenix/OpenInference
- **Debug Mode**: Comprehensive debugging with `--debug` flag

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment**:
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

3. **Run the system**:
   ```bash
   # Interactive mode
   python main.py
   
   # With specific config
   python main.py my-agents.yaml
   
   # Single request
   python main.py "What is the status of ticket ABC-123?"
   
   # Debug mode
   python main.py --debug agents.yaml "Get my calendar"
   ```

## Agent Architecture Patterns

### 1. Single Agent
```yaml
agents:
  assistant:
    instructions: |
      You are a helpful AI assistant.
      Answer questions and help with tasks.
```

### 2. Simple Multi-Agent with Supervisor
```yaml
agents:
  researcher:
    instructions: Search and find information
    tools: [WebSearch]
  
  writer:
    instructions: Write and edit content
  
  supervisor:
    instructions: |
      Route to:
      - researcher: for finding information
      - writer: for creating content
      - COMPLETE: when done

routing:
  supervisor: supervisor
```

### 3. Hierarchical Agent Teams
```yaml
agents:
  # Personal Department
  email:
    instructions: Handle Gmail tasks
    tools: [Gmail]
  
  calendar:
    instructions: Manage Google Calendar
    tools: [GoogleCalendar]
    
  personal_supervisor:
    instructions: |
      Route personal tasks:
      - email: for Gmail tasks
      - calendar: for scheduling
      - COMPLETE: when done

  # Development Department  
  github:
    instructions: Manage GitHub repositories
    tools: [GitHub]
    
  jira:
    instructions: Handle Jira tickets
    tools: [Jira]
    
  dev_supervisor:
    instructions: |
      Route development tasks:
      - github: for repositories
      - jira: for tickets
      - COMPLETE: when done

  # Master Supervisor
  master_supervisor:
    instructions: |
      Route to departments:
      - personal_supervisor: for email/calendar
      - dev_supervisor: for code/tickets
      - COMPLETE: when all done

routing:
  supervisor: master_supervisor
  max_iterations: 20
```

## Available Templates

| Template | Description | Use Case |
|----------|-------------|----------|
| `simple-agent-example.yaml` | Single agent | Basic Q&A, simple tasks |
| `supervisor-personal-assistant.yaml` | Multi-agent with supervisor | Email, calendar, documents |
| `supervisor-it-helpdesk.yaml` | IT support system | Tickets, knowledge, escalation |
| `single-supervisor-agents-template.yaml` | Customizable template | Build your own single supervisor agents |
| `hierarchical-agent-teams-example.yaml` | Full hierarchical system | Complex multi-department workflows |
| `hierarchical-agent-teams-template.yaml` | Customizable template | Build your own hierarchy of agents |

## Interactive Commands

- **Type your request**: Process through the agent system
- **`exit`**: Quit the system  
- **`reset`**: Clear conversation history
- **`continue`**: Retry after OAuth authorization

## Tool Configuration

### Simple Toolkit Access
```yaml
agents:
  agent-name:
    tools:
      - Gmail    # All Gmail tools
      - Jira     # All Jira tools
```

### Specific Tool Filtering
```yaml
agents:
  agent-name:
    tools:
      - toolkit: Jira
        tools:
          - CreateIssue
          - GetIssue
          - UpdateIssue
```

## OAuth Authorization Flow

1. Agent attempts to use a tool requiring authorization
2. System shows authorization URL: `🔒 Authorization required: https://...`
3. Complete OAuth in your browser
4. Type `continue` to retry the request
5. System maintains auth state for the session

## Environment Variables

- `OPENAI_API_KEY`: Required for agent LLMs
- `ARCADE_API_KEY`: Optional, for tool access  
- `ARCADE_USER_ID`: Optional, for tool access

## Examples

### IT Helpdesk
```bash
python main.py supervisor-it-helpdesk.yaml "User can't login to email"
```

### Personal Assistant  
```bash
python main.py supervisor-personal-assistant.yaml "Schedule a meeting and email the team"
```

### Hierarchical Teams
```bash
python main.py hierarchical-complete-example.yaml "Get latest GitHub PR and create a Google doc about it"
```

## Debug Mode

Use `--debug` to see:
- Tool discovery process
- Agent routing decisions  
- Tool execution details
- Authorization flows
- Full LangGraph execution events

```bash
python main.py --debug agents.yaml "Create a Jira ticket"
```

## Tips for Success

1. **Start Simple**: Begin with single agents, add routing when needed
2. **Use Debug Mode**: Add `--debug` to understand system behavior
3. **Test Incrementally**: Use `reset` command between tests in interactive mode
4. **Design Clear Boundaries**: Each agent should have ONE primary responsibility
5. **Handle Auth Gracefully**: Complete OAuth flows and use `continue`

## Advanced Features

- **Hierarchical Teams**: Multi-level supervisors managing specialist agents
- **Department Isolation**: Each department operates independently 
- **Smart Context**: Agents see conversation history to avoid duplicate work
- **Template Variables**: Use `{{date}}` in instructions for dynamic content
- **Conversation Tracking**: Full history maintained through graph state

## MCP Client Implementation

This system includes a **native MCP (Model Context Protocol) client** that connects directly to MCP servers and gateways. Unlike wrapper libraries, this implementation uses the official MCP SDK to:

### What is MCP?

MCP is an open protocol that standardizes how applications provide tools and context to LLMs. Instead of creating custom integrations for every service, MCP provides a universal interface:

```
Your Agents → MCP Client → MCP Gateway/Server → Tools (Gmail, Jira, GitHub, etc.)
```

### How Our MCP Client Works

1. **Connection**: Creates HTTP-based MCP sessions using `streamablehttp_client`
2. **Discovery**: Queries MCP servers with `list_tools()` to discover available tools
3. **Conversion**: Transforms MCP tool schemas into LangChain `StructuredTool` objects
4. **Execution**: Wraps each tool call in a new MCP session with `call_tool()`
5. **Authorization**: Detects auth requirements from tool responses and surfaces OAuth URLs

### Configuration Options

**Option 1: Explicit MCP Servers** (Recommended)

The system supports various authentication methods for MCP servers:

```yaml
mcpServers:
  # Header-based authentication
  arcade:
    url: https://api.arcade.dev/mcp
    headers:
      Authorization: Bearer ${ARCADE_API_KEY}
      Arcade-User-ID: ${ARCADE_USER_ID}
  
  # Query parameter authentication (API key in URL)
  api_key_server:
    url: https://api.example.com/mcp?api_key=${API_KEY}&user=${USER_ID}
    # No headers needed!
  
  # Custom header authentication
  custom_server:
    url: https://your-mcp-server.com/mcp
    headers:
      X-API-Key: ${CUSTOM_API_KEY}
      X-Custom-Header: some-value
  
  # No authentication (open server)
  local_dev:
    url: http://localhost:3000/mcp
```

**Environment Variable Substitution:**
- Use `${VAR_NAME}` syntax anywhere in `url` or `headers`
- Works with multiple variables: `url: https://api.com/mcp?key=${KEY}&id=${ID}`
- Falls back to literal string if environment variable not found

**Option 2: Backward Compatible** (Auto-detects Arcade)
```yaml
# Just define tools - system auto-connects to Arcade MCP gateway
agents:
  assistant:
    tools: [Gmail, Jira]
```

### Authentication & OAuth Support

The system handles two types of OAuth/authorization:

**1. Tool-Level OAuth** (Fully Automatic):
```yaml
# Agent tries to use Gmail.SendEmail
# → Tool requires OAuth → System shows auth URL
# → User authorizes → Types 'continue' → Request succeeds
```

**2. Server-Level OAuth** (Manual Configuration):
```yaml
mcpServers:
  oauth_server:
    url: https://oauth-mcp-server.com/mcp
    headers:
      Authorization: Bearer ${OAUTH_TOKEN}
      # You must obtain this token through the server's OAuth flow first
```

**How to Handle Server-Level OAuth:**
1. Visit the MCP server's documentation for OAuth setup
2. Complete their OAuth flow to get an access token
3. Store the token in your `.env` file
4. Reference it in your YAML config with `${TOKEN_VAR}`

**Error Detection:**
- System detects 401/403 errors during server connection
- Provides helpful error messages for authorization issues
- Tool-level OAuth is handled automatically with interactive prompts

### Key Features

- **Multi-Server Support**: Connect to multiple MCP servers simultaneously
- **Automatic Tool Discovery**: No manual tool registration needed
- **Session Management**: Creates fresh MCP sessions for each tool call
- **Environment Variables**: Supports `${VAR}` syntax in URLs and headers
- **Error Handling**: Gracefully handles MCP session termination messages
- **Authorization Flow**: Automatically detects OAuth requirements (tool-level)
- **Flexible Auth**: Supports headers, query params, or no auth

## Architecture Overview

```
YAML Config → MCP Client → Tool Discovery → LangChain Agents → LangGraph Router
                ↓
         MCP Gateway/Server → External Tools (Gmail, Jira, etc.)
```

The system automatically:
1. Parses YAML configuration into agent definitions
2. Connects to MCP servers and discovers available tools
3. Converts MCP tools to LangChain format
4. Creates LangChain agents with OpenAI integration  
5. Builds LangGraph StateGraph for routing
6. Manages conversation flow and authorization

For technical implementation details, see [TECHNICAL.md](TECHNICAL.md).