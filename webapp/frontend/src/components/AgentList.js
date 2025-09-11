import React from 'react';

const AgentList = ({ agents, onCreateAgent, onEditAgent, onDeleteAgent, onChatWithAgent }) => {
  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Agent Management</h2>
        <button
          onClick={onCreateAgent}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
        >
          <span>➕</span>
          <span>Create New Agent</span>
        </button>
      </div>

      {agents.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="text-gray-400 text-6xl mb-4">🤖</div>
          <h3 className="text-xl font-semibold text-gray-600 mb-2">No Agents Yet</h3>
          <p className="text-gray-500 mb-4">Create your first agent to get started</p>
          <button
            onClick={onCreateAgent}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg"
          >
            Create Agent
          </button>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <div
              key={agent.name}
              className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800">{agent.name}</h3>
                  <div className="flex items-center space-x-2 mt-1">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      agent.provider === 'openai' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-blue-100 text-blue-800'
                    }`}>
                      {agent.provider === 'openai' ? '🤖 OpenAI' : '⚡ LiteLLM'}
                    </span>
                    <span className="text-sm text-gray-500">{agent.model}</span>
                  </div>
                </div>
              </div>

              <div className="mb-4">
                <p className="text-sm text-gray-600 line-clamp-3">
                  {agent.instructions ? 
                    agent.instructions.slice(0, 100) + (agent.instructions.length > 100 ? '...' : '') :
                    'No instructions provided'
                  }
                </p>
              </div>

              {agent.tools && agent.tools.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-medium text-gray-500 mb-1">Tools:</p>
                  <div className="flex flex-wrap gap-1">
                    {agent.tools.slice(0, 3).map((tool, index) => (
                      <span
                        key={index}
                        className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-700"
                      >
                        {tool}
                      </span>
                    ))}
                    {agent.tools.length > 3 && (
                      <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-500">
                        +{agent.tools.length - 3} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              <div className="flex space-x-2">
                <button
                  onClick={() => onChatWithAgent(agent)}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded text-sm flex items-center justify-center space-x-1"
                >
                  <span>💬</span>
                  <span>Chat</span>
                </button>
                <button
                  onClick={() => onEditAgent(agent)}
                  className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded text-sm flex items-center justify-center space-x-1"
                >
                  <span>✏️</span>
                  <span>Edit</span>
                </button>
                <button
                  onClick={() => onDeleteAgent(agent.name)}
                  className="bg-red-100 hover:bg-red-200 text-red-700 px-3 py-2 rounded text-sm flex items-center justify-center"
                >
                  <span>🗑️</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AgentList;