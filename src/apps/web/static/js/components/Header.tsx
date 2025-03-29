import React from 'react';

type HeaderProps = {
  toggleSidebar: () => void;
}

/**
 * Header component with navigation controls
 */
const Header: React.FC<HeaderProps> = ({ toggleSidebar }) => {
  return (
    <header className="fixed top-0 w-full h-[60px] bg-neo-bg z-20 border-b border-neo-border flex items-center px-4">
      <button 
        id="toggle-sidebar"
        className="text-neo-text mr-4 w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors"
        onClick={toggleSidebar}
        title="Toggle Sidebar"
      >
        <i className="fas fa-bars"></i>
      </button>
      
      <h1 className="text-xl font-semibold">Neo Web Chat</h1>
    </header>
  );
};

export default Header;
