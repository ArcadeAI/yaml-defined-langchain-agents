import React, { useState, useEffect } from 'react';
import AgentList from './components/AgentList';
import AgentForm from './components/AgentForm';
import ChatInterface from './components/ChatInterface';

function App() {
  const [currentView, setCurrentView] = useState('agents');
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [editingAgent, setEditingAgent] = useState(null);

  // Load agents on component mount
  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      const response = await fetch('/api/agents');
      const data = await response.json();
      setAgents(data.agents || []);
    } catch (error) {
      console.error('Failed to load agents:', error);
    }
  };

  const handleCreateAgent = () => {
    setEditingAgent(null);
    setCurrentView('form');
  };

  const handleEditAgent = (agent) => {
    setEditingAgent(agent);
    setCurrentView('form');
  };

  const handleDeleteAgent = async (agentName) => {
    if (window.confirm(`Are you sure you want to delete agent "${agentName}"?`)) {
      try {
        await fetch(`/api/agents/${agentName}`, { method: 'DELETE' });
        await loadAgents();
        if (selectedAgent?.name === agentName) {
          setSelectedAgent(null);
          setCurrentView('agents');
        }
      } catch (error) {
        console.error('Failed to delete agent:', error);
        alert('Failed to delete agent');
      }
    }
  };

  const handleAgentSaved = async () => {
    await loadAgents();
    setCurrentView('agents');
    setEditingAgent(null);
  };

  const handleChatWithAgent = (agent) => {
    setSelectedAgent(agent);
    setCurrentView('chat');
  };

  const renderNavigation = () => (
    <nav className="bg-blue-600 text-white p-4 shadow-lg">
      <div className="container mx-auto flex justify-between items-center">
        <h1 className="text-xl font-bold">🤖 Agent Management System</h1>
        <div className="space-x-4">
          <button
            onClick={() => setCurrentView('agents')}
            className={`px-4 py-2 rounded ${
              currentView === 'agents' ? 'bg-blue-800' : 'bg-blue-500 hover:bg-blue-700'
            }`}
          >
            Agents
          </button>
          {selectedAgent && (
            <button
              onClick={() => setCurrentView('chat')}
              className={`px-4 py-2 rounded ${
                currentView === 'chat' ? 'bg-blue-800' : 'bg-blue-500 hover:bg-blue-700'
              }`}
            >
              Chat ({selectedAgent.name})
            </button>
          )}
        </div>
      </div>
    </nav>
  );

  const renderContent = () => {
    switch (currentView) {
      case 'form':
        return (
          <AgentForm
            agent={editingAgent}
            onSave={handleAgentSaved}
            onCancel={() => setCurrentView('agents')}
          />
        );
      case 'chat':
        return selectedAgent ? (
          <ChatInterface agent={selectedAgent} />
        ) : (
          <div className="p-8 text-center">
            <p>No agent selected for chat</p>
          </div>
        );
      default:
        return (
          <AgentList
            agents={agents}
            onCreateAgent={handleCreateAgent}
            onEditAgent={handleEditAgent}
            onDeleteAgent={handleDeleteAgent}
            onChatWithAgent={handleChatWithAgent}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {renderNavigation()}
      <main className="container mx-auto py-8">
        {renderContent()}
      </main>
    </div>
  );
}

export default App;