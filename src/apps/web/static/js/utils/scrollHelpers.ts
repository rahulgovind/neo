/**
 * Utilities for handling scroll behavior in the chat
 */

/**
 * Scrolls to the latest message in the chat area
 * Ensures that the latest user message is at the top of the viewport
 * Only the last message should be visible - previous messages won't be shown
 * Exception: If latest message is a very long assistant message, show its bottom above input
 */
export const scrollToLatestMessage = (): void => {
  // Use requestAnimationFrame to ensure scrolling happens after DOM updates
  requestAnimationFrame(() => {
    // Find the main scroll container
    const scrollContainer = document.getElementById('main-scroll-container');
    if (!scrollContainer) return;
    
    // Get all message elements
    const messageContainers = document.getElementsByClassName('message-wrapper');
    if (messageContainers.length === 0) return;
    
    // Get the latest message element
    const latestMessageContainer = messageContainers[messageContainers.length - 1];
    if (!latestMessageContainer) return;
    
    // Calculate scroll position to place the latest message at the top
    // Add offset for header height
    const headerOffset = 60;
    
    // Determine if the latest message is from assistant or user
    const isAssistantMessage = latestMessageContainer.querySelector('.message-content')?.parentElement?.classList.contains('mr-auto') || false;

    // Find the latest user message (for the special positioning requirement)
    let latestUserMessageContainer = null;
    for (let i = messageContainers.length - 1; i >= 0; i--) {
      const container = messageContainers[i];
      const isUser = !container.querySelector('.message-content')?.parentElement?.classList.contains('mr-auto');
      if (isUser) {
        latestUserMessageContainer = container;
        break;
      }
    }
    
    // We need to know the height of the viewport and input container
    const viewportHeight = window.innerHeight;
    const inputContainer = document.getElementById('input-container');
    const inputHeight = inputContainer ? inputContainer.getBoundingClientRect().height : 100;
    
    // Specific case handling - check if the conditions are met for the exception
    // The exception is: Latest is assistant message AND it's so long that user message at top would hide part of assistant message
    if (isAssistantMessage && latestUserMessageContainer) {
      // Get dimensions
      const assistantRect = latestMessageContainer.getBoundingClientRect();
      
      // Calculate if this assistant message would be partially hidden below the input
      // if we were to position the user message at the top
      const distanceBetweenMessages = (latestMessageContainer as HTMLElement).offsetTop - 
                                     (latestUserMessageContainer as HTMLElement).offsetTop;
      const userMessageAtTopHeight = distanceBetweenMessages + assistantRect.height;
      const availableHeight = viewportHeight - headerOffset - inputHeight - 40; // buffer
      
      if (userMessageAtTopHeight > availableHeight) {
        // EXCEPTION CASE - position to show the bottom of the assistant message
        // This is the only case where the latest user message isn't at the top
        console.log('Exception case: long assistant message would be hidden behind input');
        scrollContainer.scrollTop = (latestMessageContainer as HTMLElement).offsetTop + 
                                  assistantRect.height - 
                                  (viewportHeight - inputHeight - 40);
        return;
      }
    }
    
    // DEFAULT CASE - position latest user message at the top of the screen
    // (or fallback to the latest message if no user message exists)
    if (latestUserMessageContainer) {
      console.log('Default case: positioning latest user message at top');
      scrollContainer.scrollTop = (latestUserMessageContainer as HTMLElement).offsetTop - headerOffset;
    } else {
      // Fallback - no user messages found
      console.log('Fallback: no user messages found');
      scrollContainer.scrollTop = (latestMessageContainer as HTMLElement).offsetTop - headerOffset;
    }
  });
};
