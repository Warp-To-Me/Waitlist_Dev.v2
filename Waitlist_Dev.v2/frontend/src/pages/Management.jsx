import React, { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import clsx from 'clsx';
import {
    Activity, Users, Shield, Radio, AlertTriangle, Settings,
    BarChart2, Wallet, FileText, Database, Server, Key
} from 'lucide-react';

const Management = () => {
    // In a real app we'd fetch user perms here to conditionally render links
    // For now we render all as per instructions to implement full functionality

    return (
        <div className="flex flex-col md:flex-row h-full w-full overflow-hidden bg-dark-950 relative">

            {/* Sidebar (Glassmorphic Update) */}
            <aside className="w-full md:w-64 bg-slate-900/60 backdrop-blur-xl border-r border-white/10 flex-shrink-0 overflow-y-auto z-20">
                <div className="p-6 border-b border-white/5">
                    <h2 className="label-text text-brand-500">Console</h2>
                    <p className="text-white font-bold text-lg tracking-tight">Fleet Command</p>
                </div>

                <nav className="p-4 space-y-6">
                    {/* GENERAL */}
                    <div>
                        <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Analysis</span>
                        <div className="space-y-1">
                            <NavLink to="/management" end className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <BarChart2 size={16} /> Overview
                            </NavLink>
                            <NavLink to="/management/users" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Users size={16} /> User Database
                            </NavLink>
                            <NavLink to="/management/roles" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Shield size={16} /> Roles
                            </NavLink>
                        </div>
                    </div>

                    {/* OPERATIONS */}
                    <div>
                        <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Operations</span>
                        <div className="space-y-1">
                            <NavLink to="/management/fleets" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Radio size={16} /> Fleet Ops
                            </NavLink>
                        </div>
                    </div>

                    {/* FINANCE */}
                    <div>
                        <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Finance</span>
                        <div className="space-y-1">
                            <NavLink to="/management/srp" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Wallet size={16} /> SRP Dashboard
                            </NavLink>
                            <NavLink to="/management/srp/config" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Settings size={16} /> SRP Config
                            </NavLink>
                        </div>
                    </div>

                    {/* USER MGMT */}
                    <div>
                        <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">User Mgmt</span>
                        <div className="space-y-1">
                            <NavLink to="/management/bans" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <AlertTriangle size={16} /> Bans
                            </NavLink>
                            <NavLink to="/management/bans/audit" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <FileText size={16} /> Audit Log
                            </NavLink>
                        </div>
                    </div>

                    {/* SYSTEM */}
                    <div>
                        <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">System</span>
                        <div className="space-y-1">
                            <NavLink to="/management/doctrines" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <FileText size={16} /> Doctrines
                            </NavLink>
                            <NavLink to="/management/skills" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Users size={16} /> Skill Reqs
                            </NavLink>
                            <NavLink to="/management/rules" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Shield size={16} /> Rule Helper
                            </NavLink>
                            <NavLink to="/management/sde" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Database size={16} /> SDE Data
                            </NavLink>
                            <NavLink to="/management/celery" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Server size={16} /> System Health
                            </NavLink>
                            <NavLink to="/management/permissions" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                <Key size={16} /> Permissions
                            </NavLink>
                        </div>
                    </div>
                </nav>
            </aside>

            {/* Main Content Area */}
            <div className="flex-grow relative h-full bg-slate-900 z-10" id="management-content-wrapper">
                <div className="absolute inset-0 overflow-y-auto custom-scrollbar" id="management-scroll-area">
                    <div className="p-6 md:p-10 min-h-full max-w-7xl mx-auto">
                        <Outlet />
                    </div>
                </div>
            </div>

        </div>
    );
};

export default Management;