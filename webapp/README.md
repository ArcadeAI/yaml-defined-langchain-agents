# YAML-Defined LangChain Agents - Web Interface

A full-stack web application that provides an intuitive interface for managing and chatting with LangChain agents. This application bridges the gap between YAML-configured agents and user-friendly web interaction.

## 🌟 Features

- **Agent Management**: Create, edit, and delete agents through a web interface
- **Real-time Chat**: Interactive chat interface with your configured agents
- **Tool Call Visibility**: See exactly what tools agents are using with real-time JSON details
- **Multi-Provider Support**: Works with OpenAI and LiteLLM providers
- **Tool Integration**: Support for 39+ Arcade tools including Gmail, Jira, Slack, GitHub, and more
- **Configuration Management**: Web-based agent configuration instead of manual YAML editing
- **Conversation History**: Persistent chat history for each agent
- **Modern UI**: Clean, responsive interface built with React and Tailwind CSS

## 🏗️ Architecture

### Backend (FastAPI)
- REST API endpoints for agent CRUD operations
- Chat API integration with existing LangChain agent system
- WebSocket support for real-time communication
- Temporary YAML configuration generation for compatibility

### Frontend (React)
- Modern React application with component-based architecture
- Tailwind CSS for responsive styling
- Real-time chat interface
- Agent configuration forms

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ (pip will be installed automatically if needed)
- Node.js 16+ with npm
- API keys for your chosen LLM provider (OpenAI, etc.)

### 1. Backend Setup

```bash
# Navigate to backend directory
cd webapp/backend

# Install Python dependencies (the script will detect the right pip command)
pip install -r requirements.txt
# Alternative if pip is not available:
# python3 -m pip install -r requirements.txt

# Set up environment variables
cp ../../.env .env
# Edit .env file with your API keys

# Start the backend server
uvicorn app.main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`

### 2. Frontend Setup

```bash
# Navigate to frontend directory (in a new terminal)
cd webapp/frontend

# Install Node.js dependencies
npm install

# Start the development server
npm start
```

The frontend will be available at `http://localhost:3000`

## 📖 Usage Guide

### 1. Creating Your First Agent

1. Open the web application in your browser (`http://localhost:3000`)
2. Click on "➕ Create New Agent"
3. Fill in the agent configuration:
   - **Name**: Unique identifier for your agent
   - **Description**: Brief description of the agent's purpose
   - **Provider**: Choose between OpenAI or LiteLLM
   - **Model**: Select the LLM model (e.g., gpt-3.5-turbo, gpt-4)
   - **Temperature**: Set creativity level (0.0 = deterministic, 1.0 = creative)
   - **Tools**: Select available tools for the agent
4. Click "Create Agent"

### 2. Chatting with Agents

1. From the agent list, click "💬 Chat" next to any agent
2. Type your message in the chat input
3. Press Enter or click "Send" to start the conversation
4. The agent will respond using the configured model and tools
5. **Tool Call Visibility**: Watch in real-time as agents use tools:
   - 🔧 Purple messages show tool calls with JSON details
   - ✅ Green messages show tool responses
   - Expandable sections reveal complete tool arguments and responses

### Tool Call Transparency

The system provides complete visibility into agent tool usage:
- **Before Tool Execution**: See toolkit name, tool name, and JSON arguments
- **After Tool Execution**: View complete tool responses
- **Debug Information**: Detailed logging for troubleshooting
- **Real-time Updates**: Tool calls appear immediately as they happen

For troubleshooting tool calls, see [`TOOL_CALL_TROUBLESHOOTING.md`](./TOOL_CALL_TROUBLESHOOTING.md).

### 3. Managing Agents

- **Edit**: Click "✏️ Edit" to modify agent configuration
- **Delete**: Click "🗑️ Delete" to remove an agent
- **Chat**: Click "💬 Chat" to start a conversation

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the webapp directory with the following variables:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1  # Optional: for OpenAI-compatible APIs

# LiteLLM Configuration (if using alternative providers)
LITELLM_API_KEY=your_provider_api_key
LITELLM_BASE_URL=your_provider_base_url

# Arcade Tools Configuration
ARCADE_API_KEY=your_arcade_api_key
ARCADE_USER_ID=your_arcade_user_id

# Other provider keys as needed
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
```

### Available Tools (Arcade Integration)

The system supports 39+ Arcade tools that can be enabled for agents:

**Communication & Productivity:**
- **Gmail**: Email management (send, read, search, organize)
- **Slack**: Team communication and channel management
- **Discord**: Server and channel interactions
- **Jira**: Issue tracking and project management
- **Linear**: Modern issue tracking
- **Asana**: Task and project management
- **Notion**: Knowledge base and documentation
- **Confluence**: Team collaboration and documentation

**Development & Code:**
- **GitHub**: Repository management, issues, pull requests
- **GitLab**: Code hosting and CI/CD integration

**Cloud Storage:**
- **Google Drive**: File storage and document management
- **Dropbox**: File sync and sharing
- **OneDrive**: Microsoft cloud storage
- **Box**: Enterprise file sharing

**CRM & Sales:**
- **Salesforce**: Customer relationship management
- **HubSpot**: Marketing and sales automation
- **Zendesk**: Customer support and ticketing

**Social Media:**
- **Twitter**: Social media management
- **LinkedIn**: Professional networking
- **Facebook**: Social media automation
- **Instagram**: Content and engagement management
- **YouTube**: Video platform integration

**Google Services:**
- **Google Calendar**: Schedule and event management
- **Google Sheets**: Spreadsheet automation
- **Google Docs**: Document creation and editing

And many more! Each tool requires proper authentication and configuration.

## 🏃‍♂️ Development

### Backend Development

```bash
cd webapp/backend

# Run with auto-reload for development
uvicorn app.main:app --reload --port 8000

# Run tests (when available)
pytest

# Format code
black app/
isort app/
```

### Frontend Development

```bash
cd webapp/frontend

# Start development server
npm start

# Build for production
npm run build

# Run linting
npm run lint
```

## 📁 Project Structure

```
webapp/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application
│   │   └── __init__.py
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── public/
│   │   └── index.html       # HTML template
│   ├── src/
│   │   ├── components/
│   │   │   ├── AgentList.js    # Agent management
│   │   │   ├── AgentForm.js    # Agent configuration
│   │   │   └── ChatInterface.js # Chat interface
│   │   ├── App.js           # Main React component
│   │   ├── index.js         # React entry point
│   │   └── index.css        # Styles
│   └── package.json         # Node.js dependencies
└── README.md               # This file
```

## 🔧 API Documentation

Once the backend is running, visit `http://localhost:8000/docs` for interactive API documentation powered by Swagger/OpenAPI.

### Key Endpoints

- `GET /api/agents` - List all agents
- `POST /api/agents` - Create a new agent
- `GET /api/agents/{agent_name}` - Get agent details
- `PUT /api/agents/{agent_name}` - Update agent
- `DELETE /api/agents/{agent_name}` - Delete agent
- `POST /api/chat` - Send message to agent
- `GET /api/conversations/{agent_name}` - Get conversation history
- `DELETE /api/conversations/{agent_name}` - Clear conversation

## 🔍 Troubleshooting

### Common Issues

1. **Backend not starting**: Check that all dependencies are installed and API keys are set
2. **Frontend not connecting**: Ensure backend is running on port 8000
3. **Agent creation fails**: Verify API keys and model names are correct
4. **Chat not working**: Check browser console for errors and backend logs

### Debugging

- Backend logs: Check terminal where `uvicorn` is running
- Frontend logs: Check browser developer console (F12)
- API testing: Use the Swagger UI at `http://localhost:8000/docs`

## 🚢 Production Deployment

### Docker Setup (Optional)

Create a `Dockerfile` for the backend:

```dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run the frontend for production:

```bash
cd webapp/frontend
npm run build
# Serve the build/ directory with a web server
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the original repository for details.

## 🙏 Acknowledgments

- Built on top of LangChain and LangGraph
- Uses FastAPI for the backend API
- React and Tailwind CSS for the frontend
- LiteLLM for multi-provider LLM support