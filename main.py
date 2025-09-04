#!/usr/bin/env python3
"""
YAML-driven agent system using LangChain and LangGraph.
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

# LangChain/LangGraph imports
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent, ToolNode

# Optional Arcade import
try:
    from arcadepy import Arcade, PermissionDeniedError
    from langchain_arcade import ToolManager
    HAS_ARCADE = True
except ImportError:
    HAS_ARCADE = False
    print("⚠️  Arcade not installed. Tool functionality will be disabled.")
    print("   Install with: pip install arcadepy langchain-arcade")


class YAMLAgentState(MessagesState):
    """State for the YAML-driven agent system."""
    current_agent: Optional[str] = None
    auth_required: Optional[str] = None
    conversation_history: List[str] = []
    completed_supervisors: Dict[str, str] = {}  # Track which supervisors have completed their work


class YAMLAgentSystem:
    """YAML-driven multi-agent system using LangChain and LangGraph."""
    
    def __init__(self, config_path: str = "agents.yaml", debug: bool = False):
        self.config_path = config_path
        self.config = {}
        self.agents = {}
        self.arcade = None
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
                
                # Check if we got a complete response from a worker agent
                for node_name, node_state in event.items():
                    if node_name != "__end__" and node_name != "__interrupt__" and "messages" in node_state:
                        messages = node_state["messages"]
                        if messages:
                            last_msg = messages[-1]
                            if isinstance(last_msg, AIMessage) and last_msg.content:
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