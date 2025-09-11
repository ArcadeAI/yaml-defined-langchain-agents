#!/bin/bash

# YAML-Defined LangChain Agents - Web Interface Startup Script
# This script starts both the backend and frontend servers

echo "🚀 Starting YAML-Defined LangChain Agents Web Interface..."
echo "========================================================"

# Check if we're in the correct directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Please run this script from the webapp directory"
    echo "Expected directory structure:"
    echo "  webapp/"
    echo "  ├── backend/"
    echo "  ├── frontend/"
    echo "  └── start.sh"
    exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command_exists python3; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ and try again."
    exit 1
fi

if ! command_exists npm; then
    echo "❌ Node.js/npm is not installed. Please install Node.js 16+ and try again."
    exit 1
fi

# Check for pip (try multiple variants)
if ! command_exists pip && ! command_exists pip3 && ! python3 -m pip --version > /dev/null 2>&1; then
    echo "❌ pip is not available. Please install pip and try again."
    echo "💡 You can install pip with: python3 -m ensurepip --upgrade"
    exit 1
fi

echo "✅ Prerequisites check passed"

# Check for .env file
if [ ! -f ".env" ] && [ ! -f "backend/.env" ]; then
    echo "⚠️  Warning: No .env file found. Please create .env with your API keys."
    echo "Example .env content:"
    echo "OPENAI_API_KEY=your_openai_api_key_here"
    echo "OPENAI_BASE_URL=https://api.openai.com/v1"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install backend dependencies
echo ""
echo "📦 Installing backend dependencies..."
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python packages..."
# Try different pip commands
if command_exists pip; then
    pip install -r requirements.txt
elif command_exists pip3; then
    pip3 install -r requirements.txt
else
    python3 -m pip install -r requirements.txt
fi
if [ $? -ne 0 ]; then
    echo "❌ Failed to install backend dependencies"
    exit 1
fi

# Copy .env if it exists in webapp root directory
if [ ! -f ".env" ]; then
    if [ -f "../.env" ]; then
        echo "Copying .env file from webapp root directory..."
        cp ../.env .env
    fi
fi

cd ..

# Install frontend dependencies
echo ""
echo "📦 Installing frontend dependencies..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "Installing Node.js packages..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install frontend dependencies"
        exit 1
    fi
else
    echo "✅ Node modules already installed"
fi
cd ..

# Function to cleanup on script exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set up cleanup trap
trap cleanup SIGINT SIGTERM

# Start backend server
echo ""
echo "🔄 Starting backend server..."
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Check if backend is running
if ! curl -s http://localhost:8000/api/health > /dev/null; then
    echo "⚠️  Backend might not be running properly"
    echo "Check backend logs above for any errors"
else
    echo "✅ Backend server started successfully at http://localhost:8000"
fi

# Start frontend server
echo ""
echo "🔄 Starting frontend server..."
cd frontend
npm start &
FRONTEND_PID=$!
cd ..

echo ""
echo "🎉 Servers are starting up!"
echo "========================================"
echo "📍 Backend API: http://localhost:8000"
echo "📍 Frontend App: http://localhost:3000"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "💡 Tips:"
echo "   • The frontend will auto-open in your browser"
echo "   • Backend API documentation is available at /docs"
echo "   • Press Ctrl+C to stop both servers"
echo "   • Check the terminal for any error messages"
echo ""
echo "📋 What you can do now:"
echo "   1. Create your first agent using the web interface"
echo "   2. Configure API keys in the .env file if needed"
echo "   3. Start chatting with your agents!"
echo ""

# Wait for user to stop the servers
echo "🔄 Servers are running... Press Ctrl+C to stop"
wait