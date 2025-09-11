import React, { useState, useEffect } from 'react';

const AgentForm = ({ agent, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    name: '',
    provider: 'openai',
    model: 'gpt-4o',
    temperature: 0.7,
    instructions: '',
    tools: [],
    base_url: ''
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Complete list of Arcade toolkits (alphabetically sorted)
  const availableTools = [
    'Airtable', 'Asana', 'Atlassian', 'Box', 'ClickUp', 'Confluence', 'Discord',
    'Dropbox', 'Figma', 'GitHub', 'GitLab', 'Gmail', 'GoogleCalendar', 'GoogleDocs',
    'GoogleDrive', 'GoogleMaps', 'GoogleSheets', 'HubSpot', 'Intercom', 'Jira',
    'Linear', 'Miro', 'Monday', 'Notion', 'OneDrive', 'OutlookCalendar', 'OutlookMail',
    'Pinterest', 'Salesforce', 'Sharepoint', 'Shopify', 'Slack', 'Spotify', 'Teams',
    'Todoist', 'Trello', 'Twitter', 'Typeform', 'Zoom'
  ].sort();

  // All available models from the user's team access list
  const allModels = [
    'gpt-4o', 'amazon-titan-embed-text-v2', 'google-text-embedding-005', 'qwen2.5-vl-32b-instruct',
    'qwen-max', 'o3-mini', 'deepseek-r1', 'qwen-turbo', 'qwen2-72b-instruct', 'gemini-1.5-pro-002',
    'amazon-nova-pro', 'claude-3-5-haiku-latest', 'cohere-embed-english-v3', 'gpt-4o-search-preview',
    'chatgpt-4o-latest', 'imagen-3.0-fast-generate-001', 'gemini-2.0-flash-001', 'qwen-vl-max',
    'qwen2-57b-a14b-instruct', 'text-embedding-3-small', 'claude-3-7-sonnet-latest', 'qwen-vl-plus',
    'imagen-3.0-generate-002', 'claude-3-5-sonnet-latest', 'cohere-rerank-v3-5', 'text-embedding-ada-002',
    'qwen2.5-vl-72b-instruct', 'cohere-embed-multilingual-v3', 'chatgpt-4o-mini', 'text-embedding-3-large',
    'qwen-plus', 'qwen2-7b-instruct', 'gpt-4o-mini-search-preview', 'amazon-titan-embed-image-v1',
    'google-text-multilingual-embedding-002', 'gemini-2.0-flash-lite-001', 'grok-2-image-latest',
    'grok-2-vision-1212', 'amazon-nova-canvas', 'pixtral-large', 'gpt-4.1-mini', 'gpt-4.1-nano',
    'gpt-4.1', 'llama-4-scout', 'llama-4-maverick', 'o3', 'o4-mini', 'qvq-max-latest', 'qwq-plus',
    'jamba-1-5-large', 'jamba-1-5-mini', 'google-multimodal-embedding', 'gpt-image-1', 'palmyra-x5',
    'llama-3.2-1b', 'grok-3', 'claude-4-sonnet', 'grok-3-fast', 'grok-3-mini', 'grok-3-mini-fast',
    'codex-mini-latest', 'sonar-pro', 'sonar', 'imagen-4.0-preview', 'imagen-4.0-ultra-exp',
    'gemini-2.0-flash-preview-image-generation', 'mistral-ocr', 'gemini-2.5-flash', 'gemini-2.5-pro',
    'gemini-2.5-flash-lite-preview', 'gpt-4o-mini-tts', 'gemini-live-2.5-flash-preview-native-audio',
    'tts-1', 'gemini-2.0-flash-live-preview', 'grok-4', 'o4-mini-deep-research', 'imagen-4.0-ultra-generate',
    'imagen-4.0-fast-generate', 'gpt-5', 'gpt-5-nano', 'gpt-5-mini', 'imagen-4.0-fast', 'grok-code-fast-1'
  ];

  // Available models for each provider (alphabetically sorted)
  const modelOptions = {
    openai: allModels.filter(model =>
      model.startsWith('gpt-') || model.startsWith('chatgpt-') || model.startsWith('o3') ||
      model.startsWith('o4') || model.startsWith('gpt-') || model.includes('embedding') ||
      model.startsWith('tts-') || model.startsWith('codex-')
    ).sort(),
    litellm: allModels.slice().sort()
  };

  useEffect(() => {
    if (agent) {
      setFormData({
        name: agent.name || '',
        provider: agent.provider || 'openai',
        model: agent.model || 'gpt-4o',
        temperature: agent.temperature || 0.7,
        instructions: agent.instructions || '',
        tools: agent.tools || [],
        base_url: agent.base_url || ''
      });
    }
  }, [agent]);

  const handleInputChange = (e) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) : value
    }));
    setError('');
  };

  const handleToolToggle = (tool) => {
    setFormData(prev => ({
      ...prev,
      tools: prev.tools.includes(tool)
        ? prev.tools.filter(t => t !== tool)
        : [...prev.tools, tool]
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    try {
      // Validation
      if (!formData.name.trim()) {
        throw new Error('Agent name is required');
      }

      if (!formData.instructions.trim()) {
        throw new Error('Instructions are required');
      }

      const url = agent 
        ? `/api/agents/${agent.name}`
        : '/api/agents';
      
      const method = agent ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save agent');
      }

      onSave();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-800">
            {agent ? 'Edit Agent' : 'Create New Agent'}
          </h2>
          <button
            onClick={onCancel}
            className="text-gray-500 hover:text-gray-700"
          >
            ✖️
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Agent Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Agent Name *
            </label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 placeholder-gray-500"
              placeholder="e.g., Gmail Assistant"
              required
            />
          </div>

          {/* Provider and Model */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Provider
              </label>
              <select
                name="provider"
                value={formData.provider}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
              >
                <option value="openai">OpenAI</option>
                <option value="litellm">LiteLLM</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Model
              </label>
              <select
                name="model"
                value={formData.model}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
              >
                {modelOptions[formData.provider].map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Temperature */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Temperature: {formData.temperature}
            </label>
            <input
              type="range"
              name="temperature"
              min="0"
              max="2"
              step="0.1"
              value={formData.temperature}
              onChange={handleInputChange}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0.0 (Deterministic)</span>
              <span>1.0 (Balanced)</span>
              <span>2.0 (Creative)</span>
            </div>
          </div>

          {/* Base URL (for LiteLLM) */}
          {formData.provider === 'litellm' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Base URL (Optional)
              </label>
              <input
                type="url"
                name="base_url"
                value={formData.base_url}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 placeholder-gray-500"
                placeholder="e.g., https://api.custom-llm.com/v1"
              />
              <p className="text-xs text-gray-500 mt-1">
                Leave empty to use default LiteLLM endpoints
              </p>
            </div>
          )}

          {/* Instructions */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Agent Purpose & Instructions *
            </label>
            <textarea
              name="instructions"
              value={formData.instructions}
              onChange={handleInputChange}
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 placeholder-gray-500"
              placeholder="Describe what this agent should do and how it should behave. For example:
- 'You are a customer support agent. Help users with their questions and provide friendly assistance.'
- 'You are a coding assistant. Help users write, debug, and explain code.'
- 'You are a research assistant. Help users find information and summarize findings.'"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              This defines your agent's role, personality, and behavior. Be specific about what the agent should and shouldn't do.
            </p>
          </div>

          {/* Tools */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Available Tools (Optional)
            </label>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              {availableTools.map(tool => (
                <label
                  key={tool}
                  className="flex items-center space-x-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={formData.tools.includes(tool)}
                    onChange={() => handleToolToggle(tool)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{tool}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Submit Buttons */}
          <div className="flex justify-end space-x-4 pt-6 border-t">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-md flex items-center space-x-2"
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <span>💾</span>
                  <span>{agent ? 'Update Agent' : 'Create Agent'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AgentForm;