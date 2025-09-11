#!/usr/bin/env python3
"""
FastAPI Web Application for Multi-Agent System
Provides REST API and WebSocket endpoints for agent management and chat
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio
import uvicorn
import os
import sys
from datetime import datetime

# Import the local agent system
from .agent_system import AgentSystem, create_single_agent_system

app = FastAPI(title="Agent Management System", version="1.0.0")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class AgentConfig(BaseModel):
    name: str
    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.7
    instructions: str
    tools: List[str] = []
    base_url: Optional[str] = None

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = None

class ChatRequest(BaseModel):
    message: str
    agent_name: str

class AuthContinueRequest(BaseModel):
    agent_name: str

# In-memory storage (replace with database in production)
agents_store: Dict[str, Dict[str, Any]] = {}
conversations_store: Dict[str, List[ChatMessage]] = {}
auth_pending_requests: Dict[str, Dict[str, Any]] = {}  # Store requests pending auth
active_connections: List[WebSocket] = []

# No longer loading from agents.yaml - agents are created through web interface
print("🤖 Agent Management System initialized - ready for web-based agent creation")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove dead connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# API Routes
@app.get("/api/agents")
async def get_agents():
    """Get all configured agents"""
    return {"agents": list(agents_store.values())}

@app.post("/api/agents")
async def create_agent(agent: AgentConfig):
    """Create a new agent"""
    if agent.name in agents_store:
        raise HTTPException(status_code=400, detail="Agent already exists")
    
    agents_store[agent.name] = agent.dict()
    return {"message": f"Agent '{agent.name}' created successfully"}

@app.get("/api/agents/{agent_name}")
async def get_agent(agent_name: str):
    """Get specific agent configuration"""
    if agent_name not in agents_store:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agents_store[agent_name]

@app.put("/api/agents/{agent_name}")
async def update_agent(agent_name: str, agent: AgentConfig):
    """Update agent configuration"""
    if agent_name not in agents_store:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Update the agent name if it changed
    if agent.name != agent_name:
        agents_store[agent.name] = agent.dict()
        del agents_store[agent_name]
        # Update conversations key as well
        if agent_name in conversations_store:
            conversations_store[agent.name] = conversations_store.pop(agent_name)
    else:
        agents_store[agent_name] = agent.dict()
    
    return {"message": f"Agent updated successfully"}

@app.delete("/api/agents/{agent_name}")
async def delete_agent(agent_name: str):
    """Delete an agent"""
    if agent_name not in agents_store:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    del agents_store[agent_name]
    if agent_name in conversations_store:
        del conversations_store[agent_name]
    
    return {"message": f"Agent '{agent_name}' deleted successfully"}

@app.get("/api/conversations/{agent_name}")
async def get_conversation(agent_name: str):
    """Get conversation history for an agent"""
    if agent_name not in agents_store:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "agent_name": agent_name,
        "messages": conversations_store.get(agent_name, [])
    }

@app.delete("/api/conversations/{agent_name}")
async def clear_conversation(agent_name: str):
    """Clear conversation history for an agent"""
    if agent_name not in agents_store:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    conversations_store[agent_name] = []
    return {"message": f"Conversation cleared for agent '{agent_name}'"}

@app.post("/api/chat")
async def chat_with_agent(request: ChatRequest):
    """Send a message to an agent and get response"""
    if request.agent_name not in agents_store:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent_config = agents_store[request.agent_name]
    
    # Initialize conversation if it doesn't exist
    if request.agent_name not in conversations_store:
        conversations_store[request.agent_name] = []
    
    # Add user message to conversation
    user_message = ChatMessage(
        role="user",
        content=request.message,
        timestamp=datetime.now()
    )
    conversations_store[request.agent_name].append(user_message)
    
    # Store tool calls for this request
    tool_calls_data = []
    
    async def tool_callback(event_data):
        """Callback to capture tool calls and responses"""
        nonlocal tool_calls_data
        print(f"[DEBUG] Tool callback triggered with: {event_data}")
        
        # Extract the actual tool data from the event
        if isinstance(event_data, dict):
            if event_data.get("type") == "tool_call" and "data" in event_data:
                tool_data = event_data["data"]
                tool_data["type"] = "tool_call"  # Ensure type is set on the tool data itself
                tool_calls_data.append(tool_data)
                print(f"[DEBUG] Tool call added: {tool_data}")
            elif event_data.get("type") == "tool_response" and "data" in event_data:
                # Find matching tool call and update with response
                response_data = event_data["data"]
                for tool_call in tool_calls_data:
                    if (tool_call.get("call_id") == response_data.get("call_id") or
                        tool_call.get("tool_name") == response_data.get("tool_name")):
                        tool_call["response"] = response_data.get("response", "")
                        tool_call["response_timestamp"] = response_data.get("response_timestamp", "")
                        print(f"[DEBUG] Tool response added: {tool_call}")
                        break
        else:
            # Fallback: add the raw event data
            tool_calls_data.append(event_data)
            print(f"[DEBUG] Raw event data added: {event_data}")
    
    try:
        # Create temporary config for the agent system with generic system prompt
        generic_system_prompt = f"""You are a helpful AI assistant. {agent_config.get("instructions", "")}

Be helpful, accurate, and concise in your responses. If you're not sure about something, say so.
If you have access to tools, use them when appropriate to help the user.

Current date: {{{{date}}}}"""

        temp_config = {
            "agents": {
                request.agent_name: {
                    "provider": agent_config.get("provider", "openai"),
                    "model": agent_config.get("model", "gpt-4o"),
                    "temperature": agent_config.get("temperature", 0.7),
                    "instructions": generic_system_prompt,
                    "tools": agent_config.get("tools", []),
                    "base_url": agent_config.get("base_url")
                }
            }
        }
        
        # Initialize agent system with config (enable debug for tool call detection)
        system = AgentSystem(temp_config, debug=True)
        await system.initialize()
        
        # Process the request with callback for tool calls
        responses = await system.process_request(request.message, callback=tool_callback)
        
        # Debug: Print tool calls data before response
        print(f"[DEBUG] Tool calls data before response: {tool_calls_data}")
        
        # Get the first response (or error message)
        assistant_response = responses[0] if responses else "No response generated."
        
        # Check if response requires authorization
        if "🔒 AUTHORIZATION_REQUIRED:" in assistant_response:
            # Store the original request for continuation after auth
            auth_pending_requests[request.agent_name] = {
                "message": request.message,
                "timestamp": datetime.now(),
                "conversation": conversations_store[request.agent_name].copy()
            }
            return {
                "response": assistant_response,
                "conversation": conversations_store[request.agent_name],
                "tool_calls": tool_calls_data,
                "auth_required": True
            }
        
        # Add assistant response to conversation
        assistant_message = ChatMessage(
            role="assistant",
            content=assistant_response,
            timestamp=datetime.now()
        )
        conversations_store[request.agent_name].append(assistant_message)
        
        return {
            "response": assistant_response,
            "conversation": conversations_store[request.agent_name],
            "tool_calls": tool_calls_data
        }
        
    except Exception as e:
        error_message = f"Error: {str(e)}"
        assistant_message = ChatMessage(
            role="assistant",
            content=error_message,
            timestamp=datetime.now()
        )
        conversations_store[request.agent_name].append(assistant_message)
        
        return {
            "response": error_message,
            "conversation": conversations_store[request.agent_name],
            "tool_calls": tool_calls_data
        }

@app.post("/api/chat/continue")
async def continue_after_auth(request: AuthContinueRequest):
    """Continue processing after authentication"""
    if request.agent_name not in agents_store:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if request.agent_name not in auth_pending_requests:
        raise HTTPException(status_code=400, detail="No pending authentication request for this agent")
    
    # Get the stored request
    pending_req = auth_pending_requests[request.agent_name]
    original_message = pending_req["message"]
    
    # Clear the pending request
    del auth_pending_requests[request.agent_name]
    
    # Process the original request again (authentication should now work)
    chat_request = ChatRequest(
        message=original_message,
        agent_name=request.agent_name
    )
    
    return await chat_with_agent(chat_request)

# WebSocket endpoint for real-time chat
@app.websocket("/ws/chat/{agent_name}")
async def websocket_chat(websocket: WebSocket, agent_name: str):
    """WebSocket endpoint for real-time chat with an agent"""
    if agent_name not in agents_store:
        await websocket.close(code=4004, reason="Agent not found")
        return
    
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message:
                continue
            
            # Send user message back to confirm receipt
            await manager.send_personal_message(
                json.dumps({
                    "type": "user_message",
                    "content": user_message,
                    "timestamp": datetime.now().isoformat()
                }),
                websocket
            )
            
            # Process with agent (same logic as REST endpoint)
            agent_config = agents_store[agent_name]
            
            # Initialize conversation if it doesn't exist
            if agent_name not in conversations_store:
                conversations_store[agent_name] = []
            
            # Add user message to conversation
            user_msg = ChatMessage(
                role="user",
                content=user_message,
                timestamp=datetime.now()
            )
            conversations_store[agent_name].append(user_msg)
            
            try:
                # Send "typing" indicator
                await manager.send_personal_message(
                    json.dumps({
                        "type": "typing",
                        "content": f"{agent_name} is thinking..."
                    }),
                    websocket
                )
                
                # Process with agent system with generic system prompt
                generic_system_prompt = f"""You are a helpful AI assistant. {agent_config.get("instructions", "")}

Be helpful, accurate, and concise in your responses. If you're not sure about something, say so.
If you have access to tools, use them when appropriate to help the user.

Current date: {{{{date}}}}"""

                temp_config = {
                    "agents": {
                        agent_name: {
                            "provider": agent_config.get("provider", "openai"),
                            "model": agent_config.get("model", "gpt-4o"),
                            "temperature": agent_config.get("temperature", 0.7),
                            "instructions": generic_system_prompt,
                            "tools": agent_config.get("tools", []),
                            "base_url": agent_config.get("base_url")
                        }
                    }
                }
                
                # Callback for real-time tool call updates via WebSocket
                async def ws_tool_callback(event_data):
                    """Send tool call updates via WebSocket"""
                    await manager.send_personal_message(
                        json.dumps(event_data),
                        websocket
                    )
                
                system = AgentSystem(temp_config, debug=True)
                await system.initialize()
                responses = await system.process_request(user_message, callback=ws_tool_callback)
                assistant_response = responses[0] if responses else "No response generated."
                
                # Add assistant response to conversation
                assistant_msg = ChatMessage(
                    role="assistant",
                    content=assistant_response,
                    timestamp=datetime.now()
                )
                conversations_store[agent_name].append(assistant_msg)
                
                # Send assistant response
                await manager.send_personal_message(
                    json.dumps({
                        "type": "assistant_message",
                        "content": assistant_response,
                        "timestamp": datetime.now().isoformat()
                    }),
                    websocket
                )
                
            except Exception as e:
                error_message = f"Error: {str(e)}"
                await manager.send_personal_message(
                    json.dumps({
                        "type": "error",
                        "content": error_message,
                        "timestamp": datetime.now().isoformat()
                    }),
                    websocket
                )
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "agents_count": len(agents_store)}

# Serve React static files (in production)
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)