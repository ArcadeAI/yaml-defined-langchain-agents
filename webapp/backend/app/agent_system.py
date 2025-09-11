#!/usr/bin/env python3
"""
Multi-agent system using LangChain and LangGraph.
Generic agent system that can work with any configuration.
"""

import os
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# LangChain/LangGraph imports
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent, ToolNode

# LiteLLM support
try:
    from langchain_community.chat_models import ChatLiteLLM
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False

# Optional Arcade import
try:
    from arcadepy import Arcade, PermissionDeniedError
    from langchain_arcade import ToolManager
    HAS_ARCADE = True
except ImportError:
    HAS_ARCADE = False
    print("⚠️  Arcade not installed. Tool functionality will be disabled.")
    print("   Install with: pip install arcadepy langchain-arcade")


class AgentState(MessagesState):
    """State for the multi-agent system."""
    current_agent: Optional[str] = None
    auth_required: Optional[str] = None
    conversation_history: List[str] = []
    completed_supervisors: Dict[str, str] = {}


class AgentSystem:
    """Multi-agent system using LangChain and LangGraph."""
    
    def __init__(self, config: Dict[str, Any] = None, debug: bool = False):
        self.config = config or {}
        self.agents = {}
        self.arcade = None
        self.tools = []
        self.conversation = []
        self.debug = debug
        self.auth_required = None
        self.graph = None
        
    async def initialize(self):
        """Initialize agents from configuration."""
        
        # Initialize Arcade if we have tools
        if HAS_ARCADE and any(agent.get('tools') for agent in self.config.get('agents', {}).values()):
            arcade_key = os.getenv('ARCADE_API_KEY')
            if arcade_key:
                self.arcade = Arcade(api_key=arcade_key)
                # Initialize tools with proper user_id
                self._initialize_tools()
            else:
                print("⚠️  ARCADE_API_KEY not set. Tool functionality will be limited.")
        
        # Create agents
        for agent_id, agent_config in self.config.get('agents', {}).items():
            agent = self._create_agent(agent_id, agent_config)
            self.agents[agent_id] = agent
            
        # Create routing graph
        self._create_graph()
        
        if self.debug:
            print(f"✓ Initialized {len(self.agents)} agents")
    
    def _initialize_tools(self):
        """Initialize Arcade tools."""
        if not self.arcade:
            return
            
        try:
            # Get all unique toolkits mentioned in agent configs
            toolkits = set()
            for agent_config in self.config.get('agents', {}).values():
                for tool_spec in agent_config.get('tools', []):
                    if isinstance(tool_spec, str):
                        toolkits.add(tool_spec)
                    elif isinstance(tool_spec, dict) and 'toolkit' in tool_spec:
                        toolkits.add(tool_spec['toolkit'])
            
            if toolkits:
                # Initialize ToolManager with user_id from environment
                arcade_key = os.getenv('ARCADE_API_KEY')
                user_id = os.getenv('ARCADE_USER_ID', 'default')
                
                self.tool_manager = ToolManager(
                    api_key=arcade_key,
                    user_id=user_id
                )
                self.tool_manager.init_tools(toolkits=list(toolkits))
                self.tools = self.tool_manager.to_langchain(use_interrupts=True)
                
                if self.debug:
                    print(f"✓ Initialized {len(self.tools)} tools from {len(toolkits)} toolkits with user_id: {user_id}")
                    
        except Exception as e:
            print(f"Warning: Could not initialize tools: {e}")
    
    def _create_agent(self, agent_id: str, config: Dict[str, Any]):
        """Create a LangChain agent from configuration."""
        # Create model based on provider
        provider = config.get('provider', 'openai')
        model_name = config.get('model', 'gpt-4o')
        temperature = config.get('temperature', 0.7)
        base_url = config.get('base_url')
        
        if provider.lower() == 'litellm' and HAS_LITELLM:
            # Use LiteLLM for non-OpenAI providers
            model_kwargs = {
                'model': model_name,
                'temperature': temperature,
            }
            
            # Add base_url if specified
            if base_url:
                model_kwargs['base_url'] = base_url
            
            # Try to get API key from various sources
            api_key = (
                config.get('api_key') or 
                os.getenv('LITELLM_API_KEY') or 
                os.getenv('OPENAI_API_KEY')
            )
            
            if api_key:
                model_kwargs['api_key'] = api_key
            
            model = ChatLiteLLM(**model_kwargs)
        else:
            # Use OpenAI (default)
            model_kwargs = {
                'model': model_name,
                'temperature': temperature,
            }
            
            # Add API key if available
            api_key = config.get('api_key') or os.getenv('OPENAI_API_KEY')
            if api_key:
                model_kwargs['api_key'] = api_key
            
            # Add base_url if specified for OpenAI-compatible APIs
            if base_url:
                model_kwargs['base_url'] = base_url
            
            model = ChatOpenAI(**model_kwargs)
        
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
        if not self.tools or not tool_configs:
            return []
        
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
        subworkflow = StateGraph(AgentState)
        
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
        def route_department(state: AgentState):
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
                def should_continue(state: AgentState):
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
            # Single agent mode - create simple graph with tools support
            if self.agents:
                agent_id = next(iter(self.agents))
                workflow = StateGraph(AgentState)
                workflow.add_node("agent", self.agents[agent_id])
                
                # Add tools node if we have tools
                if self.tools:
                    workflow.add_node("tools", ToolNode(self.tools))
                
                workflow.add_edge(START, "agent")
                
                # Add tool routing for single agent
                if self.tools:
                    def should_continue_single(state: AgentState):
                        """Check if we should continue to tools or end for single agent."""
                        messages = state.get("messages", [])
                        if messages:
                            last_message = messages[-1]
                            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                                return "tools"
                        return "END"
                    
                    workflow.add_conditional_edges(
                        "agent",
                        should_continue_single,
                        {"tools": "tools", "END": END}
                    )
                    workflow.add_edge("tools", "agent")
                else:
                    workflow.add_edge("agent", END)
                
                self.graph = workflow.compile()
            return
        
        # Detect if hierarchical or flat
        supervisors = self._identify_supervisors()
        
        # If hierarchical (multiple supervisors), create true hierarchical teams
        if len(supervisors) > 1:
            department_supervisors = [s for s in supervisors if s != supervisor_id]
            
            workflow = StateGraph(AgentState)
            
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
            def route_main_supervisor(state: AgentState):
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
            workflow = StateGraph(AgentState)
            
            # Add supervisor and all agents
            for agent_id, agent in self.agents.items():
                workflow.add_node(agent_id, agent)
            
            # Add tools node if we have tools
            if self.tools:
                workflow.add_node("tools", ToolNode(self.tools))
            
            # Start with supervisor
            workflow.add_edge(START, supervisor_id)
        
            # For flat structure, add original routing logic
            def route_supervisor(state: AgentState):
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
            def should_continue(state: AgentState):
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
    
    async def process_request(self, user_input: str, callback=None) -> List[str]:
        """Process a user request through the agent system with optional callback for real-time updates."""
        if not self.graph:
            return ["❌ System not initialized properly"]
        
        responses = []
        tool_calls = []
        self.conversation.append(f"User: {user_input}")
        
        # Create initial state with trimmed history
        initial_state = AgentState(
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
            
            async for event in self.graph.astream(initial_state, config):
                if self.debug:
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
                
                # Check for tool calls and responses
                for node_name, node_state in event.items():
                    if node_name != "__end__" and node_name != "__interrupt__" and "messages" in node_state:
                        messages = node_state["messages"]
                        if messages:
                            last_msg = messages[-1]
                            
                            # Check for tool calls
                            if isinstance(last_msg, AIMessage) and hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                                if self.debug:
                                    print(f"[TOOL CALL DETECTED] Node: {node_name}, Tool calls: {len(last_msg.tool_calls)}")
                                for tool_call in last_msg.tool_calls:
                                    # Handle both formats: direct and function wrapper
                                    if 'function' in tool_call:
                                        # New format: {'function': {'name': '...', 'arguments': '...'}, 'id': '...'}
                                        tool_name = tool_call['function']['name']
                                        tool_args = tool_call['function'].get('arguments', '{}')
                                        # Parse JSON arguments if it's a string
                                        try:
                                            import json
                                            if isinstance(tool_args, str):
                                                tool_args = json.loads(tool_args)
                                        except:
                                            tool_args = {}
                                    else:
                                        # Old format: {'name': '...', 'args': {...}, 'id': '...'}
                                        tool_name = tool_call.get('name', '')
                                        tool_args = tool_call.get('args', {})
                                    
                                    tool_info = {
                                        "type": "tool_call",
                                        "node": node_name,
                                        "toolkit": self._extract_toolkit_name(tool_name),
                                        "tool_name": tool_name,
                                        "call_id": tool_call.get('id', ''),
                                        "args": tool_args,
                                        "timestamp": datetime.now().isoformat()
                                    }
                                    tool_calls.append(tool_info)
                                    if self.debug:
                                        print(f"[TOOL CALL] {tool_info}")
                                        print(f"[CALLBACK] Callback available: {callback is not None}")
                                    if callback:
                                        try:
                                            await callback({"type": "tool_call", "data": tool_info})
                                            if self.debug:
                                                print(f"[CALLBACK] Successfully called callback for tool call")
                                        except Exception as e:
                                            if self.debug:
                                                print(f"[CALLBACK ERROR] {e}")
                            
                            # Check for tool responses
                            elif node_name == "tools" and hasattr(last_msg, 'content'):
                                if self.debug:
                                    print(f"[TOOL RESPONSE DETECTED] Node: {node_name}, Content: {last_msg.content[:100]}...")
                                # Find matching tool call and add response
                                for tool_info in reversed(tool_calls):
                                    if not tool_info.get('response'):
                                        tool_info['response'] = last_msg.content
                                        tool_info['response_timestamp'] = datetime.now().isoformat()
                                        if self.debug:
                                            print(f"[TOOL RESPONSE] {tool_info}")
                                        if callback:
                                            try:
                                                await callback({"type": "tool_response", "data": tool_info})
                                                if self.debug:
                                                    print(f"[CALLBACK] Successfully called callback for tool response")
                                            except Exception as e:
                                                if self.debug:
                                                    print(f"[CALLBACK ERROR] Tool response: {e}")
                                        break
                            
                            # Check for regular AI responses
                            elif isinstance(last_msg, AIMessage) and last_msg.content:
                                content = last_msg.content.strip()
                                
                                # Skip supervisor routing messages
                                routing_keywords = ["ticket", "knowledge", "escalation", "COMPLETE"]
                                if content.upper() not in routing_keywords and len(content) > 10:
                                    if self.debug:
                                        print(f"[RESPONSE] From {node_name}: {content}")
                                    
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
    
    def _extract_toolkit_name(self, tool_name: str) -> str:
        """Extract toolkit name from tool name (e.g., 'jira_create_issue' -> 'Jira')."""
        if not tool_name:
            return "Unknown"
        
        # Common toolkit patterns
        toolkit_mapping = {
            'jira': 'Jira',
            'slack': 'Slack',
            'gmail': 'Gmail',
            'github': 'GitHub',
            'google': 'Google',
            'googlecalendar': 'Google Calendar',
            'googledrive': 'Google Drive',
            'googlesheets': 'Google Sheets',
            'googledocs': 'Google Docs',
            'notion': 'Notion',
            'salesforce': 'Salesforce',
            'hubspot': 'HubSpot',
            'trello': 'Trello',
            'asana': 'Asana',
            'confluence': 'Confluence',
            'zendesk': 'Zendesk',
            'linear': 'Linear',
            'discord': 'Discord',
            'twitter': 'Twitter',
            'facebook': 'Facebook',
            'linkedin': 'LinkedIn',
            'instagram': 'Instagram',
            'youtube': 'YouTube',
            'dropbox': 'Dropbox',
            'onedrive': 'OneDrive',
            'box': 'Box',
            'sharepoint': 'SharePoint'
        }
        
        tool_lower = tool_name.lower()
        for key, name in toolkit_mapping.items():
            if key in tool_lower:
                return name
        
        # Fallback: capitalize first part of tool name
        return tool_name.split('_')[0].capitalize()


def create_single_agent_system(agent_config: Dict[str, Any], debug: bool = False) -> AgentSystem:
    """Helper function to create a single-agent system from configuration."""
    config = {
        "agents": {
            "main_agent": agent_config
        }
    }
    return AgentSystem(config, debug)