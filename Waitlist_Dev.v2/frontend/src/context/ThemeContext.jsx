import { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};

export const ThemeProvider = ({ children }) => {
    // Initialize theme from local storage or default to 'default'
    const [theme, setTheme] = useState(() => {
        return localStorage.getItem('wtm-theme') || 'default';
    });

    useEffect(() => {
        // Apply the theme to the root HTML element
        document.documentElement.setAttribute('data-theme', theme);
        // Persist to local storage
        localStorage.setItem('wtm-theme', theme);
    }, [theme]);

    return (
        <ThemeContext.Provider value={{ theme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};