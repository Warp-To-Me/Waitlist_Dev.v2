import React, { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const BanEnforcer = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;

    // If user is not logged in, they can't be "banned" in the context of this system
    // (Bans are tied to authenticated accounts).
    if (!user) return;

    if (user.is_banned) {
      const path = location.pathname;
      // Define allowed paths.
      // strict match for /profile and /banned.
      // /doctrines might have sub-routes if we add them later, but currently it's just /doctrines.
      const allowedPaths = ['/profile', '/doctrines', '/banned'];

      // We might want to allow logout too!
      // Logout is usually handled by a link to /auth/logout/ which is backend,
      // or a frontend route.
      // The Layout has <a href="/auth/logout/"> which triggers a full page load to backend.
      // So that's fine.

      if (!allowedPaths.includes(path)) {
         // Prevent infinite loop if we are already trying to go there (though logic handles it)
         navigate('/banned', { replace: true });
      }
    } else {
      // If user is NOT banned, they shouldn't be on /banned
      if (location.pathname === '/banned') {
        navigate('/', { replace: true });
      }
    }
  }, [user, loading, location, navigate]);

  return children;
};

export default BanEnforcer;
