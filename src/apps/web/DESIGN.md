# Neo Web Chat Application Design Guide

## 1. Core Design Principles

### 1.1 Design Philosophy
- **Minimalism**: Focus on essential elements only, remove visual clutter
- **Flat Design**: No 3D effects, shadows, or gradients; flat colors and simple elements
- **Focus on Content**: Design should emphasize the conversation, not the interface
- **Consistency**: Maintain visual consistency across all UI components
- **Tailwind CSS**: Utilize utility-first approach for styling efficiency and consistency

### 1.2 Color System
- **Primary Background**: `bg-neo-bg` - `rgb(33, 33, 33)` - Dark background for the application
- **Message Background**: `bg-neo-message` - `rgba(50, 50, 50, 0.85)` - Consistent for all message bubbles
- **Text**: `text-neo-text` - `#e5e7eb` - Light text for optimal contrast
- **Accents**: Grayscale variations only, no blue accents
- **Status Indicators**: `neo-error` for errors, `neo-success` for success states
- **Borders**: `border-neo-border` - `hsla(0, 0%, 100%, .05)` - Subtle borders for containers

### 1.3 Typography
- **Font Family**: System UI fonts prioritizing legibility
- **Markdown Support**: `prose-sm` and `prose-invert` utilities for formatted content
- **Message Text**: Clear, legible sizing with appropriate line height
- **Meta Text**: Smaller, lower-contrast text for timestamps and secondary information

### 1.4 Spacing & Layout
- **Maximum Width**: `max-w-[840px]` for main content areas
- **Message Width**: Messages limited to `max-w-[85%]` of container
- **Vertical Spacing**: `mb-6` between message groups
- **Content Flow**: Newest messages appear at the top (reversed order)

## 2. Component-Specific Guidelines

### 2.1 Header
- Fixed position at top of viewport: `fixed top-0 w-full`
- Minimal height with essential navigation elements only
- Contains sidebar toggle and application title/logo

### 2.2 Sidebar
- Hidden by default (collapsed state) using `-translate-x-full`
- Toggle button in header reveals/hides sidebar
- Fixed position: `fixed h-[calc(100vh-60px)]`
- Contains session management controls

### 2.3 Message Containers
- **User Messages**: Right-aligned (`ml-auto`)
- **Assistant Messages**: Left-aligned (`mr-auto`)
- **Background**: Same background color for both user and assistant messages
- **Shape**: Rounded corners (`rounded-message` - 1.5rem radius)
- **Timestamps**: Displayed outside the message bubble, below the message
- **Internal Ordering**: Uses millisecond precision for correct chronological sorting

### 2.4 Input Area
- **Position**: Floating input at bottom of viewport (`fixed bottom-4`)
- **Shape**: Rounded text area matching message bubble style
- **Width**: Matches message width (`max-w-[85%]`)
- **Placeholder**: Simple "Message Neo..." text
- **Focus State**: Subtle border highlight on focus
- **Behavior**: Enter sends message, Shift+Enter creates new line
- **Appearance**: No container box around the input area, just the input itself

### 2.5 Loading States
- **Typing Indicator**: Three animated dots with staggered animation
- Shown in a message-like container
- Uses `animate-bounce` with different delay values

### 2.6 Welcome Screen
- Centered welcome message when no chat history exists
- Contains application title and brief instructions
- Displays at the top of the reversed message container

## 3. Interaction Guidelines

### 3.1 Message Display
- Messages are displayed in reverse chronological order (newest first)
- User's latest message appears at the top of the page
- Long assistant messages ensure the end of the message is visible above the input box

### 3.2 Keyboard Navigation
- Enter key sends messages
- Shift+Enter creates a new line
- Input field auto-focuses on page load
- Input field auto-resizes based on content

### 3.3 Responsive Behavior
- Interface adapts to various screen sizes
- Sidebar collapses on smaller screens
- Message width maintains proportional constraints

## 4. Technical Implementation Notes

### 4.1 Tailwind CSS Usage
- Utility-first approach for all styling
- Custom theme extensions for Neo-specific colors and properties
- Minimal custom CSS, favoring Tailwind utility composition

### 4.2 JavaScript Components
- DOM manipulation for dynamic elements
- Simple, functional approach to UI interactions
- Local storage for persistent preferences (sidebar state)
