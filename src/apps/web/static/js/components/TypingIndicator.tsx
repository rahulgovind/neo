import React from 'react';

type TypingIndicatorProps = {
  // No props needed for the typing indicator
}

/**
 * TypingIndicator component for showing typing animation
 */
const TypingIndicator: React.FC<TypingIndicatorProps> = () => {
  return (
    <div className="message-wrapper relative mb-3"> {/* Updated to match Message component spacing */}
      <div className="message-content mr-auto w-full"> {/* Added w-full to match assistant message width */}
        <div className="p-4 rounded-message bg-transparent text-neo-text border-none flex items-center">
          <div className="flex space-x-2">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TypingIndicator;
