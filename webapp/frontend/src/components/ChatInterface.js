import React, { useState, useEffect, useRef } from 'react';

const ChatInterface = ({ agent }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [authRequired, setAuthRequired] = useState(false);
  const [authUrl, setAuthUrl] = useState('');
  const [toolCalls, setToolCalls] = useState([]);
  const messagesEndRef = useRef(null);

  // Load conversation history when component mounts or agent changes
  useEffect(() => {
    if (agent) {
      loadConversationHistory();
    }
  }, [agent]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadConversationHistory = async () => {
    try {
      const response = await fetch(`/api/conversations/${agent.name}`);
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages || []);
      }
    } catch (error) {
      console.error('Failed to load conversation history:', error);
    }
  };

  const clearConversation = async () => {
    if (window.confirm('Are you sure you want to clear this conversation?')) {
      try {
        await fetch(`/api/conversations/${agent.name}`, { method: 'DELETE' });
        setMessages([]);
        setError('');
        setToolCalls([]);
      } catch (error) {
        setError('Failed to clear conversation');
      }
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    // Add user message immediately
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError('');
    setAuthRequired(false);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputMessage,
          agent_name: agent.name
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to send message');
      }

      const data = await response.json();
      
      // Debug: Log the response data
      console.log('[DEBUG] API Response:', data);
      
      // Handle tool calls if present
      if (data.tool_calls && data.tool_calls.length > 0) {
        console.log('[DEBUG] Tool calls found:', data.tool_calls);
        setToolCalls(data.tool_calls);
        
        // Add tool call messages to chat
        data.tool_calls.forEach(toolCall => {
          console.log('[DEBUG] Processing tool call:', toolCall);
          if (toolCall.type === 'tool_call') {
            const toolCallMessage = {
              role: 'tool_call',
              content: `🔧 Using ${toolCall.data.toolkit} tool: ${toolCall.data.tool_name}`,
              toolData: toolCall.data,
              timestamp: new Date().toISOString(),
              isToolCall: true
            };
            setMessages(prev => [...prev, toolCallMessage]);
          }
          
          if (toolCall.data.response) {
            const toolResponseMessage = {
              role: 'tool_response',
              content: `✅ Tool response: ${toolCall.data.response}`,
              toolData: toolCall.data,
              timestamp: new Date().toISOString(),
              isToolResponse: true
            };
            setMessages(prev => [...prev, toolResponseMessage]);
          }
        });
      }
      
      // Check if authentication is required
      if (data.auth_required && data.response.includes('🔒 AUTHORIZATION_REQUIRED:')) {
        const authUrlPart = data.response.split('🔒 AUTHORIZATION_REQUIRED:')[1].trim();
        setAuthRequired(true);
        setAuthUrl(authUrlPart);
        
        // Add auth message to chat
        const authMessage = {
          role: 'assistant',
          content: `🔒 Authorization required. Please click the link below to authorize, then click "Continue" to proceed with your request.`,
          timestamp: new Date().toISOString(),
          isAuth: true
        };
        setMessages(prev => [...prev, authMessage]);
      } else {
        // Add assistant response
        const assistantMessage = {
          role: 'assistant',
          content: data.response,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, assistantMessage]);
      }

    } catch (err) {
      setError(err.message);
      // Add error message to chat
      const errorMessage = {
        role: 'assistant',
        content: `Error: ${err.message}`,
        timestamp: new Date().toISOString(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const continueAfterAuth = async () => {
    setIsLoading(true);
    setError('');

    try {
      const response = await fetch('/api/chat/continue', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          agent_name: agent.name
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to continue after authentication');
      }

      const data = await response.json();
      
      // Handle tool calls if present in continue response
      if (data.tool_calls && data.tool_calls.length > 0) {
        // Add tool call messages to chat
        data.tool_calls.forEach(toolCall => {
          if (toolCall.type === 'tool_call') {
            const toolCallMessage = {
              role: 'tool_call',
              content: `🔧 Using ${toolCall.data.toolkit} tool: ${toolCall.data.tool_name}`,
              toolData: toolCall.data,
              timestamp: new Date().toISOString(),
              isToolCall: true
            };
            setMessages(prev => [...prev, toolCallMessage]);
          }
          
          if (toolCall.data.response) {
            const toolResponseMessage = {
              role: 'tool_response',
              content: `✅ Tool response: ${toolCall.data.response}`,
              toolData: toolCall.data,
              timestamp: new Date().toISOString(),
              isToolResponse: true
            };
            setMessages(prev => [...prev, toolResponseMessage]);
          }
        });
      }
      
      // Add assistant response
      const assistantMessage = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);
      setAuthRequired(false);
      setAuthUrl('');

    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const renderToolCallDetails = (toolData) => {
    return (
      <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
        <div className="font-semibold text-gray-700">Tool Call Details:</div>
        <div className="mt-1 text-gray-600">
          <div><strong>Toolkit:</strong> {toolData.toolkit}</div>
          <div><strong>Tool:</strong> {toolData.tool_name}</div>
          {toolData.args && Object.keys(toolData.args).length > 0 && (
            <div>
              <strong>Arguments:</strong>
              <pre className="mt-1 text-xs bg-white p-1 rounded border overflow-x-auto">
                {JSON.stringify(toolData.args, null, 2)}
              </pre>
            </div>
          )}
          {toolData.response && (
            <div className="mt-2">
              <strong>Response:</strong>
              <div className="mt-1 p-1 bg-white rounded border text-xs">
                {toolData.response}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-md h-[600px] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <div>
            <h2 className="text-xl font-bold text-gray-800">
              💬 Chat with {agent.name}
            </h2>
            <div className="flex items-center space-x-2 mt-1">
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                agent.provider === 'openai'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-blue-100 text-blue-800'
              }`}>
                {agent.provider === 'openai' ? '🤖 OpenAI' : '⚡ LiteLLM'}
              </span>
              <span className="text-sm text-gray-500">{agent.model}</span>
            </div>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={clearConversation}
              className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded"
            >
              🗑️ Clear
            </button>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="mx-4 mt-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 mt-8">
              <div className="text-4xl mb-4">💬</div>
              <p>Start a conversation with {agent.name}</p>
              <p className="text-sm mt-2">
                This agent can help with: {agent.tools?.join(', ') || 'general assistance'}
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : message.isError
                      ? 'bg-red-100 text-red-800 border border-red-300'
                      : message.isAuth
                      ? 'bg-yellow-100 text-yellow-800 border border-yellow-300'
                      : message.isToolCall
                      ? 'bg-purple-100 text-purple-800 border border-purple-300'
                      : message.isToolResponse
                      ? 'bg-green-100 text-green-800 border border-green-300'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                  {message.toolData && renderToolCallDetails(message.toolData)}
                  {message.timestamp && (
                    <div className={`text-xs mt-1 ${
                      message.role === 'user' ? 'text-blue-200' : 'text-gray-500'
                    }`}>
                      {formatTimestamp(message.timestamp)}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-lg px-4 py-2 max-w-xs">
                <div className="flex items-center space-x-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                  </div>
                  <span className="text-sm text-gray-600">{agent.name} is thinking...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Authentication Section */}
        {authRequired && authUrl && (
          <div className="border-t p-4 bg-yellow-50">
            <div className="flex flex-col space-y-3">
              <div className="text-sm text-yellow-800">
                🔒 Authorization required to continue with your request
              </div>
              <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3">
                <a
                  href={authUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-center text-sm"
                >
                  🔗 Authorize Access
                </a>
                <button
                  onClick={continueAfterAuth}
                  disabled={isLoading}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white rounded-lg text-sm"
                >
                  ✅ Continue After Authorization
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t p-4">
          <div className="flex space-x-2">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={`Type your message to ${agent.name}...`}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none text-gray-900 placeholder-gray-500"
              rows={1}
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={!inputMessage.trim() || isLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg flex items-center space-x-2"
            >
              {isLoading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              ) : (
                <>
                  <span>📤</span>
                  <span>Send</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;