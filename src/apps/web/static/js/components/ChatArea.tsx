import React from 'react';
// Use relative imports within the same directory
import Message from './Message';
import TypingIndicator from './TypingIndicator';

/**
 * Format a date into a readable timestamp (e.g., "3:45 PM")
 */
const formatTimestamp = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

/**
 * Check if a timestamp should be shown (no prior message or > 15 minutes from previous)
 */
const shouldShowTimestamp = (currentTimestamp: string, previousTimestamp?: string): boolean => {
  if (!previousTimestamp) return true;
  
  const currentTime = new Date(currentTimestamp).getTime();
  const previousTime = new Date(previousTimestamp).getTime();
  
  // 15 minutes = 15 * 60 * 1000 milliseconds
  return currentTime - previousTime > 15 * 60 * 1000;
};

type ChatAreaProps = {
  messages: Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
  }>;
  isLoading: boolean;
}

/**
 * ChatArea component for displaying messages
 */
const ChatArea: React.FC<ChatAreaProps> = ({ messages, isLoading }) => {
  // For the welcome message check, ensure we're checking actual message content
  const hasMessages = messages.length > 0 && messages.some(msg => msg && msg.content && msg.content.trim() !== '');
  
  // Get messages in chronological order for display
  // We won't reverse the messages anymore since we want latest at the bottom
  const displayMessages = [...messages];
  
  return (
    <div 
      className="max-w-[840px] mx-auto w-full pt-[80px] pb-[80px] px-6" 
      id="chat-messages"
    >
      {/* Welcome message when no messages with content */}
      {!hasMessages ? (
        <div className="flex-grow flex items-center justify-center h-[60vh]">
          <div className="text-center">
            <p className="text-gray-400">Type a message below to start chatting with Neo.</p>
          </div>
        </div>
      ) : (
        // Display messages in chronological order with flex layout
        // The min-height ensures we have enough space for scrolling behavior
        <div className="flex flex-col min-h-[calc(100vh-280px)] mb-8 space-y-8">
          {/* Map through messages to display them with proper timestamps */}
          {displayMessages.map((message, index) => {
            // Get previous message index for timestamp logic
            const prevIndex = index - 1;
            
            // Get previous message
            const prevMessage = prevIndex >= 0 ? messages[prevIndex] : undefined;
            
            // Only show timestamps for user messages and only when needed
            const showTimestamp = message.role === 'user' && 
                               shouldShowTimestamp(message.timestamp, prevMessage?.timestamp);
            
            return (
              <React.Fragment key={message.id}>
                <div className="message-wrapper relative mb-1">
                  {showTimestamp && (
                    <div className="timestamp-container text-center mb-1 mt-3">
                      <span className="text-xs text-gray-500 bg-[rgba(0,0,0,0.05)] px-2 py-1 rounded-full">
                        {formatTimestamp(message.timestamp)}
                      </span>
                    </div>
                  )}
                  <Message
                    role={message.role}
                    content={message.content}
                    timestamp={message.timestamp}
                    showTimestamp={false} // We're handling timestamps at the ChatArea level now
                  />
                </div>
              </React.Fragment>
            );
          })}
          
          {/* Loading indicator - shown only after all messages */}
          {isLoading && <TypingIndicator />}
        </div>
      )}
    </div>
  );
};

export default ChatArea;
