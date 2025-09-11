# Tool Call Visibility Troubleshooting Guide

## Overview
The tool call visibility feature shows real-time information when agents use tools (like Jira, Gmail, Slack, etc.) during conversations.

## How It Works

### Expected Behavior
When an agent uses tools, you should see:

1. **Tool Call Message** (Purple background with 🔧 icon):
   - "🔧 Using Gmail tool: gmail_send_email"
   - Shows toolkit name and specific tool being used
   - Expandable details showing JSON arguments

2. **Tool Response Message** (Green background with ✅ icon):
   - "✅ Tool response: [response content]"
   - Shows the actual response from the tool
   - Added after the tool completes execution

3. **Final Agent Reply**:
   - The agent's response incorporating the tool results

## Common Issues and Solutions

### 1. Tool Calls Not Showing

**Symptoms:** Agent seems to work but no purple tool call messages appear

**Possible Causes:**
- Agent not configured with tools
- Tools not properly initialized
- Single agent mode issues (fixed in latest version)

**Solutions:**
1. **Check Agent Configuration:**
   - Ensure the agent has tools selected (e.g., "Gmail", "Jira", "Slack")
   - Verify ARCADE_API_KEY is set in `.env` file
   - Check that ARCADE_USER_ID is configured

2. **Check Server Logs:**
   - Look for debug messages like `[TOOL CALL DETECTED]` and `[TOOL RESPONSE DETECTED]`
   - If no tool initialization messages appear, check Arcade setup

3. **Test Tool Setup:**
   ```bash
   # In webapp directory
   python -c "
   from arcadepy import Arcade
   from langchain_arcade import ToolManager
   arcade = Arcade(api_key='your_api_key')
   manager = ToolManager(api_key='your_api_key', user_id='test_user')
   manager.init_tools(toolkits=['Gmail'])
   tools = manager.to_langchain()
   print(f'Loaded {len(tools)} tools')
   "
   ```

### 2. Authentication Issues

**Symptoms:** Tool calls appear but show authorization required messages

**Solutions:**
1. Click the authorization link when it appears
2. Complete the OAuth flow in the new window
3. Return to the chat and click "Continue After Authorization"
4. The tool should now execute successfully

### 3. Tool Call Detection Problems

**Symptoms:** Tools work but visibility doesn't show correctly

**Debug Steps:**
1. **Enable Debug Mode:** The system now runs with debug=True by default
2. **Check Server Output:** Look for these log messages:
   ```
   [TOOL CALL DETECTED] Node: agent, Tool calls: 1
   [TOOL CALL] {'type': 'tool_call', 'toolkit': 'Gmail', ...}
   [TOOL RESPONSE DETECTED] Node: tools, Content: Success...
   [TOOL RESPONSE] {'response': 'Success...', ...}
   ```

3. **Frontend Issues:** Check browser console for JavaScript errors

### 4. Specific Toolkit Issues

#### Gmail
- **Requirements:** Google OAuth setup, Gmail API enabled
- **Common Issue:** Scope permissions - ensure Gmail read/write access
- **Test Command:** Try simple email listing first

#### Jira
- **Requirements:** Jira API token, correct instance URL
- **Common Issue:** Authentication format (username:token vs token only)
- **Test Command:** Try getting issue information first

#### Slack
- **Requirements:** Slack app with bot token
- **Common Issue:** Channel permissions and bot scope
- **Test Command:** Try listing channels first

## Environment Setup

### Required Environment Variables
```bash
# In webapp/.env
ARCADE_API_KEY=your_arcade_api_key
ARCADE_USER_ID=your_user_id
OPENAI_API_KEY=your_openai_key

# Optional for specific tools
JIRA_API_TOKEN=your_jira_token
SLACK_BOT_TOKEN=your_slack_token
GMAIL_CREDENTIALS=path_to_credentials.json
```

### Arcade Setup
1. Sign up at https://arcade-ai.com
2. Get your API key from the dashboard
3. Configure toolkits you want to use
4. Set up OAuth for tools that require it

## Testing Tool Calls

### Step-by-Step Test Process

1. **Create a Test Agent:**
   - Name: "Gmail Test Agent"
   - Provider: OpenAI or LiteLLM
   - Model: gpt-4o (recommended)
   - Tools: Select "Gmail"
   - Instructions: "You are a helpful assistant that can manage emails using Gmail tools."

2. **Test Messages:**
   ```
   "List my recent emails"
   "Send a test email to myself with subject 'Test'"
   "Check if I have any unread emails"
   ```

3. **Expected Flow:**
   - User sends message
   - Purple tool call message appears: "🔧 Using Gmail tool: gmail_list_messages"
   - Expandable details show JSON arguments
   - Green response message: "✅ Tool response: Found 5 emails..."
   - Final agent reply summarizing the results

## Advanced Debugging

### Server-Side Debugging
Enable verbose logging by setting debug=True in agent creation:
```python
system = AgentSystem(config, debug=True)
```

### Frontend Debugging
Open browser DevTools and check:
1. Network tab for API responses
2. Console for JavaScript errors
3. Response data should include `tool_calls` array

### Graph Execution Flow
For single agents, the execution flow should be:
```
START → agent → tools → agent → END
```

With proper conditional edges to handle tool calls.

## Getting Help

If tool calls still aren't working:
1. Check all environment variables are set
2. Verify Arcade account and API key
3. Test with a simple tool like Gmail list operations
4. Check server logs for initialization errors
5. Ensure the agent has tools configured in the web interface

The debug output will help identify exactly where the issue occurs in the tool execution pipeline.