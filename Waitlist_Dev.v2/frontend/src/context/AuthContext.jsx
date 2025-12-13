import { createContext, useContext, useState } from 'react';

const AuthContext = createContext();

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    // Initialize user from local storage if available
    const [user, setUser] = useState(() => {
        const savedUser = localStorage.getItem('wtm-user');
        return savedUser ? JSON.parse(savedUser) : null;
    });

    const login = () => {
        // Mock Login Data
        const mockUser = {
            username: "Space Pilot",
            isStaff: true,
            eve_character: {
                character_id: 2112625428, // CCP Fozzie (Example)
                character_name: "CCP Fozzie",
                portrait_url: "https://images.evetech.net/characters/2112625428/portrait?size=64"
            }
        };
        setUser(mockUser);
        localStorage.setItem('wtm-user', JSON.stringify(mockUser));
    };

    const logout = () => {
        setUser(null);
        localStorage.removeItem('wtm-user');
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};