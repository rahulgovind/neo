/**
 * Neo Web Chat Application JavaScript
 * 
 * Handles the client-side functionality of the chat interface including:
 * - Loading chat history
 * - Sending messages
 * - Rendering messages with Markdown support
 * - Handling command formatting
 */

// Initialize marked for Markdown rendering
marked.setOptions({
    highlight: function(code, lang) {
        const language = hljs.getLanguage(lang) ? lang : 'plaintext';
        return hljs.highlight(code, { language }).value;
    },
    langPrefix: 'hljs language-',
    breaks: true
});

// Command indicators
const COMMAND_START = '▶';
const SUCCESS_PREFIX = '✅';
const ERROR_PREFIX = '❌';
const COMMAND_END = '■';

/**
 * Loads chat history from the API
 */
function loadChatHistory() {
    // Show loading indicator
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = `
        <div class="flex items-center justify-center py-8">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-white mr-2"></div>
            <span class="text-gray-400">Loading chat history...</span>
        </div>
    `;
    
    // Fetch chat history
    console.log('Fetching chat history...');
    fetch('/api/history')
        .then(response => {
            console.log('History API response status:', response.status);
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Clear loading indicator
            chatMessages.innerHTML = '';
            
            console.log('History data received:', data);
            
            // Check if there's an error message from the server
            if (data.error) {
                throw new Error(data.error);
            }
            
            // If no messages, show welcome message
            if (!Array.isArray(data) || data.length === 0) {
                console.log('No messages in history, showing welcome screen');
                chatMessages.innerHTML = `
                    <div class="text-center py-12 order-first">
                        <h2 class="text-2xl font-semibold mb-4">Welcome to Neo Web Chat</h2>
                        <p class="text-gray-400">Type a message below to start chatting with Neo.</p>
                    </div>
                `;
                return;
            }
            
            // Render each message in reversed order (newest first)
            // Sort by timestamp with millisecond precision
            const sortedMessages = [...data].sort((a, b) => {
                return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
            });
            
            sortedMessages.forEach(message => {
                // Get content from either message.message (DB format) or message.content (possible expected format)
                const content = message.message || message.content || '';
                console.log('Message data:', message);
                renderMessage(message.role, content, message.timestamp);
            });
        })
        .catch(error => {
            console.error('Error loading chat history:', error);
            chatMessages.innerHTML = `
                <div class="text-center py-12 order-first">
                    <h2 class="text-2xl font-semibold text-neo-error mb-4">Error Loading Chat History</h2>
                    <p class="text-gray-400 mb-2">Error details: ${error.message}</p>
                    <p class="text-gray-400">Please try refreshing the page or check the console for more information.</p>
                </div>
            `;
        });
}

/**
 * Renders a message in the chat container
 * 
 * @param {string} role - 'user' or 'assistant'
 * @param {string} content - Message content
 * @param {string} timestamp - Timestamp of the message
 */
function renderMessage(role, content, timestamp) {
    const chatMessages = document.getElementById('chat-messages');
    const messageContainer = document.createElement('div');
    
    // Container for message with timestamp
    messageContainer.className = 'mb-6';
    
    // Message box with same background for both roles
    const messageElement = document.createElement('div');
    
    // Common classes for all messages - same background color for both roles
    let baseClasses = 'p-6 rounded-message w-full max-w-[85%] shadow-sm bg-neo-message text-neo-text';
    
    // Role-specific positioning
    if (role === 'user') {
        baseClasses += ' ml-auto';
    } else {
        baseClasses += ' mr-auto';
    }
    
    messageElement.className = baseClasses;
    
    // Format timestamp
    const formattedTime = new Date(timestamp).toLocaleTimeString();
    
    // Process content based on role
    if (role === 'user') {
        // For user messages, just display the text
        messageElement.innerHTML = `<div class="prose-sm prose-invert break-words">${escapeHtml(content)}</div>`;
    } else {
        // For assistant messages, process commands and render markdown
        const processedContent = processCommands(content);
        messageElement.innerHTML = `<div class="prose-sm prose-invert break-words">${processedContent}</div>`;
    }
    
    // Create timestamp element outside the message box
    const timestampElement = document.createElement('div');
    timestampElement.className = `text-xs text-gray-500 mt-1 ${role === 'user' ? 'text-right' : 'text-left'}`;
    timestampElement.textContent = formattedTime;
    
    // Add elements to container
    messageContainer.appendChild(messageElement);
    messageContainer.appendChild(timestampElement);
    
    // Add to the beginning to show newest messages at top (reversed order)
    chatMessages.prepend(messageContainer);
}

/**
 * Process commands in text and format them appropriately
 * 
 * @param {string} text - Text potentially containing commands
 * @returns {string} HTML formatted text with command styling
 */
function processCommands(text) {
    // First convert the markdown 
    let html = marked.parse(text);
    
    // Process command blocks
    // This regex looks for command blocks from ▶ to ■
    const commandRegex = new RegExp(`${COMMAND_START}([^${COMMAND_END}]+)${COMMAND_END}`, 'g');
    
    // Replace command blocks with styled divs
    html = html.replace(commandRegex, (match, commandText) => {
        return `<div class="font-mono text-sm bg-[rgba(30,30,30,0.6)] p-3 rounded-md my-2 overflow-x-auto whitespace-pre-wrap w-full">${COMMAND_START}${escapeHtml(commandText)}${COMMAND_END}</div>`;
    });
    
    // Process result blocks
    // Look for success results: ✅...■
    const successRegex = new RegExp(`${SUCCESS_PREFIX}([^${COMMAND_END}]+)${COMMAND_END}`, 'g');
    html = html.replace(successRegex, (match, resultText) => {
        return `<div class="font-mono text-sm bg-[rgba(16,185,129,0.1)] border-l-4 border-neo-success p-3 rounded-md my-2 overflow-x-auto whitespace-pre-wrap w-full">${SUCCESS_PREFIX}${escapeHtml(resultText)}${COMMAND_END}</div>`;
    });
    
    // Look for error results: ❌...■
    const errorRegex = new RegExp(`${ERROR_PREFIX}([^${COMMAND_END}]+)${COMMAND_END}`, 'g');
    html = html.replace(errorRegex, (match, resultText) => {
        return `<div class="font-mono text-sm bg-[rgba(239,68,68,0.1)] border-l-4 border-neo-error p-3 rounded-md my-2 overflow-x-auto whitespace-pre-wrap w-full">${ERROR_PREFIX}${escapeHtml(resultText)}${COMMAND_END}</div>`;
    });
    
    return html;
}

/**
 * Escape HTML characters to prevent XSS
 * 
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Send a message to the API and render the response
 * 
 * @param {string} message - User message to send
 */
function sendMessage(message) {
    // Get chat container
    const chatMessages = document.getElementById('chat-messages');
    
    // Get current time
    const timestamp = new Date().toISOString();
    
    // Clear welcome message if present
    const welcomeMessage = document.querySelector('.text-center.py-12');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
    
    // Render user message immediately
    renderMessage('user', message, timestamp);
    
    // Add typing indicator (Apple Messages style)
    const typingIndicator = document.createElement('div');
    typingIndicator.id = 'typing-indicator';
    typingIndicator.className = 'mb-6';
    typingIndicator.innerHTML = `
        <div class="p-6 rounded-message mr-auto bg-neo-message text-neo-text max-w-[85%] shadow-sm flex items-center">
            <div class="flex space-x-2">
                <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
            </div>
        </div>
    `;
    // Add to chat messages container at the beginning (top)
    chatMessages.prepend(typingIndicator);
    
    // Make sure typing indicator is visible
    typingIndicator.scrollIntoView({ behavior: 'smooth', block: 'start' });
    
    // Send to API
    fetch('/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message })
    })
    .then(response => response.json())
    .then(data => {
        // Remove typing indicator
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
        
        if (data.error) {
            // Handle error response
            const errorElement = document.createElement('div');
            errorElement.className = 'message message-system';
            errorElement.innerHTML = `
                <div class="message-content error">
                    <strong>Error:</strong> ${escapeHtml(data.error)}
                </div>
                <div class="message-time">${new Date().toLocaleTimeString()}</div>
            `;
            chatMessages.appendChild(errorElement);
        } else {
            // Render assistant response
            renderMessage('assistant', data.response, new Date().toISOString());
        }
        
        // Scroll to bottom
        scrollToBottom();
    })
    .catch(error => {
        // Remove typing indicator
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
        
        // Show error message
        const errorElement = document.createElement('div');
        errorElement.className = 'message message-system';
        errorElement.innerHTML = `
            <div class="message-content error">
                <strong>Error:</strong> Failed to communicate with the server.
            </div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;
        chatMessages.appendChild(errorElement);
        
        console.error('Error sending message:', error);
        
        // Scroll to bottom
        scrollToBottom();
    });
}

/**
 * No longer needed as we're using flex-col-reverse, which keeps the newest message visible
 * This is left as a placeholder for any future scrolling needs
 */
function scrollToBottom() {
    // With the reversed column layout, scrolling is automatic
    return;
}

// Event listeners
/**
 * Loads and displays sessions in the sidebar
 */
function loadSessions() {
    const sessionsList = document.getElementById('sessions-list');
    if (!sessionsList) return;
    
    // Show loading indicator
    sessionsList.innerHTML = '<div class="sidebar-loading">Loading sessions...</div>';
    
    // Fetch sessions
    fetch('/api/sessions')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Clear loading indicator
            sessionsList.innerHTML = '';
            
            // Check if there's an error message from the server
            if (data.error) {
                throw new Error(data.error);
            }
            
            // If no sessions, show message
            if (!Array.isArray(data) || data.length === 0) {
                sessionsList.innerHTML = '<div class="sidebar-loading">No sessions found</div>';
                return;
            }
            
            // Get current session ID from URL if available
            const urlParams = new URLSearchParams(window.location.search);
            const currentSessionId = urlParams.get('session_id');
            
            // Render each session
            data.forEach(session => {
                const sessionElement = document.createElement('div');
                // Safely handle session ID
                const sessionId = session.id || session.session_id || 'unknown'; 
                sessionElement.className = `session-item ${sessionId === currentSessionId ? 'active' : ''}`;
                sessionElement.dataset.sessionId = sessionId;
                
                // Format date
                const lastActive = new Date(session.last_active || session.created_at);
                const formattedDate = lastActive.toLocaleDateString();
                const formattedTime = lastActive.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                
                // Create shorter display ID safely
                const displayId = typeof sessionId === 'string' ? sessionId.substring(0, 8) : 'unknown';
                
                sessionElement.innerHTML = `
                    <div class="session-item-title">Session ${displayId}</div>
                    <div class="session-item-time">${formattedDate} ${formattedTime}</div>
                `;
                
                // Add click event to switch to this session
                sessionElement.addEventListener('click', function() {
                    window.location.href = `/switch_session/${sessionId}`;
                });
                
                sessionsList.appendChild(sessionElement);
            });
        })
        .catch(error => {
            console.error('Error loading sessions:', error);
            sessionsList.innerHTML = `<div class="p-4 text-center text-neo-error italic">Error: ${error.message}</div>`;
        });
}

/**
 * Toggle sidebar visibility
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const inputContainer = document.getElementById('input-container');
    const toggleBtn = document.getElementById('toggle-sidebar');
    
    if (sidebar) {
        sidebar.classList.toggle('-translate-x-full');
        
        // Update content margins
        const isCollapsed = sidebar.classList.contains('-translate-x-full');
        
        if (isCollapsed) {
            mainContent.dataset.sidebarOpen = 'false';
            inputContainer.classList.remove('ml-[280px]');
            toggleBtn.setAttribute('title', 'Show Sidebar');
        } else {
            mainContent.dataset.sidebarOpen = 'true';
            inputContainer.classList.add('ml-[280px]');
            toggleBtn.setAttribute('title', 'Hide Sidebar');
        }
        
        // Store sidebar state in localStorage
        localStorage.setItem('sidebarCollapsed', isCollapsed);
    }
}

/**
 * Initialize sidebar state based on localStorage
 */
function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const inputContainer = document.getElementById('input-container');
    const toggleBtn = document.getElementById('toggle-sidebar');
    
    if (sidebar && toggleBtn) {
        // Default to collapsed sidebar on first visit with our new design
        const savedState = localStorage.getItem('sidebarCollapsed');
        const isCollapsed = savedState !== null ? savedState === 'true' : true;
        
        if (isCollapsed) {
            sidebar.classList.add('-translate-x-full');
            mainContent.dataset.sidebarOpen = 'false';
            inputContainer.classList.remove('ml-[280px]');
            toggleBtn.setAttribute('title', 'Show Sidebar');
        } else {
            sidebar.classList.remove('-translate-x-full');
            mainContent.dataset.sidebarOpen = 'true';
            inputContainer.classList.add('ml-[280px]');
            toggleBtn.setAttribute('title', 'Hide Sidebar');
        }
        
        // Add click event for toggle button
        toggleBtn.addEventListener('click', toggleSidebar);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    
    // Initialize sidebar
    initSidebar();
    
    // Load sessions in sidebar
    loadSessions();
    
    
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const message = userInput.value.trim();
            if (message) {
                sendMessage(message);
                userInput.value = '';
            }
        });
    }
    
    if (userInput) {
        // Allow Enter to send message, but Shift+Enter for new line
        userInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const message = userInput.value.trim();
                if (message) {
                    sendMessage(message);
                    userInput.value = '';
                }
            }
        });
        
        // Auto-focus the input field when the page loads
        userInput.focus();
        
        // Auto-resize the textarea based on content
        userInput.addEventListener('input', function() {
            // Reset height to auto to get the right scrollHeight
            this.style.height = 'auto';
            // Set to scrollHeight to expand properly
            this.style.height = (this.scrollHeight) + 'px';
        });
    }
});
