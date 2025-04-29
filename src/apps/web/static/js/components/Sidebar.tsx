import React, { useEffect, useState } from 'react';

type SidebarProps = {
  isOpen: boolean;
}

type Session = {
  session_id: string;
  created_at: string;
  updated_at: string;
  description: string | null;
}

/**
 * Sidebar component for chat session management
 */
const Sidebar: React.FC<SidebarProps> = ({ isOpen }) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    _loadSessions();
  }, []);
  
  /**
   * Loads chat sessions from the server
   */
  const _loadSessions = async (): Promise<void> => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/sessions');
      
      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }
      
      const data = await response.json();
      setSessions(data);
      setError(null);
    } catch (error) {
      console.error('Error loading sessions:', error);
      setError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Switches to a different chat session
   */
  const switchSession = (sessionId: string): void => {
    window.location.href = `/session/${sessionId}`;
  };
  
  /**
   * Creates a new chat session
   */
  const createNewSession = (): void => {
    window.location.href = '/new_session';
  };
  
  return (
    <aside 
      id="sidebar" 
      className={`fixed h-[calc(100vh-60px)] top-[60px] w-[280px] bg-neo-bg border-r border-neo-border transform transition-transform duration-300 ease-in-out overflow-y-auto ${isOpen ? '' : '-translate-x-full'}`}
    >
      <div className="p-4">
        <button 
          onClick={createNewSession}
          className="bg-neo-message w-full py-2 px-4 rounded-md hover:bg-white/10 transition-colors mb-4"
        >
          <i className="fas fa-plus mr-2"></i> New Chat
        </button>
      </div>
      
      <div className="p-4 border-t border-neo-border">
        <h2 className="text-sm uppercase text-gray-500 mb-2">Recent Sessions</h2>
        
        {isLoading ? (
          <div className="p-2 text-center text-sm text-gray-400">Loading sessions...</div>
        ) : error ? (
          <div className="p-4 text-center text-neo-error italic">Error: {error}</div>
        ) : sessions.length === 0 ? (
          <div className="p-2 text-center text-sm text-gray-400">No sessions found</div>
        ) : (
          <ul>
            {sessions.map(session => (
              <li 
                key={session.session_id}
                className="py-2 px-3 rounded-md mb-1 cursor-pointer hover:bg-white/10"
                onClick={() => switchSession(session.session_id)}
              >
                <div className="text-neo-text">{session.description || 'Untitled Session'}</div>
                <div className="text-xs text-gray-500">{new Date(session.updated_at).toLocaleString()}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
};

export default Sidebar;
