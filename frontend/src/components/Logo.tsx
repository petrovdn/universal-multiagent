export function Logo() {
  return (
    <div className="logo-container">
      <svg 
        className="logo-icon" 
        viewBox="0 0 24 24" 
        fill="none" 
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="24" height="24" rx="4" fill="currentColor" className="logo-icon-bg"/>
        <path 
          d="M12 6C9.79 6 8 7.79 8 10C8 11.19 8.5 12.27 9.32 13L8 17H10L10.5 15H13.5L14 17H16L14.68 13C15.5 12.27 16 11.19 16 10C16 7.79 14.21 6 12 6ZM12 8C13.1 8 14 8.9 14 10C14 11.1 13.1 12 12 12C10.9 12 10 11.1 10 10C10 8.9 10.9 8 12 8Z" 
          fill="white"
        />
        <circle cx="10" cy="9.5" r="0.8" fill="currentColor" className="logo-icon-bg"/>
        <circle cx="14" cy="9.5" r="0.8" fill="currentColor" className="logo-icon-bg"/>
      </svg>
      <span className="logo-text">GPTzator 2.0</span>
    </div>
  )
}

