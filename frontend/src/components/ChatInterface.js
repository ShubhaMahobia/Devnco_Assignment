import React, { useState, useRef, useEffect } from 'react';
import { qaAPI } from '../services/api';

const ChatInterface = ({ selectedFile, onViewChange }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: g 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Clear messages when file changes
    if (selectedFile) {
      setMessages([{
        type: 'system',
        content: `Ready to answer questions about all documents in the database. You can ask about "${selectedFile.filename}" or any other document. Ask me anything!`,
        timestamp: new Date().toISOString()
      }]);
    } else {
      setMessages([{
        type: 'system',
        content: 'Select a document to start asking questions about all documents in the database.',
        timestamp: new Date().toISOString()
      }]);
    }
    setError(null);
  }, [selectedFile]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = {
      type: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toISOString()
    };

    // Add user message
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    try {
      // Get the file ID if a file is selected
      const fileId = selectedFile ? selectedFile.file_id : null;
      
      // Make API call
      const response = await qaAPI.askQuestion(userMessage.content, fileId);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Handle streaming response
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = {
        type: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        sources: [],
        citations: []
      };

      // Add empty assistant message that we'll update
      setMessages(prev => [...prev, assistantMessage]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.answer) {
                // Update the assistant message with the complete response
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage.type === 'assistant') {
                    lastMessage.content = data.answer;
                    lastMessage.sources = data.sources || [];
                    lastMessage.citations = data.citations || [];
                    lastMessage.retrieved_documents = data.retrieved_documents;
                    lastMessage.context_used = data.context_used;
                  }
                  return newMessages;
                });
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }

    } catch (error) {
      console.error('Chat error:', error);
      setError(error.message || 'Failed to get response. Please try again.');
      
      // Add error message
      setMessages(prev => [...prev, {
        type: 'error',
        content: 'Sorry, I encountered an error while processing your question. Please try again.',
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const clearChat = () => {
    if (selectedFile) {
      setMessages([{
        type: 'system',
        content: `Ready to answer questions about all documents in the database. You can ask about "${selectedFile.filename}" or any other document. Ask me anything!`,
        timestamp: new Date().toISOString()
      }]);
    } else {
      setMessages([{
        type: 'system',
        content: 'Select a document to start asking questions about all documents in the database.',
        timestamp: new Date().toISOString()
      }]);
    }
    setError(null);
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <div className="chat-title">
          <h3>💬 Ask Questions</h3>
          {selectedFile && (
            <p className="chat-subtitle">About: {selectedFile.filename}</p>
          )}
        </div>
        <div className="chat-header-actions">
          {onViewChange && (
            <button 
              className="view-switch-button" 
              onClick={() => onViewChange('pdf')}
              title="Switch to PDF view"
            >
              📄
            </button>
          )}
          <button 
            className="clear-chat-button" 
            onClick={clearChat}
            title="Clear conversation"
          >
            🗑️
          </button>
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.type}`}>
            <div className="message-content">
              {message.content}
              
              {message.sources && message.sources.length > 0 && (
                <div className="message-sources">
                  <strong>Sources:</strong>
                  <ul>
                    {message.sources.map((source, idx) => (
                      <li key={idx}>{source}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {message.retrieved_documents && (
                <div className="message-metadata">
                  Retrieved {message.retrieved_documents} relevant document(s)
                  {message.context_used && ` • ${message.context_used} words of context used`}
                </div>
              )}
            </div>
            <div className="message-time">
              {formatTime(message.timestamp)}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="message assistant loading">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <span className="loading-text">Thinking...</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="chat-error">
          <span className="error-icon">⚠️</span>
          {error}
          <button 
            className="error-close"
            onClick={() => setError(null)}
          >
            ×
          </button>
        </div>
      )}

      <div className="chat-input-container">
        <div className="chat-input">
          <textarea
            ref={inputRef}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              selectedFile 
                ? "Ask any question about all documents in the database..."
                : "Select a document first to ask questions..."
            }
            disabled={!selectedFile || isLoading}
            rows="1"
          />
          <button
            onClick={handleSendMessage}
            disabled={!selectedFile || !inputMessage.trim() || isLoading}
            className="send-button"
            title="Send message (Enter)"
          >
            {isLoading ? (
              <div className="spinner-small"></div>
            ) : (
              '📤'
            )}
          </button>
        </div>
        
        {selectedFile && (
          <div className="chat-help">
            💡 Ask any question among all the documents present in the database. Try: "What topics are covered?", "Compare information across documents", or ask specific questions about any content.
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatInterface;

