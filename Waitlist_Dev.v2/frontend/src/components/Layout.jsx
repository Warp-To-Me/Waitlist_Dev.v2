import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import { Menu, ChevronDown } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useSelector, useDispatch } from 'react-redux';
import { setTheme, selectTheme } from '../store/slices/uiSlice';
import { wsConnect, wsDisconnect } from '../store/middleware/socketMiddleware';
import { selectNotificationBuckets } from '../store/slices/notificationSlice';

const Layout = ({ children }) => {
  const theme = useSelector(selectTheme);
  const dispatch = useDispatch();
  const { user } = useAuth(); // Consume global user state

  useEffect(() => {
    // Check cookie for theme
    const match = document.cookie.match(new RegExp('(^| )site_theme=([^;]+)'));
    if (match) {
      dispatch(setTheme(match[2]));
    }
    
    // Cleanup existing theme classes
    document.body.classList.remove('theme-default', 'theme-caldari', 'theme-gallente', 'theme-amarr', 'theme-light');
    document.body.classList.add(`theme-${theme}`);
  }, [theme, dispatch]);

  const handleSetTheme = (newTheme) => {
    dispatch(setTheme(newTheme));
    const d = new Date();
    d.setTime(d.getTime() + (365 * 24 * 60 * 60 * 1000));
    document.cookie = `site_theme=${newTheme};expires=${d.toUTCString()};path=/`;
  };

  return (
    <div className={`flex flex-col h-full overflow-hidden text-slate-300`}>
       {/* Persistent Navbar */}
      <nav className="glass-header z-50 flex-shrink-0 relative">
        <div className="container mx-auto px-4 h-16 flex justify-between items-center">

            {/* Left: Brand */}
            <div className="flex items-center gap-8">
                <Link to="/" className="flex items-center gap-3 group">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-slate-900 font-bold text-xl shadow-lg shadow-brand-500/20 group-hover:scale-105 transition">W</div>
                    <span className="text-xl font-bold text-white tracking-tight group-hover:text-brand-400 transition">WarpToMe</span>
                </Link>

                {user && (user.is_staff || user.is_superuser) && (
                  <span className="badge badge-red hidden md:inline-block">System Admin</span>
                )}

                {/* Desktop Menu */}
                <div className="hidden md:flex items-center gap-1 border-l border-white/10 pl-6 h-8">
                    <Link to="/doctrines" className="px-3 py-1.5 rounded-md text-sm font-medium text-slate-400 hover:text-white hover:bg-white/5 transition">
                        Doctrines
                    </Link>
                </div>
            </div>

            {/* Right: User Controls */}
            <div className="flex items-center gap-3">
                {/* THEME SWITCHER */}
                <div className="relative group">
                    <button className="p-2 text-slate-400 hover:text-brand-400 transition rounded-full hover:bg-white/5 relative z-10 pb-4 mb-[-1rem]">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" /></svg>
                    </button>
                    {/* Dropdown Content */}
                    <div className="absolute right-0 pt-2 w-48 hidden group-hover:block z-50">
                        <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl overflow-hidden">
                            <div className="p-2 space-y-1">
                                <div className="px-3 py-1 text-[10px] uppercase font-bold text-slate-400 tracking-wider">Mode</div>
                                <button onClick={() => handleSetTheme('light')} className="flex items-center gap-3 w-full text-left px-3 py-2 rounded hover:bg-white/5 text-xs text-slate-300 hover:text-white transition">
                                    <span className="w-3 h-3 rounded-full bg-slate-200 border border-slate-400"></span> Light Mode
                                </button>

                                <div className="px-3 py-1 mt-2 text-[10px] uppercase font-bold text-slate-400 tracking-wider">Faction</div>
                                <button onClick={() => handleSetTheme('default')} className="flex items-center gap-3 w-full text-left px-3 py-2 rounded hover:bg-white/5 text-xs text-slate-300 hover:text-white transition">
                                    <span className="w-3 h-3 rounded-full bg-orange-700"></span> Minmatar (Rust)
                                </button>
                                <button onClick={() => handleSetTheme('caldari')} className="flex items-center gap-3 w-full text-left px-3 py-2 rounded hover:bg-white/5 text-xs text-slate-300 hover:text-white transition">
                                    <span className="w-3 h-3 rounded-full bg-blue-600"></span> Caldari (Steel)
                                </button>
                                <button onClick={() => handleSetTheme('gallente')} className="flex items-center gap-3 w-full text-left px-3 py-2 rounded hover:bg-white/5 text-xs text-slate-300 hover:text-white transition">
                                    <span className="w-3 h-3 rounded-full bg-emerald-600"></span> Gallente (Teal)
                                </button>
                                <button onClick={() => handleSetTheme('amarr')} className="flex items-center gap-3 w-full text-left px-3 py-2 rounded hover:bg-white/5 text-xs text-slate-300 hover:text-white transition">
                                    <span className="w-3 h-3 rounded-full bg-yellow-600"></span> Amarr (Gold)
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                {user ? (
                   <>
                    {user.navbar_char && (
                        <Link to="/profile" className="flex items-center gap-3 pl-1 pr-3 py-1 rounded-full border border-slate-700/50 bg-slate-800/50 hover:bg-slate-700 hover:border-brand-500/50 transition group">
                            <img src={`https://images.evetech.net/characters/${user.navbar_char.character_id}/portrait?size=64`} className="w-8 h-8 rounded-full border border-slate-600 group-hover:border-brand-400 transition" alt="Portrait" />
                            <div className="flex flex-col text-left">
                                <span className="text-xs font-bold text-white leading-none">{user.navbar_char.character_name}</span>
                                <span className={clsx("text-[10px] leading-none mt-0.5", user.navbar_char.is_main ? "text-brand-400" : "text-slate-500")}>
                                    {user.navbar_char.is_main ? 'MAIN' : 'ALT'}
                                </span>
                            </div>
                        </Link>
                    )}

                    <div className="flex items-center gap-2 pl-2 border-l border-white/10 ml-2">
                        {user.is_management && (
                            <Link to="/management" className="btn-ghost p-2" title="Management Console">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>
                            </Link>
                        )}
                        <a href="/auth/logout/" className="btn-ghost text-xs font-bold uppercase tracking-wider">Logout</a>
                    </div>
                   </>
                ) : (
                    <a href="/auth/login/" className="btn-primary py-1.5 text-sm">
                        <span>Log In</span>
                    </a>
                )}
            </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 relative overflow-hidden flex flex-col" id="main-content">
          {children}
      </main>

      {/* ESI Monitor */}
      <ESIMonitor user={user} />
    </div>
  );
};

const ESIMonitor = ({ user }) => {
    const dispatch = useDispatch();
    const buckets = useSelector(selectNotificationBuckets);

    useEffect(() => {
        if (!user) return;
        
        // Connect via Redux Middleware with specific key
        dispatch(wsConnect('/ws/user/notify/', 'user_notify'));

        return () => {
            dispatch(wsDisconnect('user_notify'));
        };
    }, [user, dispatch]);

    return (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 items-end pointer-events-none">
            {Object.values(buckets).map(bucket => (
                <RateLimitBar key={bucket.bucket} data={bucket} />
            ))}
        </div>
    );
}

const RateLimitBar = ({ data }) => {
    const percent = (data.remaining / data.limit) * 100;
    let colorClass = 'bg-green-500';
    if (percent < 50) colorClass = 'bg-yellow-500';
    if (percent < 20) colorClass = 'bg-red-500';

    return (
        <div className="bg-slate-900/90 backdrop-blur border border-white/10 p-2 rounded-lg shadow-xl w-48 pointer-events-auto animate-fade-in">
             <div className="flex justify-between items-end mb-1">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{data.bucket.toUpperCase()}</span>
                <span className="text-[10px] font-mono text-white font-bold ml-4">{data.remaining}</span>
            </div>
            <div className="w-full h-1.5 bg-dark-900 rounded-full overflow-hidden border border-white/10">
                <div className={`h-full ${colorClass} transition-all duration-500 ease-out shadow-[0_0_8px_rgba(255,255,255,0.2)]`} style={{ width: `${percent}%` }}></div>
            </div>
        </div>
    )
}

export default Layout;
