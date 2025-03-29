import React, { useState, useRef, useEffect } from 'react';

type InputAreaProps = {
  onSendMessage: (message: string) => void;
  sidebarOpen: boolean;
}

/**
 * InputArea component for typing and sending messages
 */
const InputArea: React.FC<InputAreaProps> = ({ onSendMessage, sidebarOpen }) => {
  const [message, setMessage] = useState<string>('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Auto-focus the textarea on component mount
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);
  
  // Auto-resize the textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, [message]);
  
  /**
   * Handle form submission to send messages
   */
  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    
    if (message.trim()) {
      onSendMessage(message);
      setMessage('');
      
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };
  
  /**
   * Handle keydown events (Enter to send, Shift+Enter for new line)
   */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };
  
  return (
    <div className="input-area-container fixed bottom-0 left-0 right-0 z-10 py-4 bg-gradient-to-t from-neo-bg to-transparent" id="input-container">
      <div className="max-w-[900px] mx-auto w-full px-8">
        <form className="mx-auto" onSubmit={handleSubmit}>
          <div className={`transition-all duration-300 pb-2 ${sidebarOpen ? 'ml-[280px]' : ''}`}>
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Neo..."
              className="w-full p-4 resize-none text-neo-text bg-neo-message rounded-[28px] border border-neo-border focus:outline-none transition-colors shadow-md"
            />
          </div>
        </form>
      </div>
    </div>
  );
};

export default InputArea;
