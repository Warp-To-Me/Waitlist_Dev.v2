import React, { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import clsx from 'clsx';
import { 
    Activity, Users, Shield, Radio, AlertTriangle, Settings, 
    BarChart2, Wallet, FileText, Database, Server, Key, Terminal, ClipboardList
} from 'lucide-react';
import { useSelector } from 'react-redux';
import { selectHasCapability } from '../store/slices/authSlice';

const Management = () => {
    // Permission Checks
    const hasAccessManagement = useSelector(selectHasCapability('access_management'));
    const hasFleetCommand = useSelector(selectHasCapability('access_fleet_command'));
    const hasViewSrp = useSelector(selectHasCapability('view_srp_dashboard'));
    const hasManageSrpSource = useSelector(selectHasCapability('manage_srp_source'));
    const hasInspectPilots = useSelector(selectHasCapability('inspect_pilots'));
    const hasManageBans = useSelector(selectHasCapability('manage_bans'));
    const hasViewBanAudit = useSelector(selectHasCapability('view_ban_audit_log'));
    const hasManageDoctrines = useSelector(selectHasCapability('manage_doctrines'));
    const hasManageSkills = useSelector(selectHasCapability('manage_skill_requirements'));
    const hasManageRules = useSelector(selectHasCapability('manage_analysis_rules'));
    const hasAccessAdmin = useSelector(selectHasCapability('access_admin'));

    // Section Visibility Helpers
    const showOperations = hasAccessManagement || hasFleetCommand;
    const showFinance = hasViewSrp || hasManageSrpSource;
    const showUserMgmt = hasInspectPilots || hasManageBans || hasViewBanAudit;
    const showSystem = hasManageDoctrines || hasManageSkills || hasManageRules || hasAccessAdmin;

    return (
        <div className="flex flex-col md:flex-row h-full w-full overflow-hidden bg-dark-950 relative">

            {/* Sidebar (Glassmorphic Update) */}
            <aside className="w-full md:w-64 bg-slate-900/60 backdrop-blur-xl border-r border-white/10 flex-shrink-0 overflow-y-auto z-20">
                <div className="p-6 border-b border-white/5">
                    <h2 className="label-text text-brand-500">Console</h2>
                    <p className="text-white font-bold text-lg tracking-tight">Fleet Command</p>
                </div>

                <nav className="p-4 space-y-6">
                    {/* OPERATIONS */}
                    {showOperations && (
                        <div>
                            <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Operations</span>
                            <div className="space-y-1">
                                {hasAccessManagement && (
                                    <NavLink to="/management" end className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <BarChart2 size={16} /> Overview
                                    </NavLink>
                                )}
                                {hasFleetCommand && (
                                    <NavLink to="/management/fleets" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <Radio size={16} /> Fleet Ops
                                    </NavLink>
                                )}
                            </div>
                        </div>
                    )}

                    {/* FINANCE */}
                    {showFinance && (
                        <div>
                            <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Finance</span>
                            <div className="space-y-1">
                                {hasViewSrp && (
                                    <NavLink to="/management/srp" end className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <Wallet size={16} /> SRP Dashboard
                                    </NavLink>
                                )}
                                {hasManageSrpSource && (
                                    <NavLink to="/management/srp/config" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <Settings size={16} /> SRP Config
                                    </NavLink>
                                )}
                            </div>
                        </div>
                    )}

                    {/* USER MGMT */}
                    {showUserMgmt && (
                        <div>
                            <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">User Mgmt</span>
                            <div className="space-y-1">
                                {hasInspectPilots && (
                                    <NavLink to="/management/users" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <Users size={16} /> User Database
                                    </NavLink>
                                )}
                                {hasManageBans && (
                                    <NavLink to="/management/bans" end className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <AlertTriangle size={16} /> Bans
                                    </NavLink>
                                )}
                                {hasViewBanAudit && (
                                    <NavLink to="/management/bans/audit" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <FileText size={16} /> Audit Log
                                    </NavLink>
                                )}
                                {hasManageBans && (
                                     <NavLink to="/management/command" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <ClipboardList size={16} /> Command Onboarding
                                    </NavLink>
                                )}
                            </div>
                        </div>
                    )}

                    {/* SYSTEM */}
                    {showSystem && (
                        <div>
                            <span className="px-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">System</span>
                            <div className="space-y-1">
                                {hasManageDoctrines && (
                                    <NavLink to="/management/doctrines" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <FileText size={16} /> Doctrines
                                    </NavLink>
                                )}
                                {hasManageSkills && (
                                    <NavLink to="/management/skills" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <Users size={16} /> Skill Reqs
                                    </NavLink>
                                )}
                                {hasManageRules && (
                                    <NavLink to="/management/rules" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                        <Shield size={16} /> Rule Helper
                                    </NavLink>
                                )}
                                {hasAccessAdmin && (
                                    <>
                                        <NavLink to="/management/sde" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                            <Database size={16} /> SDE Data
                                        </NavLink>
                                        <NavLink to="/management/celery" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                            <Server size={16} /> System Health
                                        </NavLink>
                                        <NavLink to="/management/permissions" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                            <Key size={16} /> Permissions
                                        </NavLink>
                                        <NavLink to="/management/scripts" className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-lg transition text-sm font-medium", isActive ? "bg-brand-500/10 text-brand-400 border border-brand-500/20" : "text-slate-400 hover:text-white hover:bg-white/5")}>
                                            <Terminal size={16} /> Script Runner
                                        </NavLink>
                                    </>
                                )}
                            </div>
                        </div>
                    )}
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
