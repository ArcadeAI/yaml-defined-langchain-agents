#!/usr/bin/env python3
"""
YAML-driven agent system using LangChain and LangGraph with MCP client support.
Usage: python main.py [config.yaml] [request]
"""

import os
import sys
import yaml
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Suppress harmless MCP session termination warnings
import warnings
warnings.filterwarnings('ignore', message='.*Session termination failed.*')

# Phoenix/OpenInference Observability (optional)
try:
    import phoenix as px
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register
    
    # Auto-launch Phoenix for workshop simplicity
    phoenix_session = px.launch_app()
    print(f"🔍 Phoenix observability started at http://localhost:{phoenix_session.port}")
    
    # Register Phoenix tracer
    tracer_provider = register()
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    HAS_PHOENIX = True
except ImportError:
    HAS_PHOENIX = False
    print("⚠️  Phoenix observability not available. Install with: pip install arize-phoenix")

# LangChain/LangGraph imports
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent, ToolNode

# MCP SDK imports
try:
    from mcp import ClientSession, types
    from mcp.client.streamable_http import streamablehttp_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("⚠️  MCP SDK not installed. Tool functionality will be disabled.")
    print("   Install with: pip install mcp")


# Default Arcade MCP gateway URL
# This single gateway provides access to all Arcade tools
ARCADE_MCP_GATEWAY = os.getenv('ARCADE_MCP_GATEWAY', 'https://api.arcade.dev/mcp')


class YAMLAgentState(MessagesState):
    """State for the YAML-driven agent system."""
    current_agent: Optional[str] = None
    auth_required: Optional[str] = None
    conversation_history: List[str] = []
    completed_supervisors: Dict[str, str] = {}  # Track which supervisors have completed their work


class YAMLAgentSystem:
    """YAML-driven multi-agent system using LangChain and LangGraph with MCP client support."""
    
    def __init__(self, config_path: str = "agents.yaml", debug: bool = False):
        self.config_path = config_path
        self.config = {}
        self.agents = {}
        self.mcp_sessions = {}  # Store MCP client sessions by gateway URL
        self.tools = []
        self.conversation = []
        self.debug = debug
        self.auth_required = None
        self.graph = None
        
    async def initialize(self):
        """Load YAML and create agents."""
        # Load configuration
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize MCP tools
        if HAS_MCP:
            # Check if we have explicit mcpServers configuration
            if 'mcpServers' in self.config:
                await self._initialize_mcp_servers()
            # Otherwise, use backward-compatible Arcade gateway if agents have tools
            elif any(agent.get('tools') for agent in self.config.get('agents', {}).values()):
                arcade_key = os.getenv('ARCADE_API_KEY')
                user_id = os.getenv('ARCADE_USER_ID')
                
                if arcade_key and user_id:
                    await self._initialize_tools()
                else:
                    print("⚠️  ARCADE_API_KEY or ARCADE_USER_ID not set. Tool functionality will be limited.")
        
        # Create agents
        for agent_id, agent_config in self.config.get('agents', {}).items():
            agent = self._create_agent(agent_id, agent_config)
            self.agents[agent_id] = agent
            
        # Create routing graph
        self._create_graph()
        
        print(f"✓ Initialized {len(self.agents)} agents")
    
    async def _initialize_mcp_servers(self):
        """Initialize tools from explicitly configured MCP servers."""
        try:
            mcp_servers = self.config.get('mcpServers', {})
            
            if self.debug:
                print(f"[MCP] Found {len(mcp_servers)} configured MCP servers")
            
            self.tools = []
            
            for server_name, server_config in mcp_servers.items():
                url = server_config.get('url')
                headers = server_config.get('headers', {})
                
                # Support environment variable substitution in headers
                processed_headers = {}
                for key, value in headers.items():
                    if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                        env_var = value[2:-1]
                        processed_headers[key] = os.getenv(env_var, value)
                    else:
                        processed_headers[key] = value
                
                # Automatically add Arcade credentials from .env if not already specified
                if 'Authorization' not in processed_headers:
                    arcade_key = os.getenv('ARCADE_API_KEY')
                    if arcade_key:
                        processed_headers['Authorization'] = f"Bearer {arcade_key}"
                
                if 'Arcade-User-ID' not in processed_headers:
                    user_id = os.getenv('ARCADE_USER_ID')
                    if user_id:
                        processed_headers['Arcade-User-ID'] = user_id
                
                if self.debug:
                    print(f"[MCP] Connecting to {server_name} at {url}")
                
                # Connect to MCP server
                try:
                    async with streamablehttp_client(url, headers=processed_headers) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            
                            # List all available tools from this server
                            tools_response = await session.list_tools()
                            
                            if self.debug:
                                print(f"[MCP] Found {len(tools_response.tools)} tools from {server_name}")
                            
                            # Store connection info for this server
                            self.mcp_sessions[server_name] = {
                                'url': url,
                                'headers': processed_headers
                            }
                            
                            # Convert MCP tools to LangChain tools
                            for mcp_tool in tools_response.tools:
                                langchain_tool = self._mcp_tool_to_langchain(mcp_tool, url, processed_headers)
                                self.tools.append(langchain_tool)
                                if self.debug:
                                    print(f"[MCP]   - {mcp_tool.name}: {mcp_tool.description[:80] if mcp_tool.description else 'No description'}...")
                except Exception as session_error:
                    # Suppress harmless "Session termination failed: 202" errors
                    if "Session termination failed" not in str(session_error) and "202" not in str(session_error):
                        raise
            
            if self.debug:
                print(f"✓ Initialized {len(self.tools)} MCP tools from {len(mcp_servers)} servers")
                    
        except Exception as e:
            print(f"Warning: Could not initialize MCP servers: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
    
    async def _initialize_tools(self):
        """Initialize tools from Arcade MCP gateway (backward compatibility)."""
        try:
            arcade_key = os.getenv('ARCADE_API_KEY')
            user_id = os.getenv('ARCADE_USER_ID')
            
            if not arcade_key or not user_id:
                return
            
            # Connect to Arcade MCP gateway
            headers = {
                "Authorization": f"Bearer {arcade_key}",
                "Arcade-User-ID": user_id
            }
            
            if self.debug:
                print(f"[MCP] Connecting to Arcade MCP gateway: {ARCADE_MCP_GATEWAY}")
            
            # Create MCP client session
            try:
                async with streamablehttp_client(ARCADE_MCP_GATEWAY, headers=headers) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        
                        # List all available tools from the gateway
                        tools_response = await session.list_tools()
                        
                        if self.debug:
                            print(f"[MCP] Found {len(tools_response.tools)} tools from gateway")
                        
                        # Convert MCP tools to LangChain tools
                        self.tools = []
                        for mcp_tool in tools_response.tools:
                            langchain_tool = self._mcp_tool_to_langchain(mcp_tool, ARCADE_MCP_GATEWAY, headers)
                            self.tools.append(langchain_tool)
                        
                        if self.debug:
                            print(f"✓ Initialized {len(self.tools)} MCP tools")
            except Exception as session_error:
                # Suppress harmless "Session termination failed: 202" errors
                if "Session termination failed" not in str(session_error) and "202" not in str(session_error):
                    raise
                    
        except Exception as e:
            print(f"Warning: Could not initialize MCP tools: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
    
    def _mcp_tool_to_langchain(self, mcp_tool: types.Tool, gateway_url: str, headers: Dict[str, str]) -> StructuredTool:
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
                # Need to create a new session for each call
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
                                if "authorization_url" in result_text.lower() or "authorize" in result_text.lower():
                                    # Try to parse JSON for auth URL
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
                # Suppress harmless "Session termination failed: 202" errors during session cleanup
                error_msg = str(session_error)
                if "Session termination failed" in error_msg or "202" in error_msg:
                    pass  # Ignore and continue to return result
                else:
                    # Real error, re-raise
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
    
    def _create_agent(self, agent_id: str, config: Dict[str, Any]):
        """Create a LangChain agent from configuration."""
        # Create model
        model = ChatOpenAI(
            model=config.get('model', 'gpt-4o'),
            temperature=config.get('temperature', 0.7),
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        # Process instructions
        instructions = config.get('instructions', '')
        instructions = instructions.replace('{{date}}', datetime.now().strftime("%Y-%m-%d"))
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", instructions),
            ("placeholder", "{messages}"),
        ])
        
        # Get tools for this agent
        agent_tools = self._get_agent_tools(config.get('tools', []))
        
        # Create react agent
        if agent_tools:
            agent = create_react_agent(
                model=model.bind_tools(agent_tools),
                tools=agent_tools,
                prompt=prompt,
                name=agent_id
            )
        else:
            agent = create_react_agent(
                model=model,
                tools=[],
                prompt=prompt, 
                name=agent_id
            )
        
        return agent
    
    def _get_agent_tools(self, tool_configs: List[Union[str, Dict[str, Any]]]) -> List:
        """Get filtered tools for an agent based on configuration."""
        if not self.tools:
            return []
        
        # If no tool configuration specified, give agent ALL tools from MCP gateway
        if not tool_configs:
            return self.tools
        
        agent_tools = []
        
        for tool_spec in tool_configs:
            if isinstance(tool_spec, str):
                # Simple toolkit name (e.g., "Jira")
                toolkit_name = tool_spec.lower()
                matching_tools = [t for t in self.tools if toolkit_name in t.name.lower()]
                agent_tools.extend(matching_tools)
                
            elif isinstance(tool_spec, dict):
                # Specific tool configuration
                if 'toolkit' in tool_spec and 'tools' in tool_spec:
                    toolkit = tool_spec['toolkit'].lower()
                    specific_tools = tool_spec['tools']
                    
                    for tool_name in specific_tools:
                        # Find tools that match both toolkit and specific tool name
                        matching_tools = [
                            t for t in self.tools 
                            if toolkit in t.name.lower() and tool_name.lower() in t.name.lower()
                        ]
                        agent_tools.extend(matching_tools)
        
        return agent_tools
    
    def _identify_supervisors(self):
        """Identify which agents are supervisors by analyzing their instructions."""
        supervisors = set()
        
        for agent_id, agent_config in self.config.get('agents', {}).items():
            instructions = agent_config.get('instructions', '').lower()
            # Check if this agent routes to other agents
            if 'route' in instructions and any(other_id in instructions for other_id in self.agents if other_id != agent_id):
                supervisors.add(agent_id)
        
        return supervisors
    
    def _find_agent_supervisor(self, agent_id, supervisors):
        """Find which supervisor manages this agent."""
        for supervisor_id in supervisors:
            supervisor_config = self.config.get('agents', {}).get(supervisor_id, {})
            instructions = supervisor_config.get('instructions', '').lower()
            
            # Check if this supervisor mentions this agent in routing instructions
            if agent_id.lower() in instructions:
                return supervisor_id
        
        # Fallback to main supervisor
        return self.config.get('routing', {}).get('supervisor')

    def _create_department_subgraph(self, department_supervisor_id, department_agents):
        """Create a subgraph for a department with its supervisor and agents."""
        subworkflow = StateGraph(YAMLAgentState)
        
        # Add department supervisor and its agents
        subworkflow.add_node(department_supervisor_id, self.agents[department_supervisor_id])
        for agent_id in department_agents:
            subworkflow.add_node(agent_id, self.agents[agent_id])
        
        # Add tools node for this department
        if self.tools:
            subworkflow.add_node("tools", ToolNode(self.tools))
        
        # Start with department supervisor
        subworkflow.add_edge(START, department_supervisor_id)
        
        # Department supervisor routes to its agents
        def route_department(state: YAMLAgentState):
            messages = state.get("messages", [])
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, 'content'):
                    content = last_message.content.strip().upper()
                    
                    if "COMPLETE" in content:
                        return "END"
                    
                    # Check for specific agent names in this department
                    for agent_id in department_agents:
                        if agent_id.upper() in content:
                            return agent_id
            return "END"
        
        # Add routing from department supervisor
        route_options = {agent_id: agent_id for agent_id in department_agents}
        route_options["END"] = END
        
        subworkflow.add_conditional_edges(
            department_supervisor_id,
            route_department,
            route_options
        )
        
        # Department agents return to department supervisor or use tools
        for agent_id in department_agents:
            if self.tools:
                def should_continue(state: YAMLAgentState):
                    messages = state.get("messages", [])
                    if messages:
                        last_message = messages[-1]
                        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                            return "tools"
                    return department_supervisor_id
                
                subworkflow.add_conditional_edges(
                    agent_id,
                    should_continue,
                    {"tools": "tools", department_supervisor_id: department_supervisor_id}
                )
            else:
                subworkflow.add_edge(agent_id, department_supervisor_id)
        
        # Tools return to department supervisor
        if self.tools:
            subworkflow.add_edge("tools", department_supervisor_id)
        
        return subworkflow.compile()

    def _create_graph(self):
        """Create the LangGraph routing system supporting both flat and hierarchical structures."""
        # Get routing configuration
        routing = self.config.get('routing', {})
        supervisor_id = routing.get('supervisor')
        
        if not supervisor_id or supervisor_id not in self.agents:
            # Single agent mode - create simple graph
            if self.agents:
                agent_id = next(iter(self.agents))
                workflow = StateGraph(YAMLAgentState)
                workflow.add_node("agent", self.agents[agent_id])
                workflow.add_edge(START, "agent")
                workflow.add_edge("agent", END)
                self.graph = workflow.compile()
            return
        
        # Detect if hierarchical or flat
        supervisors = self._identify_supervisors()
        
        # If hierarchical (multiple supervisors), create true hierarchical teams
        if len(supervisors) > 1:
            department_supervisors = [s for s in supervisors if s != supervisor_id]
            
            workflow = StateGraph(YAMLAgentState)
            
            # Add main supervisor
            workflow.add_node(supervisor_id, self.agents[supervisor_id])
            
            # Create department subgraphs as independent LangGraph objects
            department_graphs = {}
            for dept_supervisor in department_supervisors:
                # Find agents managed by this department supervisor
                dept_agents = []
                supervisor_config = self.config.get('agents', {}).get(dept_supervisor, {})
                supervisor_instructions = supervisor_config.get('instructions', '').lower()
                
                for agent_id, agent_config in self.config.get('agents', {}).items():
                    if agent_id != dept_supervisor and agent_id not in supervisors:
                        if agent_id.lower() in supervisor_instructions:
                            dept_agents.append(agent_id)
                
                if dept_agents:  # Only create subgraph if department has agents
                    # Create isolated subgraph for this department
                    dept_subgraph = self._create_department_subgraph(dept_supervisor, dept_agents)
                    department_graphs[dept_supervisor] = dept_subgraph
                    
                    # Add the entire department as a single node
                    workflow.add_node(dept_supervisor, dept_subgraph)
                else:
                    # Fallback: add as regular agent if no managed agents found
                    workflow.add_node(dept_supervisor, self.agents[dept_supervisor])
            
            # Start with main supervisor
            workflow.add_edge(START, supervisor_id)
            
            # Main supervisor routes to departments
            def route_main_supervisor(state: YAMLAgentState):
                messages = state.get("messages", [])
                
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, 'content'):
                        content = last_message.content.strip().upper()
                        
                        if "COMPLETE" in content:
                            return "END"
                        
                        # Route to department supervisors based on content
                        for dept_supervisor in department_supervisors:
                            if dept_supervisor.upper() in content:
                                return dept_supervisor
                
                return "END"
            
            route_options = {dept_supervisor: dept_supervisor for dept_supervisor in department_supervisors}
            route_options["END"] = END
            
            workflow.add_conditional_edges(
                supervisor_id,
                route_main_supervisor,
                route_options
            )
            
            # Department subgraphs return to main supervisor when complete
            for dept_supervisor in department_supervisors:
                workflow.add_edge(dept_supervisor, supervisor_id)
            
        else:
            # Flat structure - original approach
            workflow = StateGraph(YAMLAgentState)
            
            # Add supervisor and all agents
            for agent_id, agent in self.agents.items():
                workflow.add_node(agent_id, agent)
            
            # Add tools node if we have tools
            if self.tools:
                workflow.add_node("tools", ToolNode(self.tools))
            
            # Start with supervisor
            workflow.add_edge(START, supervisor_id)
        
            # For flat structure, add original routing logic
            def route_supervisor(state: YAMLAgentState):
                """Route based on supervisor's last message content."""
                messages = state.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, 'content'):
                        content = last_message.content.strip().upper()
                        
                        # Check for COMPLETE first
                        if "COMPLETE" in content:
                            return "END"
                        
                        # Check for specific agent names
                        for agent_id in self.agents:
                            if agent_id != supervisor_id and agent_id.upper() in content:
                                return agent_id
                
                # Default to END if can't determine routing
                return "END"
            
            # Add conditional routing from supervisor
            route_options = {agent_id: agent_id for agent_id in self.agents if agent_id != supervisor_id}
            route_options["END"] = END
            
            workflow.add_conditional_edges(
                supervisor_id,
                route_supervisor,
                route_options
            )
            
            # Worker agents: check if they need tools or should return to supervisor
            def should_continue(state: YAMLAgentState):
                """Check if we should continue to tools or back to supervisor."""
                messages = state.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                        return "tools"
                return "supervisor"  # Return to supervisor for continued routing
            
            # Add conditional edges for all worker agents
            for agent_id in self.agents:
                if agent_id != supervisor_id:
                    if self.tools:
                        workflow.add_conditional_edges(
                            agent_id,
                            should_continue,
                            {"tools": "tools", "supervisor": supervisor_id}
                        )
                    else:
                        # No tools available, return directly to supervisor
                        workflow.add_edge(agent_id, supervisor_id)
            
            # Tools always return to supervisor for continued routing
            if self.tools:
                workflow.add_edge("tools", supervisor_id)
        
        self.graph = workflow.compile()
    
    def _trim_messages(self, messages: List, max_messages: int = 10):
        """Trim messages to prevent overwhelming the model."""
        if len(messages) <= max_messages:
            return messages
        
        # Keep the first message (original request) and last few messages
        return [messages[0]] + messages[-(max_messages-1):]
    
    async def process_request(self, user_input: str) -> List[str]:
        """Process a user request through the agent system."""
        if not self.graph:
            return ["❌ System not initialized properly"]
        
        responses = []
        self.conversation.append(f"User: {user_input}")
        
        # Create initial state with trimmed history
        initial_state = YAMLAgentState(
            messages=[HumanMessage(content=user_input)],
            conversation_history=self.conversation.copy(),
            completed_supervisors={}
        )
        
        try:
            # Get routing configuration for max iterations
            routing = self.config.get('routing', {})
            max_iterations = routing.get('max_iterations', 10)
            
            if self.debug:
                print(f"[GRAPH] Starting execution with max_iterations: {max_iterations}")
            
            # Execute the graph step by step for better debugging
            user_id = os.getenv('ARCADE_USER_ID', 'default')
            config = {
                "recursion_limit": max_iterations,
                "configurable": {
                    "user_id": user_id
                }
            }
            final_state = None
            
            iteration_count = 0
            async for event in self.graph.astream(initial_state, config):
                iteration_count += 1
                if self.debug:
                    print(f"\n[ITERATION {iteration_count}]")
                    # Show which node is executing
                    for node_name in event.keys():
                        if node_name not in ["__end__", "__interrupt__"]:
                            print(f"[EXECUTING NODE] {node_name}")
                    print(f"[GRAPH EVENT] {event}")
                final_state = event
                
                # Handle interrupts (authorization requests)
                if "__interrupt__" in event:
                    interrupt_data = event["__interrupt__"]
                    if hasattr(interrupt_data[0], 'value'):
                        interrupt_msg = interrupt_data[0].value
                        if self.debug:
                            print(f"[INTERRUPT] {interrupt_msg}")
                        
                        # Check if this is an authorization URL
                        if "http" in interrupt_msg:
                            self.auth_required = interrupt_msg
                            responses.append(f"🔒 AUTHORIZATION_REQUIRED: {interrupt_msg}")
                            break
                        else:
                            # Other type of interrupt
                            responses.append(f"⚠️ Tool execution interrupted: {interrupt_msg}")
                            break
                
                # Check if we got a complete response from a worker agent
                for node_name, node_state in event.items():
                    if node_name != "__end__" and node_name != "__interrupt__" and "messages" in node_state:
                        messages = node_state["messages"]
                        if messages:
                            # Check for authorization in ToolMessage errors
                            from langchain_core.messages import ToolMessage
                            for msg in messages:
                                if isinstance(msg, ToolMessage) and "🔒 AUTHORIZATION_REQUIRED:" in msg.content:
                                    # Extract the authorization URL
                                    import re
                                    auth_match = re.search(r'🔒 AUTHORIZATION_REQUIRED:\s*(https?://[^\s\'")\]]+)', msg.content)
                                    if auth_match:
                                        auth_url = auth_match.group(1)
                                        self.auth_required = auth_url
                                        responses.clear()  # Clear any previous responses
                                        responses.append(f"🔒 Authorization required. Please click here to authorize:\n{auth_url}")
                                        if self.debug:
                                            print(f"[AUTH] Found authorization URL: {auth_url}")
                                        return responses  # Return immediately with auth URL
                            
                            last_msg = messages[-1]
                            if isinstance(last_msg, AIMessage) and last_msg.content:
                                content = last_msg.content.strip()
                                
                                # In debug mode, always show supervisor routing decisions
                                if self.debug and ("supervisor" in node_name.lower()):
                                    print(f"[SUPERVISOR {node_name}] Routing decision: '{content}'")
                                
                                # Skip supervisor routing messages
                                routing_keywords = ["ticket", "knowledge", "escalation", "COMPLETE"]
                                if content.upper() not in routing_keywords and len(content) > 10:
                                    if self.debug:
                                        print(f"[RESPONSE] From {node_name}: {content[:100]}...")
                                    
                                    # Check for authorization required
                                    if "🔒 AUTHORIZATION_REQUIRED:" in content:
                                        self.auth_required = content.split("🔒 AUTHORIZATION_REQUIRED:")[1].strip()
                                        responses.append(content)
                                    elif content not in responses:
                                        responses.append(content)
                                        # Add successful responses to conversation
                                        self.conversation.append(f"Assistant: {content}")
            
            if self.debug:
                print(f"[GRAPH] Execution completed. Found {len(responses)} responses")
            
            return responses if responses else ["No response generated."]
            
        except Exception as e:
            if self.debug:
                print(f"[ERROR] Graph execution failed: {e}")
                import traceback
                traceback.print_exc()
            return [f"Error: {str(e)}"]


async def main():
    """Main entry point."""
    # Parse arguments
    config_file = "agents.yaml"
    request = None
    debug = False
    
    # Simple argument parsing
    args = sys.argv[1:]
    if '--debug' in args:
        debug = True
        args.remove('--debug')
    
    if args:
        if args[0].endswith(('.yaml', '.yml')):
            config_file = args[0]
            if len(args) > 1:
                request = " ".join(args[1:])
        else:
            request = " ".join(args)
    
    # Create system
    system = YAMLAgentSystem(config_file, debug=debug)
    
    try:
        await system.initialize()
    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_file}")
        print("\nCreate an agents.yaml file to define your agents.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to initialize: {str(e)}")
        sys.exit(1)
    
    # Process request or run interactive
    if request:
        # Single request mode
        print(f"\n💬 Processing: {request}\n")
        responses = await system.process_request(request)
        
        if responses:
            print("\n🤖 Response:")
            
            # Check if we have auth errors
            auth_messages = []
            other_messages = []
            
            for response in responses:
                if "🔒 AUTHORIZATION_REQUIRED:" in response:
                    auth_messages.append(response)
                else:
                    other_messages.append(response)
            
            # If we have auth messages, show only the first one cleanly
            if auth_messages:
                # Extract URL from AUTHORIZATION_REQUIRED message
                auth_msg = auth_messages[0]
                if "🔒 AUTHORIZATION_REQUIRED:" in auth_msg:
                    # Extract everything after the marker
                    url_part = auth_msg.split("🔒 AUTHORIZATION_REQUIRED:")[1].strip()
                    if url_part.startswith("http"):
                        print(f"\n🔒 Authorization required. Please click here to authorize:\n{url_part}")
                    else:
                        print(f"\n🔒 Authorization required: {url_part}")
                else:
                    print(f"\n{auth_msg}")
            else:
                # Show all other messages
                for response in other_messages:
                    print(f"\n{response}")
        else:
            print("\n❓ No response generated.")
    else:
        # Interactive mode
        print("\n🤖 Agent System (Interactive Mode)")
        print("=" * 50)
        print("Commands: 'exit' to quit, 'reset' to clear conversation")
        print("=" * 50)
        
        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if user_input.lower() == 'exit':
                    print("\n👋 Goodbye!")
                    break
                elif user_input.lower() == 'reset':
                    system.conversation = []
                    system.auth_required = None
                    print("✓ Conversation reset")
                    continue
                elif user_input.lower() == 'continue' and system.auth_required:
                    # Clear auth requirement and retry last request
                    system.auth_required = None
                    print("✓ Continuing after authorization...")
                    # Get the last user message from conversation
                    last_user_msg = None
                    for msg in reversed(system.conversation):
                        if msg.startswith("User:"):
                            last_user_msg = msg.split("User:", 1)[1].strip()
                            break
                    if last_user_msg:
                        print(f"Retrying: {last_user_msg}")
                        responses = await system.process_request(last_user_msg)
                        
                        if responses:
                            print("\n🤖 Assistant:")
                            
                            # Check if we have auth errors
                            auth_messages = []
                            other_messages = []
                            
                            for response in responses:
                                if "🔒 AUTHORIZATION_REQUIRED:" in response:
                                    auth_messages.append(response)
                                else:
                                    other_messages.append(response)
                            
                            # If we have auth messages, show only the first one cleanly
                            if auth_messages:
                                # Extract URL from AUTHORIZATION_REQUIRED message
                                auth_msg = auth_messages[0]
                                if "🔒 AUTHORIZATION_REQUIRED:" in auth_msg:
                                    # Extract everything after the marker
                                    url_part = auth_msg.split("🔒 AUTHORIZATION_REQUIRED:")[1].strip()
                                    if url_part.startswith("http"):
                                        print(f"\n🔒 Authorization required. Please click here to authorize:\n{url_part}")
                                        print("\nOnce authorized, type 'continue' to proceed.")
                                    else:
                                        print(f"\n🔒 Authorization required: {url_part}")
                                        print("\nPlease authorize and type 'continue' to proceed.")
                                else:
                                    print(f"\n{auth_msg}")
                            else:
                                # Show all other messages
                                for response in other_messages:
                                    print(f"\n{response}")
                        else:
                            print("\n❓ No response generated.")
                    continue
                elif not user_input:
                    continue
                
                print("\n⏳ Processing...")
                responses = await system.process_request(user_input)
                
                if responses:
                    print("\n🤖 Assistant:")
                    
                    # Check if we have auth errors
                    auth_messages = []
                    other_messages = []
                    
                    for response in responses:
                        if "🔒 AUTHORIZATION_REQUIRED:" in response:
                            auth_messages.append(response)
                        else:
                            other_messages.append(response)
                    
                    # If we have auth messages, show only the first one cleanly
                    if auth_messages:
                        # Extract URL from AUTHORIZATION_REQUIRED message
                        auth_msg = auth_messages[0]
                        if "🔒 AUTHORIZATION_REQUIRED:" in auth_msg:
                            # Extract everything after the marker
                            url_part = auth_msg.split("🔒 AUTHORIZATION_REQUIRED:")[1].strip()
                            if url_part.startswith("http"):
                                print(f"\n🔒 Authorization required. Please click here to authorize:\n{url_part}")
                                print("\nOnce authorized, type 'continue' to proceed.")
                            else:
                                print(f"\n🔒 Authorization required: {url_part}")
                                print("\nPlease authorize and type 'continue' to proceed.")
                        else:
                            print(f"\n{auth_msg}")
                    else:
                        # Show all other messages
                        for response in other_messages:
                            print(f"\n{response}")
                else:
                    print("\n❓ No response generated.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())