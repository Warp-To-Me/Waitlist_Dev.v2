import React, { createContext, useContext, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchUserMe, selectUser, selectAuthLoading } from '../store/slices/authSlice';

// We keep the Context to avoid breaking every import in the app,
// but now it just bridges Redux state.
const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const dispatch = useDispatch();
    const user = useSelector(selectUser);
    const loading = useSelector(selectAuthLoading);

    useEffect(() => {
        // Only fetch if we haven't already (or if status is idle)
        // For now, we just force fetch on mount like the original context did
        dispatch(fetchUserMe());
    }, [dispatch]);

    // Check for ban status - Side Effect logic
    useEffect(() => {
        if (user && user.is_banned) {
             // Optionally redirect here or let components handle it
             // window.location.href = '/banned'; 
        }
    }, [user]);

    const refreshUser = async () => {
        return dispatch(fetchUserMe()).unwrap();
    };

    return (
        <AuthContext.Provider value={{ user, loading, refreshUser }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);