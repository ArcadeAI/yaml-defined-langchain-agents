# Troubleshooting Guide

## Common Issues and Solutions

### 1. Model Access Error (401)
**Error**: `team not allowed to access model. This team can only access models=['gpt-4o', ...]`

**Solution**: 
- Use only models that your team has access to
- The web interface now includes updated model lists with available models
- Recommended models for your team:
  - **OpenAI**: `gpt-4o`, `chatgpt-4o-latest`, `gpt-4o-mini`
  - **LiteLLM**: `claude-3-5-sonnet-latest`, `gemini-2.0-flash-001`, `qwen-max`

**Prevention**: 
- Always select models from the dropdown in the web interface
- The interface now only shows models accessible to your team

### 2. Input Text Not Visible (White Text)
**Issue**: Text typed in chat input box appears white/invisible

**Solution**: Fixed in the latest version
- Input text now has proper dark text color (`text-gray-900`)
- Placeholder text is properly styled (`placeholder-gray-500`)

### 3. pip Installation Issues on macOS
**Error**: `pip is not installed. Please install pip and try again.`

**Solution**: The startup script now automatically detects and uses:
- `pip` (if available)
- `pip3` (if available) 
- `python3 -m pip` (fallback)

**Manual fix**:
```bash
# If pip is missing, install it:
python3 -m ensurepip --upgrade
```

### 4. Backend Not Starting
**Symptoms**: 
- Backend fails to start
- Connection errors in frontend

**Solutions**:
1. **Check API Keys**: Ensure your `.env` file has valid API keys
2. **Check Python Version**: Requires Python 3.8+
3. **Virtual Environment**: Make sure virtual environment is activated
4. **Dependencies**: Run `pip install -r requirements.txt`

**Manual debugging**:
```bash
cd webapp/backend
source venv/bin/activate
python -c "import fastapi; print('FastAPI OK')"
uvicorn app.main:app --reload --port 8000
```

### 5. Frontend Not Starting
**Symptoms**:
- npm start fails
- Module not found errors

**Solutions**:
1. **Node Version**: Requires Node.js 16+
2. **Clean Install**: Delete `node_modules` and run `npm install`
3. **Check Dependencies**: Ensure `package.json` is present

**Manual debugging**:
```bash
cd webapp/frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

### 6. CORS Issues
**Error**: `Access to fetch at 'http://localhost:8000/api/...' blocked by CORS`

**Solution**: Already configured in backend
- Backend allows requests from `http://localhost:3000`
- If using different ports, update CORS settings in `webapp/backend/app/main.py`

### 7. Agent Creation Fails
**Error**: Various validation or server errors

**Troubleshooting**:
1. **Required Fields**: Ensure name and instructions are filled
2. **Model Selection**: Select a model from the dropdown
3. **Network**: Check backend is running on port 8000
4. **Logs**: Check browser console and backend terminal for errors

### 8. Chat Not Working
**Common Issues**:
1. **Agent Not Found**: Ensure agent was created successfully
2. **Model Access**: Use only accessible models (see issue #1)
3. **API Keys**: Check `.env` file has correct keys
4. **Backend Connection**: Verify backend health at `http://localhost:8000/api/health`

**Quick Test**:
```bash
# Test backend health
curl http://localhost:8000/api/health

# Test agent list
curl http://localhost:8000/api/agents
```

## Getting Help

### Debug Information to Collect

When reporting issues, please include:

1. **System Info**:
   - Operating System (macOS/Linux/Windows)
   - Python version: `python3 --version`
   - Node.js version: `node --version`

2. **Error Messages**:
   - Full error message from browser console (F12)
   - Backend terminal output
   - Frontend terminal output

3. **Configuration**:
   - Agent configuration (without API keys)
   - Model being used
   - Tools selected

### Useful Commands

```bash
# Check system requirements
python3 --version
node --version
npm --version

# Test API endpoints
curl http://localhost:8000/api/health
curl http://localhost:8000/api/agents

# Check backend logs
cd webapp/backend && source venv/bin/activate && uvicorn app.main:app --reload

# Check frontend
cd webapp/frontend && npm start

# Reset everything
cd webapp
./start.sh
```

### File Locations

- **Backend logs**: Terminal where `uvicorn` is running
- **Frontend logs**: Browser console (F12 → Console)
- **Configuration**: `webapp/backend/.env`
- **Agent storage**: In-memory (resets on restart)

## Known Limitations

1. **In-Memory Storage**: Agent configurations and conversations are lost on restart
2. **Single User**: No authentication or multi-user support
3. **Basic Error Handling**: Some edge cases may not be handled gracefully
4. **Model Limitations**: Restricted to team-accessible models only

## Performance Tips

1. **Use gpt-4o-mini** for faster responses and lower costs
2. **Lower temperature** (0.1-0.3) for more consistent responses
3. **Fewer tools** for faster agent initialization
4. **Clear conversations** regularly to reduce memory usage

## Future Improvements

- [ ] Persistent database storage
- [ ] Better error messages
- [ ] Model capability detection
- [ ] Conversation export/import
- [ ] Agent templates
- [ ] Performance monitoring