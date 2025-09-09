# YAML-Driven Agent System

A powerful yet simple multi-agent system using LangChain and LangGraph. Define everything in YAML - no coding required!

## Key Features

- **Pure YAML Configuration**: Define agents, tools, and routing in YAML
- **Hierarchical Agent Teams**: Multi-level supervisor architecture with department specialization  
- **Automatic Tool Discovery**: Agents automatically discover and use Arcade tools
- **Smart OAuth Handling**: Built-in authorization flow with proper interrupt handling
- **Flexible Routing**: From simple single agents to complex multi-department workflows
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

3. **Run Phoenix (observability)**
   ```bash
   phoenix serve &
   ```
   View will be able to view traces at http://localhost:6006/
   
4. **Run the system**:
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

## Architecture Overview

```
YAML Config → main.py → LangChain Agents → LangGraph Router → Arcade Tools
```

The system automatically:
1. Parses YAML configuration into agent definitions
2. Creates LangChain agents with OpenAI integration  
3. Builds LangGraph StateGraph for routing
4. Discovers and registers Arcade tools
5. Manages conversation flow and authorization

For technical implementation details, see [TECHNICAL.md](TECHNICAL.md).