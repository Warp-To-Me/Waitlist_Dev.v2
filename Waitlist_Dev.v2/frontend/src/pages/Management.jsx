import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import clsx from 'clsx';
import { Users, Shield, Radio, Activity, Settings, AlertTriangle } from 'lucide-react';

const Management = () => {
    const location = useLocation();

    const navItems = [
        { path: '/management', label: 'Dashboard', icon: Activity, end: true },
        { path: '/management/users', label: 'Users & Roles', icon: Users },
        { path: '/management/fleets', label: 'Fleet Control', icon: Radio },
        { path: '/management/bans', label: 'Bans & Audits', icon: AlertTriangle },
        { path: '/management/srp', label: 'SRP Config', icon: Shield },
        { path: '/management/sde', label: 'SDE Database', icon: Settings },
    ];

    return (
        <div className="flex h-full">
            {/* Sidebar */}
            <div className="w-64 bg-dark-900 border-r border-white/5 flex-shrink-0 flex flex-col">
                <div className="p-6">
                    <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Management Console</h2>
                    <nav className="space-y-1">
                        {navItems.map((item) => (
                            <NavLink
                                key={item.path}
                                to={item.path}
                                end={item.end}
                                className={({ isActive }) => clsx(
                                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition",
                                    isActive 
                                        ? "bg-brand-600/20 text-brand-400 border border-brand-500/20" 
                                        : "text-slate-400 hover:text-white hover:bg-white/5"
                                )}
                            >
                                <item.icon size={16} />
                                {item.label}
                            </NavLink>
                        ))}
                    </nav>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto bg-dark-950/50 p-8">
                <Outlet />
            </div>
        </div>
    );
};

export default Management;