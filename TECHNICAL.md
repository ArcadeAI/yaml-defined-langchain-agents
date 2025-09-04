# Technical Documentation - YAML Agent System

## Architecture Overview

The system implements a **YAML-driven multi-agent framework** using LangChain and LangGraph with support for both flat and hierarchical agent teams. It automatically creates agents from YAML configuration and integrates with Arcade for tool functionality.

```
┌─────────────┐     ┌──────────────────────────────────────┐     ┌─────────────────┐
│ agents.yaml │ ──> │              main.py                 │ ──> │  Agent System   │
│ (Config)    │     │                                      │     │ (Runtime)       │
└─────────────┘     │  1. YAML config loading              │     └─────────────────┘
                    │  2. LangChain agent creation         │              │
                    │  3. LangGraph StateGraph building    │              ▼
                    │  4. Arcade tool discovery            │    ┌─────────────────┐
                    │  5. Hierarchical routing setup       │    │   Arcade API    │
                    │  6. Conversation flow management     │    │  (Tool access)  │
                    └──────────────────────────────────────┘    └─────────────────┘
```

## Core Classes and Components

### YAMLAgentSystem Class

Main orchestrator class responsible for:
- YAML configuration loading and parsing
- LangChain agent creation with OpenAI integration
- LangGraph StateGraph construction (flat and hierarchical)
- Arcade tool discovery and registration
- Conversation flow management through graph execution

```python
class YAMLAgentSystem:
    def __init__(self, config_path: str = "agents.yaml", debug: bool = False):
        self.config = {}                    # Parsed YAML configuration
        self.agents = {}                    # Created LangChain agents  
        self.arcade = None                  # Arcade client instance
        self.tools = []                     # LangChain tools from Arcade
        self.conversation = []              # Conversation history
        self.auth_required = None           # Track auth requirements
        self.graph = None                   # LangGraph StateGraph instance
        self.tool_manager = None            # Arcade ToolManager
```

### YAMLAgentState Class

LangGraph state management extending MessagesState:

```python
class YAMLAgentState(MessagesState):
    current_agent: Optional[str] = None              # Currently active agent
    auth_required: Optional[str] = None              # Authorization requirement
    conversation_history: List[str] = []             # Full conversation context
    completed_supervisors: Dict[str, str] = {}       # Track supervisor completion
```

## Agent Creation Process

### 1. Configuration Loading (`initialize()`)

```python
# Load YAML configuration
with open(self.config_path, 'r') as f:
    self.config = yaml.safe_load(f)

# Initialize Arcade if tools are present
if HAS_ARCADE and any(agent.get('tools') for agent in self.config.get('agents', {}).values()):
    self._initialize_tools()

# Create individual agents
for agent_id, agent_config in self.config.get('agents', {}).items():
    agent = self._create_agent(agent_id, agent_config)
    self.agents[agent_id] = agent
```

### 2. Individual Agent Creation (`_create_agent()`)

Each agent is created using LangChain's `create_react_agent`:

```python
def _create_agent(self, agent_id: str, config: Dict[str, Any]):
    # Create OpenAI model
    model = ChatOpenAI(
        model=config.get('model', 'gpt-4o'),
        temperature=config.get('temperature', 0.7),
        api_key=os.getenv('OPENAI_API_KEY')
    )
    
    # Process instructions with template variables
    instructions = config.get('instructions', '')
    instructions = instructions.replace('{{date}}', datetime.now().strftime("%Y-%m-%d"))
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", instructions),
        ("placeholder", "{messages}"),
    ])
    
    # Get agent-specific tools
    agent_tools = self._get_agent_tools(config.get('tools', []))
    
    # Create react agent
    return create_react_agent(
        model=model.bind_tools(agent_tools),
        tools=agent_tools,
        prompt=prompt,
        name=agent_id
    )
```

## LangGraph Architecture

### Routing Pattern Detection

The system automatically detects whether to use flat or hierarchical routing:

```python
def _identify_supervisors(self):
    """Identify supervisors by analyzing instructions for routing keywords."""
    supervisors = set()
    
    for agent_id, agent_config in self.config.get('agents', {}).items():
        instructions = agent_config.get('instructions', '').lower()
        # Check if this agent routes to other agents
        if 'route' in instructions and any(other_id in instructions 
                                         for other_id in self.agents if other_id != agent_id):
            supervisors.add(agent_id)
    
    return supervisors
```

### 1. Flat Architecture (Single Supervisor)

For traditional supervisor → worker patterns:

```python
workflow = StateGraph(YAMLAgentState)

# Add all agents
for agent_id, agent in self.agents.items():
    workflow.add_node(agent_id, agent)

# Add tools node
workflow.add_node("tools", ToolNode(self.tools))

# Supervisor routing
def route_supervisor(state: YAMLAgentState):
    last_message = state["messages"][-1]
    content = last_message.content.strip().upper()
    
    if "COMPLETE" in content:
        return "END"
    
    # Check for agent names
    for agent_id in self.agents:
        if agent_id != supervisor_id and agent_id.upper() in content:
            return agent_id
    
    return "END"
```

### 2. Hierarchical Architecture (Multi-Level Supervisors)

For complex department-based workflows:

```python
# Detect hierarchical structure
if len(supervisors) > 1:
    department_supervisors = [s for s in supervisors if s != supervisor_id]
    
    # Create department subgraphs
    for dept_supervisor in department_supervisors:
        dept_agents = self._find_department_agents(dept_supervisor)
        dept_subgraph = self._create_department_subgraph(dept_supervisor, dept_agents)
        
        # Add entire department as single node
        workflow.add_node(dept_supervisor, dept_subgraph)
    
    # Master supervisor coordinates departments
    def route_main_supervisor(state: YAMLAgentState):
        content = state["messages"][-1].content.strip().upper()
        
        for dept_supervisor in department_supervisors:
            if dept_supervisor.upper() in content:
                return dept_supervisor
        
        return "END"
```

### 3. Department Subgraph Creation

Each department operates as an independent LangGraph:

```python
def _create_department_subgraph(self, department_supervisor_id, department_agents):
    """Create isolated subgraph for department."""
    subworkflow = StateGraph(YAMLAgentState)
    
    # Add department supervisor and agents
    subworkflow.add_node(department_supervisor_id, self.agents[department_supervisor_id])
    for agent_id in department_agents:
        subworkflow.add_node(agent_id, self.agents[agent_id])
    
    # Add tools for department
    subworkflow.add_node("tools", ToolNode(self.tools))
    
    # Department-specific routing
    def route_department(state: YAMLAgentState):
        content = state["messages"][-1].content.strip().upper()
        
        if "COMPLETE" in content:
            return "END"
        
        for agent_id in department_agents:
            if agent_id.upper() in content:
                return agent_id
        
        return "END"
    
    return subworkflow.compile()
```

## Arcade Tool Integration

### Tool Discovery and Registration

```python
def _initialize_tools(self):
    """Initialize Arcade tools with proper filtering."""
    # Get unique toolkits from all agents
    toolkits = set()
    for agent_config in self.config.get('agents', {}).values():
        for tool_spec in agent_config.get('tools', []):
            if isinstance(tool_spec, str):
                toolkits.add(tool_spec)
            elif isinstance(tool_spec, dict) and 'toolkit' in tool_spec:
                toolkits.add(tool_spec['toolkit'])
    
    # Initialize ToolManager
    self.tool_manager = ToolManager(
        api_key=os.getenv('ARCADE_API_KEY'),
        user_id=os.getenv('ARCADE_USER_ID', 'default')
    )
    self.tool_manager.init_tools(toolkits=list(toolkits))
    self.tools = self.tool_manager.to_langchain(use_interrupts=True)
```

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

### Authorization Handling

The system uses LangGraph's interrupt mechanism for OAuth:

1. **Tool Execution**: Agent attempts to call tool requiring auth
2. **Interrupt Generation**: LangGraph creates interrupt with auth URL
3. **User Authorization**: User completes OAuth in browser
4. **Retry Mechanism**: System retries with valid authorization

```python
# In process_request
if "__interrupt__" in event:
    interrupt_data = event["__interrupt__"]
    interrupt_msg = interrupt_data[0].value
    
    if "http" in interrupt_msg:
        self.auth_required = interrupt_msg
        return [f"🔒 AUTHORIZATION_REQUIRED: {interrupt_msg}"]
```

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

## Best Practices for Extension

### Adding New Agent Types

1. Define clear boundaries in instructions
2. Specify only necessary tools
3. Test single-agent functionality first
4. Add routing keywords to supervisor

### Implementing New Toolkits

1. Register toolkit in `_initialize_tools`
2. Add to agent tool configurations
3. Test authorization flows
4. Handle toolkit-specific errors

### Creating New Routing Patterns

1. Extend `_identify_supervisors` for detection
2. Add routing logic in `_create_graph`
3. Implement department finding logic
4. Test with debug mode

## Performance Considerations

### Memory Usage

- **State Size**: Conversation history grows with usage
- **Tool Loading**: All tools loaded regardless of agent assignment
- **Graph Complexity**: Hierarchical graphs use more memory

### Execution Speed

- **Sequential Processing**: Agents execute one at a time
- **Tool Latency**: API calls add execution time  
- **Routing Overhead**: Complex routing adds processing time

### Optimization Strategies

- Use `max_iterations` to prevent infinite loops
- Implement message trimming for long conversations
- Filter tools precisely per agent to reduce token usage
- Use debug mode to identify bottlenecks

## Security Considerations

- **API Keys**: Stored in environment variables, not code
- **Tool Permissions**: Agent-specific tool filtering
- **Authorization**: OAuth flows handled securely via interrupts
- **Input Validation**: Basic YAML validation and error handling

For user documentation and examples, see [README.md](README.md).
