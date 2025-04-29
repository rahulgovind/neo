import React from 'react';
import { processMarkdown } from '../utils/markdown';

type MessageProps = {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  showTimestamp?: boolean;
}

/**
 * Message component for displaying chat messages
 */
const Message: React.FC<MessageProps> = ({ role, content, timestamp, showTimestamp = false }) => {
  // Skip rendering if message has no content (this helps with empty assistant messages)
  if (!content || content.trim() === '') {
    return null;
  }
  
  // Convert UTC timestamp to local timezone and format for display (with null check)
  const formattedTime = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
  
  // Different styling for user vs assistant messages
  // User messages are limited in width, assistant messages can span the full chat panel
  const userMessageClasses = 'p-6 rounded-message w-full max-w-[85%] shadow-sm bg-neo-message text-neo-text';
  const assistantMessageClasses = 'p-6 rounded-message w-full bg-transparent text-neo-text border-none'; // Removed max-width
  
  // Role-specific positioning
  const positionClasses = role === 'user' ? 'ml-auto' : 'mr-auto';
  
  return (
    <div className="message-container mb-3"> {/* Reduced mb from 6 to 3 (50% reduction) */}
      <div className={`${role === 'user' ? userMessageClasses : assistantMessageClasses} ${positionClasses}`}>
        <div 
          className="prose-sm prose-invert break-words message-content"
          dangerouslySetInnerHTML={{ __html: processMarkdown(content) }}
        />
      </div>
      
      {/* Timestamp outside the message bubble (only shown if showTimestamp is true) */}
      {showTimestamp && (
        <div className={`text-xs text-gray-500 mt-1 ${role === 'user' ? 'text-right' : 'text-left'}`}>
          {formattedTime}
        </div>
      )}
    </div>
  );
};

export default Message;
