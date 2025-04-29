import React, { useState, useEffect } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import ChatArea from './ChatArea';
import InputArea from './InputArea';
import { scrollToLatestMessage } from '../utils/scrollHelpers';

type AppProps = {
  // No props needed for the main App component
}

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

/**
 * Main App component that coordinates all other components
 */
const App: React.FC<AppProps> = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  
  // Use URL parameters to determine session if available
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    if (sessionId) {
      // If there's a session_id in the URL, load that specific session
      _loadSessionHistory(sessionId);
    } else {
      // Check if we're on a session-specific page
      const pathMatch = window.location.pathname.match(/\/session\/([^/]+)/);
      if (pathMatch && pathMatch[1]) {
        _loadSessionHistory(pathMatch[1]);
      } else {
        // Otherwise try to load the latest session or show empty state
        _loadLatestSession();
      }
    }
  }, []);
  
  /**
   * Loads chat history for the current session from the server
   */
  const _loadChatHistory = async (): Promise<void> => {
    try {
      const response = await fetch('/api/history');
      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }
      
      const data = await response.json();
      _processMessageData(data);
    } catch (error) {
      console.error('Error loading chat history:', error);
    }
  };
  
  /**
   * Loads chat history for a specific session
   */
  const _loadSessionHistory = async (sessionId: string): Promise<void> => {
    try {
      const response = await fetch(`/api/history/${sessionId}`);
      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }
      
      const data = await response.json();
      _processMessageData(data);
    } catch (error) {
      console.error(`Error loading history for session ${sessionId}:`, error);
    }
  };
  
  /**
   * Loads the latest session if one exists
   */
  const _loadLatestSession = async (): Promise<void> => {
    try {
      // First try to get the latest session
      const sessionResponse = await fetch('/api/latest_session');
      
      if (sessionResponse.ok) {
        const sessionData = await sessionResponse.json();
        if (sessionData && sessionData.session_id) {
          // We have a latest session, load its messages
          await _loadSessionHistory(sessionData.session_id);
          return;
        }
      }
      
      // If we get here, either there's no latest session or we couldn't load it
      // Just load the current session (which might be empty)
      await _loadChatHistory();
    } catch (error) {
      console.error('Error loading latest session:', error);
      // Fallback to current session
      await _loadChatHistory();
    }
  };
  
  /**
   * Process message data from the API and update state
   */
  const _processMessageData = (data: any[]): void => {
    if (Array.isArray(data) && data.length > 0) {
      // Sort messages by timestamp (chronological order) and ensure user messages come before assistant messages
      const sortedMessages = [...data].sort((a, b) => {
        const timeA = new Date(a.timestamp).getTime();
        const timeB = new Date(b.timestamp).getTime();
        // If timestamps are equal, sort by role (user first, then assistant)
        if (timeA === timeB) {
          return a.role === 'user' ? -1 : 1;
        }
        // Otherwise sort by timestamp (ascending)
        return timeA - timeB;
      });
      
      setMessages(sortedMessages);
      
      // Scroll to position the latest message at the top after render
      setTimeout(() => scrollToLatestMessage(), 100);
    }
  };
  
  /**
   * Sends a message to the server and updates the UI
   */
  const sendMessage = async (content: string): Promise<void> => {
    if (!content.trim()) return;
    
    // Create timestamp
    const timestamp = new Date().toISOString();
    
    // Get current URL path to extract session ID if on a session page
    const pathMatch = window.location.pathname.match(/\/session\/([^/]+)/);
    const sessionId = pathMatch && pathMatch[1] ? pathMatch[1] : null;
    
    // Create new message object
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp
    };
    
    // Add user message to state
    setMessages(prevMessages => {
      // Schedule a scroll after the DOM updates with the user message
      setTimeout(() => scrollToLatestMessage(), 0);
      return [...prevMessages, userMessage];
    });
    
    // Show loading state
    setIsLoading(true);
    
    try {
      // Include session ID in request if we're on a session-specific page
      const payload: any = { message: content };
      if (sessionId) {
        payload.session_id = sessionId;
      }
      
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Only add the assistant message if it has content
      if (data.response && data.response.trim()) {
        // Create assistant message with proper content
        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: data.response,
          timestamp: new Date().toISOString()
        };
        
        // Add assistant message to state
        setMessages(prevMessages => {
          const newMessages = [...prevMessages, assistantMessage];
          // Scroll after state update and render - use a longer timeout to ensure DOM has updated
          setTimeout(() => scrollToLatestMessage(), 50);
          return newMessages;
        });
      } else {
        console.warn('Received empty message from server');
      }
    } catch (error) {
      console.error('Error sending message:', error);
      
      // Add error message
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Sorry, there was an error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date().toISOString()
      };
      
      setMessages(prevMessages => [...prevMessages, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };
  
  /**
   * Toggles sidebar visibility
   */
  const toggleSidebar = (): void => {
    setSidebarOpen(!sidebarOpen);
    
    // Store in localStorage
    localStorage.setItem('sidebarCollapsed', (!sidebarOpen).toString());
  };
  
  return (
    <div className="flex flex-col h-screen bg-neo-bg text-neo-text relative overflow-hidden">
      <Header toggleSidebar={toggleSidebar} />
      
      <div className="flex flex-1 overflow-hidden">
        <Sidebar isOpen={sidebarOpen} />
        
        <main 
          className="flex-1 overflow-y-auto pb-[120px]" 
          id="main-scroll-container"
          data-sidebar-open={sidebarOpen}
        >
          <ChatArea 
            messages={messages} 
            isLoading={isLoading} 
          />
        </main>
      </div>
      
      <div className="fixed bottom-0 left-0 right-0 z-10">
        <InputArea onSendMessage={sendMessage} sidebarOpen={sidebarOpen} />
      </div>
    </div>
  );
};

export default App;
