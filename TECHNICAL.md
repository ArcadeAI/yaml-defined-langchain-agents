# Technical Documentation - YAML Agent System

## MCP Client Implementation

### Overview

The system implements a **native MCP (Model Context Protocol) client** that connects directly to MCP servers and gateways. This provides universal tool access without requiring service-specific integrations.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        YAML Configuration                        │
│  - mcpServers: Define gateway URLs and headers                   │
│  - agents.tools: Specify which toolkits each agent can access    │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MCP Client Initialization                      │
│  1. Parse mcpServers configuration                               │
│  2. Create HTTP-based MCP sessions per server                    │
│  3. Call list_tools() on each MCP server                         │
│  4. Convert MCP tool schemas → LangChain StructuredTools         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Tool Execution Flow                           │
│  Agent → LangChain Tool → MCP Client → MCP Server → External API │
│                              ↓                                    │
│                    Create new MCP session                         │
│                    Call tool with arguments                       │
│                    Parse response (text/error)                    │
│                    Handle auth requirements                       │
└──────────────────────────────────────────────────────────────────┘
```

### MCP Server Configuration

The system supports two configuration modes:

#### 1. Explicit MCP Servers (Recommended)

```yaml
mcpServers:
  arcade:
    url: https://api.arcade.dev/mcp
    headers:
      Authorization: ${ARCADE_API_KEY}
      Arcade-User-ID: ${ARCADE_USER_ID}
  
  custom_server:
    url: https://your-mcp-gateway.com
    headers:
      X-API-Key: ${CUSTOM_API_KEY}
```

**Features**:
- Connect to multiple MCP servers simultaneously
- Environment variable substitution with `${VAR}` syntax
- Custom headers per server
- Automatic Arcade credential injection from `.env` file

#### 2. Backward Compatible Mode

```yaml
agents:
  assistant:
    tools: [Gmail, Jira]  # Auto-connects to Arcade MCP gateway
```

If no `mcpServers` defined but agents have tools, system automatically connects to `ARCADE_MCP_GATEWAY` using credentials from environment.

### MCP Client Initialization Process

#### Step 1: Parse Configuration and Connect

```python
async def _initialize_mcp_servers(self):
    """Initialize tools from explicitly configured MCP servers."""
    mcp_servers = self.config.get('mcpServers', {})
    
    for server_name, server_config in mcp_servers.items():
        url = server_config.get('url')
        headers = server_config.get('headers', {})
        
        # Process environment variable substitution
        processed_headers = {}
        for key, value in headers.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                processed_headers[key] = os.getenv(env_var, value)
            else:
                processed_headers[key] = value
        
        # Automatically inject Arcade credentials if not specified
        if 'Authorization' not in processed_headers:
            arcade_key = os.getenv('ARCADE_API_KEY')
            if arcade_key:
                processed_headers['Authorization'] = f"Bearer {arcade_key}"
        
        if 'Arcade-User-ID' not in processed_headers:
            user_id = os.getenv('ARCADE_USER_ID')
            if user_id:
                processed_headers['Arcade-User-ID'] = user_id
```

#### Step 2: Create MCP Session and Discover Tools

```python
        # Connect to MCP server using streamable HTTP client
        async with streamablehttp_client(url, headers=processed_headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                # Initialize MCP protocol handshake
                await session.initialize()
                
                # List all available tools from this server
                tools_response = await session.list_tools()
                
                # Store connection info for later tool execution
                self.mcp_sessions[server_name] = {
                    'url': url,
                    'headers': processed_headers
                }
                
                # Convert each MCP tool to LangChain format
                for mcp_tool in tools_response.tools:
                    langchain_tool = self._mcp_tool_to_langchain(
                        mcp_tool, url, processed_headers
                    )
                    self.tools.append(langchain_tool)
```

**Key Points**:
- Uses `streamablehttp_client` from MCP SDK for HTTP-based connections
- `ClientSession` manages MCP protocol communication
- `list_tools()` returns MCP tool schemas with name, description, inputSchema
- Each server's connection info stored in `self.mcp_sessions` for tool execution

### MCP Tool to LangChain Conversion

```python
def _mcp_tool_to_langchain(self, mcp_tool: types.Tool, gateway_url: str, 
                           headers: Dict[str, str]) -> StructuredTool:
    """Convert an MCP tool to a LangChain StructuredTool."""
    
    # Store original name for MCP calls
    original_tool_name = mcp_tool.name
    
    # Sanitize tool name for OpenAI API (replace dots with underscores)
    # OpenAI requires: ^[a-zA-Z0-9_-]+$
    sanitized_name = original_tool_name.replace('.', '_')
    
    # Create async function that calls the MCP tool
    async def call_mcp_tool(**kwargs):
        """Call the MCP tool through the gateway."""
        result_text = None
        auth_error = None
        
        try:
            # Create new session for each call (MCP best practice)
            async with streamablehttp_client(gateway_url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as new_session:
                    await new_session.initialize()
                    
                    # Call the tool using original MCP name
                    result = await new_session.call_tool(original_tool_name, kwargs)
                    
                    # Check if result indicates error (like authorization)
                    if result.isError if hasattr(result, 'isError') else False:
                        error_content = []
                        for content in result.content:
                            if isinstance(content, types.TextContent):
                                error_content.append(content.text)
                        error_msg = "\n".join(error_content)
                        
                        # Check if it's an authorization error
                        if "authorization" in error_msg.lower() or "authorize" in error_msg.lower():
                            auth_error = f"🔒 AUTHORIZATION_REQUIRED: {error_msg}"
                        else:
                            raise Exception(f"Tool error: {error_msg}")
                    
                    # Extract text content from result
                    if not auth_error:
                        if result.content:
                            text_parts = []
                            for content in result.content:
                                if isinstance(content, types.TextContent):
                                    text_parts.append(content.text)
                                elif isinstance(content, types.ImageContent):
                                    text_parts.append(f"[Image: {content.mimeType}]")
                                elif isinstance(content, types.EmbeddedResource):
                                    if hasattr(content.resource, 'text'):
                                        text_parts.append(content.resource.text)
                            
                            result_text = "\n".join(text_parts) if text_parts else "Tool executed successfully"
                            
                            # Also check result text for auth URLs
                            if "authorization_url" in result_text.lower():
                                try:
                                    import json
                                    data = json.loads(result_text)
                                    if "authorization_url" in data:
                                        auth_error = f"🔒 AUTHORIZATION_REQUIRED: {data['authorization_url']}"
                                except json.JSONDecodeError:
                                    pass
                        else:
                            result_text = "Tool executed successfully"
                        
        except Exception as session_error:
            # Suppress harmless "Session termination failed: 202" errors
            error_msg = str(session_error)
            if "Session termination failed" not in error_msg and "202" not in error_msg:
                raise
        
        # If we found an auth error, raise it
        if auth_error:
            raise Exception(auth_error)
        
        return result_text if result_text else "Tool executed successfully"
    
    # Parse input schema from MCP tool
    input_schema = mcp_tool.inputSchema if hasattr(mcp_tool, 'inputSchema') else {}
    
    # Create LangChain StructuredTool with sanitized name
    return StructuredTool(
        name=sanitized_name,
        description=mcp_tool.description or f"Tool: {original_tool_name}",
        coroutine=call_mcp_tool,
        args_schema=None,  # Could parse inputSchema to create pydantic model
    )
```

**Critical Implementation Details**:

1. **Name Sanitization**: MCP tools use dots (e.g., `Gmail.SendMessage`) but OpenAI API requires `^[a-zA-Z0-9_-]+$`, so we replace dots with underscores for LangChain while preserving original name for MCP calls

2. **Fresh Sessions**: Each tool call creates a new MCP session. This is required because:
   - MCP sessions are not thread-safe
   - Sessions may timeout between calls
   - Ensures clean state for each execution

3. **Content Type Handling**: MCP supports multiple content types:
   - `TextContent`: Plain text responses
   - `ImageContent`: Images with MIME type
   - `EmbeddedResource`: Structured data with text

4. **Authorization Detection**: Checks for auth requirements in:
   - `result.isError` flag from MCP response
   - Error messages containing "authorization"/"authorize"
   - JSON responses with `authorization_url` field

5. **Error Suppression**: MCP SDK sometimes throws benign "Session termination failed: 202" errors during cleanup - these are suppressed

### Tool Discovery and Registration

```python
# After connecting to all MCP servers:
self.tools = []  # List of all LangChain StructuredTools

for server_name, server_config in mcp_servers.items():
    # ... connect to server ...
    
    tools_response = await session.list_tools()
    
    for mcp_tool in tools_response.tools:
        langchain_tool = self._mcp_tool_to_langchain(mcp_tool, url, processed_headers)
        self.tools.append(langchain_tool)
```

**Result**: Single flat list of all tools from all MCP servers, ready for agent assignment

### Agent-Specific Tool Filtering

```python
def _get_agent_tools(self, tool_configs: List[Union[str, Dict[str, Any]]]) -> List:
    """Filter tools for specific agent based on configuration."""
    agent_tools = []
    
    for tool_spec in tool_configs:
        if isinstance(tool_spec, str):
            # Simple toolkit: "Jira" → all Jira tools
            toolkit_name = tool_spec.lower()
            matching_tools = [t for t in self.tools if toolkit_name in t.name.lower()]
            agent_tools.extend(matching_tools)
            
        elif isinstance(tool_spec, dict):
            # Specific tools: {"toolkit": "Jira", "tools": ["CreateIssue"]}
            toolkit = tool_spec['toolkit'].lower()
            specific_tools = tool_spec['tools']
            
            for tool_name in specific_tools:
                matching_tools = [
                    t for t in self.tools 
                    if toolkit in t.name.lower() and tool_name.lower() in t.name.lower()
                ]
                agent_tools.extend(matching_tools)
    
    return agent_tools
```

## Request Processing Flow

### Execution Pipeline

```python
async def process_request(self, user_input: str) -> List[str]:
    # Create initial state
    initial_state = YAMLAgentState(
        messages=[HumanMessage(content=user_input)],
        conversation_history=self.conversation.copy(),
        completed_supervisors={}
    )
    
    # Configure execution
    config = {
        "recursion_limit": max_iterations,
        "configurable": {"user_id": user_id}
    }
    
    # Stream execution events
    async for event in self.graph.astream(initial_state, config):
        # Handle authorization interrupts
        if "__interrupt__" in event:
            interrupt_data = event["__interrupt__"]
            if hasattr(interrupt_data[0], 'value'):
                interrupt_msg = interrupt_data[0].value
                if "http" in interrupt_msg:
                    self.auth_required = interrupt_msg
                    return [f"🔒 AUTHORIZATION_REQUIRED: {interrupt_msg}"]
        
        # Process agent responses
        for node_name, node_state in event.items():
            if "messages" in node_state:
                # Extract and return agent responses
```

### MCP Authorization Flow

Unlike traditional LangGraph interrupts, this implementation handles authorization through **exception-based flow** in the MCP tool wrapper:

```
Agent calls tool → MCP call_tool() → MCP Server → Tool requires auth
                                                          ↓
                            Raises exception ← Returns error with auth_url
                                    ↓
                    LangGraph sees ToolMessage error ← LangChain catches exception
                                    ↓
              System detects "🔒 AUTHORIZATION_REQUIRED:" in messages
                                    ↓
                         Surfaces auth URL to user
                                    ↓
                      User completes OAuth in browser
                                    ↓
                   User types "continue" command
                                    ↓
              System retries with valid credentials stored in MCP server
```

#### Authorization Detection in MCP Tools

```python
# In _mcp_tool_to_langchain coroutine
async def call_mcp_tool(**kwargs):
    result = await new_session.call_tool(original_tool_name, kwargs)
    
    # Check MCP result for error flag
    if result.isError:
        error_content = []
        for content in result.content:
            if isinstance(content, types.TextContent):
                error_content.append(content.text)
        error_msg = "\n".join(error_content)
        
        # Detect authorization errors
        if "authorization" in error_msg.lower() or "authorize" in error_msg.lower():
            auth_error = f"🔒 AUTHORIZATION_REQUIRED: {error_msg}"
            raise Exception(auth_error)
    
    # Also check successful responses for auth URLs
    if "authorization_url" in result_text.lower():
        try:
            data = json.loads(result_text)
            if "authorization_url" in data:
                auth_error = f"🔒 AUTHORIZATION_REQUIRED: {data['authorization_url']}"
                raise Exception(auth_error)
        except json.JSONDecodeError:
            pass
```

#### Authorization Detection in Graph Execution

```python
# In process_request, during graph streaming
async for event in self.graph.astream(initial_state, config):
    for node_name, node_state in event.items():
        if "messages" in node_state:
            messages = node_state["messages"]
            
            # Check for authorization in ToolMessage errors
            from langchain_core.messages import ToolMessage
            for msg in messages:
                if isinstance(msg, ToolMessage) and "🔒 AUTHORIZATION_REQUIRED:" in msg.content:
                    # Extract the authorization URL
                    import re
                    auth_match = re.search(
                        r'🔒 AUTHORIZATION_REQUIRED:\s*(https?://[^\s\'")\]]+)', 
                        msg.content
                    )
                    if auth_match:
                        auth_url = auth_match.group(1)
                        self.auth_required = auth_url
                        return [f"🔒 Authorization required: {auth_url}"]
```

#### Retry After Authorization

```python
# In main() interactive loop
elif user_input.lower() == 'continue' and system.auth_required:
    # Clear auth requirement
    system.auth_required = None
    
    # Get the last user message from conversation
    last_user_msg = None
    for msg in reversed(system.conversation):
        if msg.startswith("User:"):
            last_user_msg = msg.split("User:", 1)[1].strip()
            break
    
    if last_user_msg:
        # Retry the request - MCP server now has valid OAuth token
        responses = await system.process_request(last_user_msg)
```

**Key Points**:
- Authorization state stored server-side by MCP server (e.g., Arcade)
- Client doesn't store tokens - just retries after user completes OAuth
- Same MCP session headers work after authorization (server associates auth with user_id)

## State Management

### Conversation Context

- **Full History**: All agents see complete conversation history
- **Response Tracking**: Previous agent outputs marked to avoid duplication  
- **State Propagation**: Context flows through LangGraph state
- **Message Trimming**: Prevents overwhelming models with long contexts

### Supervisor Coordination  

- **Department Isolation**: Each department subgraph manages its own state
- **Completion Tracking**: System tracks which supervisors have finished
- **Sequential Routing**: Multi-department requests handled systematically

## Error Handling and Debugging

### Error Recovery

- **Graceful Degradation**: System continues with warnings for missing components
- **Tool Failures**: Caught via LangGraph interrupts and reported clearly
- **Agent Errors**: Wrapped and returned as user-friendly messages
- **Authorization Flows**: Automatic retry after OAuth completion

### Debug Mode Features

With `--debug` flag, the system provides:

```python
[GRAPH] Starting execution with max_iterations: 20
[GRAPH EVENT] {'master_supervisor': {...}}
[RESPONSE] From github: Latest PR is #545...
[TOOL CALL] Github_ListPullRequests  
[INTERRUPT] Authorization required: https://...
[GRAPH] Execution completed. Found 2 responses
```

## Routing Algorithms

### Hierarchical Department Detection

```python
def _find_department_agents(self, dept_supervisor):
    """Find agents managed by department supervisor."""
    dept_agents = []
    supervisor_config = self.config.get('agents', {}).get(dept_supervisor, {})
    supervisor_instructions = supervisor_config.get('instructions', '').lower()
    
    for agent_id, agent_config in self.config.get('agents', {}).items():
        if agent_id != dept_supervisor and agent_id not in supervisors:
            if agent_id.lower() in supervisor_instructions:
                dept_agents.append(agent_id)
    
    return dept_agents
```

### Content-Based Routing  

```python
def route_supervisor(state: YAMLAgentState):
    """Parse supervisor response to determine next agent."""
    messages = state.get("messages", [])
    last_message = messages[-1]
    content = last_message.content.strip().upper()
    
    # Check for completion
    if "COMPLETE" in content:
        return "END"
    
    # Find agent name in response
    for agent_id in self.agents:
        if agent_id.upper() in content:
            return agent_id
    
    return "END"
```

## Performance Optimizations

### Message Management

- **Context Trimming**: Prevents token overflow with long conversations
- **State Isolation**: Department subgraphs maintain separate contexts
- **Efficient Routing**: Direct agent lookup vs expensive pattern matching

```python
def _trim_messages(self, messages: List, max_messages: int = 10):
    """Keep first message (original request) and recent context."""
    if len(messages) <= max_messages:
        return messages
    
    return [messages[0]] + messages[-(max_messages-1):]
```

### Tool Performance

- **Shared ToolManager**: Single instance across all agents
- **Lazy Loading**: Tools only initialized when needed
- **Filtered Access**: Agents only get relevant tools to reduce overhead

## Implementation Details

### Graph Execution Modes

**Single Agent**:
```
START → agent → END
```

**Flat Multi-Agent**:
```
START → supervisor → worker_agent → tools → supervisor → END
```

**Hierarchical Teams**:
```
START → master_supervisor → dept_supervisor_subgraph → master_supervisor → END
                                    ↓
                            [dept_supervisor → worker → tools → dept_supervisor]
```

### Tool Call Flow

```python
# Agent makes tool call
agent → [tool_calls: [{name: "Gmail_SendEmail", args: {...}}]]

# LangGraph routes to tools node  
tools_node → [executes tool via Arcade API]

# Results return to agent
agent ← [tool_results: "Email sent successfully"]

# Agent processes results and responds
agent → [final_response: "I've sent the email to..."]
```

### Authorization Interrupt Flow

```python
# Tool requires auth
tool_execution → [throws PermissionDeniedError with auth URL]

# LangGraph creates interrupt
graph → [interrupt: "Please authorize: https://..."]

# System catches interrupt
process_request → [returns: "🔒 AUTHORIZATION_REQUIRED: https://..."]

# User completes OAuth, retries
continue → [re-executes with valid auth]
```

## Configuration Schema

### Agent Definition

```yaml
agents:
  agent_name:
    model: gpt-4                    # OpenAI model name
    temperature: 0.7                # Model temperature  
    instructions: |                 # System prompt
      Your role and capabilities...
      Template variables: {{date}}
    tools:                          # Tool configuration
      - ToolkitName                 # Simple: all tools from toolkit
      - toolkit: ToolkitName        # Advanced: specific tools
        tools:
          - SpecificTool1
          - SpecificTool2
```

### Routing Configuration

```yaml
routing:
  supervisor: supervisor_agent_name    # Which agent coordinates
  max_iterations: 20                   # Max routing loops
```

## Advanced Features

### Template Variables

Currently supported in instructions:
- `{{date}}`: Current date in YYYY-MM-DD format

### Supervisor Intelligence

Supervisors use content analysis to route:
- **Keyword Detection**: Looks for agent names in responses
- **Completion Recognition**: "COMPLETE" triggers workflow end
- **Multi-Department**: Routes across departments based on request content

### Department Specialization

Each department operates independently:
- **Isolated State**: No cross-department state interference
- **Specialized Tools**: Department agents only access relevant tools
- **Clean Boundaries**: Agents enforce their domain limitations

## Error Handling Strategies

### Graceful Degradation

```python
# Missing Arcade
if not HAS_ARCADE:
    print("⚠️  Arcade not installed. Tool functionality disabled.")

# Missing API keys  
if not arcade_key:
    print("⚠️  ARCADE_API_KEY not set. Tool functionality limited.")

# Tool initialization failures
except Exception as e:
    print(f"Warning: Could not initialize tools: {e}")
```

### Runtime Error Recovery

```python
try:
    async for event in self.graph.astream(initial_state, config):
        # Process events
except Exception as e:
    if self.debug:
        traceback.print_exc()
    return [f"Error: {str(e)}"]
```

## Complete MCP Lifecycle

### 1. System Startup

```python
system = YAMLAgentSystem(config_file, debug=True)
await system.initialize()
```

**What Happens**:
- Loads YAML configuration
- Detects `mcpServers` or auto-configures Arcade gateway
- For each MCP server:
  - Processes environment variable substitution (`${VAR}`)
  - Creates `streamablehttp_client` connection
  - Establishes `ClientSession`
  - Calls `session.initialize()` (MCP handshake)
  - Calls `session.list_tools()` (tool discovery)
  - Converts each MCP tool to LangChain format
- Stores all tools in `self.tools` list
- Creates LangChain agents with filtered tools
- Builds LangGraph routing structure

### 2. Tool Execution

```python
# Agent decides to call a tool
responses = await system.process_request("Send email to john@example.com")
```

**What Happens**:
1. User request → LangGraph → Supervisor agent
2. Supervisor routes to email specialist agent
3. Email agent calls `Gmail_SendMessage` tool
4. LangChain invokes tool's coroutine function
5. Tool coroutine creates **new MCP session**:
   ```python
   async with streamablehttp_client(gateway_url, headers=headers) as (read, write, _):
       async with ClientSession(read, write) as new_session:
           await new_session.initialize()
           result = await new_session.call_tool(tool_name, arguments)
   ```
6. MCP server executes tool via external API
7. MCP server returns result (or error)
8. Tool coroutine parses result content
9. LangChain receives tool result as string
10. Agent processes result and formulates response

### 3. Authorization Flow

```python
# When tool requires authorization
responses = await system.process_request("Read my Gmail inbox")
# → ["🔒 Authorization required: https://arcade.dev/auth?token=..."]

# User clicks URL, completes OAuth, returns to terminal
responses = await system.process_request("continue")
# → System retries with now-authorized session
```

**What Happens**:
1. Tool call reaches MCP server without authorization
2. MCP server returns `isError: true` with authorization URL
3. Tool coroutine detects auth keywords and raises exception
4. LangChain catches exception → creates ToolMessage with error
5. Graph execution continues, system checks all ToolMessages
6. System detects `🔒 AUTHORIZATION_REQUIRED:` pattern
7. Returns auth URL to user interface
8. User completes OAuth (authorization stored server-side)
9. User types "continue"
10. System retries **exact same request**
11. MCP server now has valid OAuth token for this user_id
12. Tool executes successfully

### 4. Session Management

**Why Fresh Sessions Per Call?**

```python
# Each tool call does this:
async with streamablehttp_client(url, headers=headers) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(tool_name, arguments)
# Session automatically closed when exiting context
```

**Rationale**:
- MCP sessions are not thread-safe (concurrent tool calls)
- Sessions may timeout between calls (long-running graphs)
- Clean state for each execution (no side effects)
- Handles connection errors gracefully (auto-reconnect)
- MCP SDK best practice for HTTP-based clients

**Performance Considerations**:
- Session creation adds ~50-100ms overhead per tool call
- HTTP/2 connection pooling helps (if supported by MCP server)
- Alternative: connection pooling with session reuse (not implemented)

### 5. Error Handling

**MCP SDK Errors**:
- `Session termination failed: 202` → Suppressed (benign cleanup error)
- Connection errors → Propagated to user with clear message
- Tool execution errors → Returned in ToolMessage for agent to see

**Authorization Errors**:
- Detected via `result.isError` flag
- Detected via "authorization"/"authorize" keywords in error text
- Detected via `authorization_url` field in JSON responses
- All converted to `🔒 AUTHORIZATION_REQUIRED:` format

**Tool Result Parsing**:
- `TextContent` → Extracted as plain text
- `ImageContent` → Formatted as `[Image: mime/type]`
- `EmbeddedResource` → Extracted text field if available
- Empty/missing content → Returns "Tool executed successfully"

## Best Practices for Extension

### Working with MCP

#### Adding New MCP Servers

```yaml
mcpServers:
  your_server:
    url: https://your-mcp-server.com
    headers:
      X-API-Key: ${YOUR_API_KEY}
      X-User-ID: ${YOUR_USER_ID}
```

**Checklist**:
1. Ensure server implements MCP protocol (supports `list_tools`, `call_tool`)
2. Test connection with debug mode: `python main.py --debug`
3. Verify tools appear in discovery: Look for `[MCP] Found N tools from your_server`
4. Test authorization flow if tools require OAuth
5. Handle any server-specific error formats

#### Debugging MCP Issues

**Enable debug mode**:
```bash
python main.py --debug config.yaml "test request"
```

**Look for**:
- `[MCP] Connecting to server_name at url` → Connection attempt
- `[MCP] Found N tools from server_name` → Successful discovery
- `[MCP]   - tool_name: description` → Individual tool listing
- `[TOOL CALL] tool_name` → Tool execution in graph
- `[ERROR]` messages → Connection or execution errors

**Common Issues**:
1. **"MCP SDK not installed"** → `pip install mcp`
2. **"Could not initialize MCP servers"** → Check URL and credentials
3. **"Session termination failed: 202"** → Harmless, ignored automatically
4. **Authorization loops** → User may not have completed OAuth properly
5. **Tool not found** → Check tool name sanitization (dots → underscores)

#### Custom Tool Filtering

```yaml
agents:
  email_agent:
    tools:
      - toolkit: Gmail  # All Gmail tools
      - toolkit: Jira
        tools:
          - CreateIssue  # Only specific Jira tools
          - GetIssue
```

**Filtering Logic**:
```python
# Simple toolkit: "Gmail"
matching_tools = [t for t in self.tools if "gmail" in t.name.lower()]

# Specific tools: toolkit="Jira", tools=["CreateIssue"]
matching_tools = [
    t for t in self.tools 
    if "jira" in t.name.lower() and "createissue" in t.name.lower()
]
```

### Adding New Agent Types

1. Define clear boundaries in instructions
2. Specify only necessary tools (filtered access)
3. Test single-agent functionality first
4. Add routing keywords to supervisor
5. Test with debug mode to see tool discovery

### Implementing New Toolkits

1. Add MCP server to `mcpServers` configuration
2. Verify tools discovered via `list_tools()`
3. Add to agent tool configurations
4. Test authorization flows (if OAuth required)
5. Handle toolkit-specific errors in tool coroutines

### Creating New Routing Patterns

1. Extend `_identify_supervisors` for detection
2. Add routing logic in `_create_graph`
3. Implement department finding logic
4. Test with debug mode to verify routing decisions

## MCP Protocol Compliance

### What is MCP?

The **Model Context Protocol (MCP)** is an open protocol developed by Anthropic that standardizes how applications provide context to LLMs. It defines:

1. **Server-Client Architecture**: Applications expose tools/resources via MCP servers
2. **Standardized API**: Common interface for tool discovery and execution
3. **Transport Layer**: Supports stdio, HTTP, and WebSocket transports
4. **Content Types**: Text, images, and embedded resources

### MCP Protocol Components

This implementation uses the following MCP protocol features:

#### 1. Client Initialization

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Create HTTP transport
async with streamablehttp_client(url, headers=headers) as (read, write, _):
    # Create MCP session
    async with ClientSession(read, write) as session:
        # Initialize protocol handshake
        await session.initialize()
```

**Protocol Flow**:
- Client sends `initialize` request with protocol version
- Server responds with capabilities and tool metadata
- Session ready for tool operations

#### 2. Tool Discovery (`list_tools`)

```python
tools_response = await session.list_tools()

for mcp_tool in tools_response.tools:
    print(f"Tool: {mcp_tool.name}")
    print(f"Description: {mcp_tool.description}")
    print(f"Schema: {mcp_tool.inputSchema}")
```

**MCP Tool Schema**:
```typescript
interface Tool {
  name: string;              // e.g., "Gmail.SendMessage"
  description?: string;      // Human-readable description
  inputSchema: JSONSchema;   // JSON Schema for parameters
}
```

#### 3. Tool Execution (`call_tool`)

```python
result = await session.call_tool(tool_name, arguments)

# Result structure
interface CallToolResult {
  content: Content[];     // Array of text/image/resource content
  isError?: boolean;      // True if execution failed
}
```

**Content Types Supported**:
```python
# Text content
types.TextContent:
    text: str

# Image content  
types.ImageContent:
    data: str
    mimeType: str

# Embedded resource
types.EmbeddedResource:
    resource: {
        uri: str
        text?: str
        blob?: str
    }
```

#### 4. Session Management

**Per MCP Specification**:
- Sessions should be short-lived for HTTP transport
- Each request should create a new session
- Sessions automatically closed when context exits

**Our Implementation**:
```python
# Tool discovery: One session at startup
async with streamablehttp_client(url, headers) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
# Session automatically closed

# Tool execution: Fresh session per call
async with streamablehttp_client(url, headers) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(name, args)
# Session automatically closed
```

### HTTP Transport Implementation

This implementation uses **streamable HTTP transport** (`streamablehttp_client`):

```python
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(url, headers=headers) as (read, write, _):
    # read: AsyncIterable for reading server messages
    # write: Callable for writing client messages
    # _: Context manager for cleanup
    ...
```

**Transport Features**:
- HTTP/1.1 or HTTP/2 connections
- Server-sent events (SSE) for streaming responses
- Custom headers for authentication (Authorization, User-ID, etc.)
- Connection pooling (if supported by underlying HTTP client)

### Protocol-Specific Behaviors

#### Authorization Flow

MCP doesn't define authorization in the core protocol. Implementation-specific behavior:

**Arcade MCP Gateway**:
- Returns `isError: true` with authorization URL in error message
- Authorization state stored server-side keyed by `Arcade-User-ID` header
- After OAuth completion, subsequent calls with same User-ID succeed

**Our Authorization Handling**:
```python
if result.isError:
    error_msg = extract_error_message(result)
    if "authorization" in error_msg.lower():
        # Surface auth URL to user
        raise Exception(f"🔒 AUTHORIZATION_REQUIRED: {error_msg}")
```

#### Error Handling

MCP defines error responses but not specific error codes:

```python
# MCP error response
CallToolResult {
    content: [TextContent("Error message here")],
    isError: true
}

# Our implementation checks:
1. result.isError flag
2. Error message keywords ("authorization", "permission")
3. Tool-specific error formats (JSON with error fields)
```

#### Content Extraction

```python
def extract_content(result: CallToolResult) -> str:
    text_parts = []
    
    for content in result.content:
        if isinstance(content, types.TextContent):
            text_parts.append(content.text)
        elif isinstance(content, types.ImageContent):
            text_parts.append(f"[Image: {content.mimeType}]")
        elif isinstance(content, types.EmbeddedResource):
            if hasattr(content.resource, 'text'):
                text_parts.append(content.resource.text)
    
    return "\n".join(text_parts) if text_parts else "Tool executed successfully"
```

### Compatibility Notes

**Works With**:
- ✅ Arcade MCP Gateway (`https://api.arcade.dev/mcp`)
- ✅ Any MCP server implementing HTTP transport
- ✅ MCP servers with custom authentication headers
- ✅ Multi-server configurations

**Limitations**:
- ❌ Does not support stdio transport (process-based MCP servers)
- ❌ Does not support WebSocket transport
- ❌ Does not implement MCP resources (only tools)
- ❌ Does not implement MCP prompts
- ❌ Does not convert `inputSchema` to Pydantic models (uses dynamic args)

**Future Enhancements**:
- Parse `inputSchema` to create typed Pydantic models for better validation
- Support stdio transport for local MCP servers
- Implement MCP resources for context retrieval
- Connection pooling for reduced latency
- Caching of tool discovery results

## Performance Considerations

### Memory Usage

- **State Size**: Conversation history grows with usage
- **Tool Loading**: All tools loaded at startup (could lazy-load)
- **Graph Complexity**: Hierarchical graphs use more memory
- **MCP Sessions**: Fresh session per call (no long-lived connections)

### Execution Speed

- **Sequential Processing**: Agents execute one at a time
- **Tool Latency**: API calls add execution time  
- **Routing Overhead**: Complex routing adds processing time
- **MCP Overhead**: ~50-100ms per tool call for session creation

### Optimization Strategies

- Use `max_iterations` to prevent infinite loops
- Implement message trimming for long conversations
- Filter tools precisely per agent to reduce token usage
- Use debug mode to identify bottlenecks
- Consider connection pooling for high-frequency tool use
- Cache tool discovery results (currently re-fetched at startup)

## Security Considerations

- **API Keys**: Stored in environment variables, not code
- **MCP Headers**: Credentials passed via HTTP headers (ensure HTTPS)
- **Tool Permissions**: Agent-specific tool filtering
- **Authorization**: OAuth flows handled server-side by MCP gateway
- **Input Validation**: Basic YAML validation and error handling
- **Session Isolation**: Fresh sessions prevent state leakage between calls

For user documentation and examples, see [README.md](README.md).
