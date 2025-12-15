import React, { useEffect, useState, useRef } from 'react';
import { Search, ChevronLeft, ChevronRight, Plus, Minus, User } from 'lucide-react';

const ManagementRoles = () => {
    const [page, setPage] = useState(1);
    const [query, setQuery] = useState('');
    const [roleFilter, setRoleFilter] = useState('');
    const [users, setUsers] = useState([]);
    const [rolesList, setRolesList] = useState([]); // List of all possible roles for dropdown
    const [pagination, setPagination] = useState({ has_next: false, has_previous: false, num_pages: 1, current_page: 1 });
    const [selectedUser, setSelectedUser] = useState(null);
    const [userRoles, setUserRoles] = useState({ current_roles: [], available_roles: [] });

    // Initial Fetch for roles dropdown
    useEffect(() => {
        // Assuming there is an endpoint to get all roles for the filter
        // If not, we might need to hardcode or fetch differently.
        // The django template iterates `roles`, passed from context.
        // We will try to fetch from a new endpoint or existing one.
        // Let's assume the search endpoint returns them or we just use text search for now if complex.
        // But `api_search_users` takes `role` param.
        
        // Actually, let's just fetch the users first, maybe the response includes metadata or we can infer.
        // For now, hardcoded common roles or fetching if possible would be best.
        // Let's stick to just the user search part.
        fetchUsers();
    }, [page, query, roleFilter]);

    const fetchUsers = () => {
        const url = `/api/mgmt/search_users/?q=${encodeURIComponent(query)}&role=${encodeURIComponent(roleFilter)}&page=${page}`;
        fetch(url)
            .then(res => res.json())
            .then(data => {
                setUsers(data.results || []);
                setPagination(data.pagination || { has_next: false, has_previous: false, num_pages: 1, current_page: 1 });
                // If the API provided roles list, we'd set it here.
                if (data.all_roles) setRolesList(data.all_roles); 
            });
    };

    const fetchUserRoles = (userId) => {
        fetch(`/api/mgmt/user_roles/${userId}/`)
            .then(res => res.json())
            .then(data => setUserRoles(data));
    };

    const selectPilot = (user) => {
        setSelectedUser(user);
        fetchUserRoles(user.id);
    };

    const updateRole = (userId, role, action) => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch('/api/mgmt/update_role/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ user_id: userId, role, action })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                fetchUserRoles(userId);
            } else {
                alert(data.error);
            }
        });
    };

    return (
        <div className="flex flex-col gap-6 h-full">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-white/5 pb-6 shrink-0">
                <div>
                    <h1 className="heading-1">Role Management</h1>
                    <p className="text-slate-400 text-sm mt-1">Select a pilot from the directory or search to manage access rights.</p>
                </div>
            </div>

            {/* Search Area */}
            <div className="glass-panel p-6 shrink-0">
                <div className="flex flex-col md:flex-row gap-4 max-w-4xl">
                    <div className="relative flex-grow group">
                        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none group-focus-within:text-brand-500 transition">
                            <Search className="w-5 h-5 text-slate-500" />
                        </div>
                        <input 
                            type="text"
                            className="input-field pl-10"
                            placeholder="Search by Character Name..."
                            value={query}
                            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
                        />
                    </div>
                    
                    {/* Role Filter - Simplified if we don't have list, or we can hardcode common ones if known */}
                    {rolesList.length > 0 && (
                        <div className="md:w-64">
                            <select 
                                className="select-field h-full" 
                                value={roleFilter} 
                                onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
                            >
                                <option value="">All Roles</option>
                                {rolesList.map(r => <option key={r} value={r}>{r}</option>)}
                            </select>
                        </div>
                    )}
                </div>
            </div>

            {/* Content Split */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-grow items-stretch min-h-0">
                
                {/* Left: Search Results */}
                <div className="glass-panel flex flex-col overflow-hidden h-full">
                    <div className="p-4 bg-white/5 border-b border-white/5">
                        <h3 className="label-text mb-0">Select Pilot</h3>
                    </div>

                    <div className="divide-y divide-white/5 flex-grow overflow-y-auto custom-scrollbar">
                        {users.map(user => (
                            <div 
                                key={user.id}
                                className={`p-2.5 hover:bg-white/5 cursor-pointer transition flex items-center gap-3 group ${selectedUser?.id === user.id ? 'bg-white/10' : ''}`}
                                onClick={() => selectPilot(user)}
                            >
                                <img src={`https://images.evetech.net/characters/${user.char_id}/portrait?size=64`} className="w-8 h-8 rounded border border-white/10 group-hover:border-white transition" alt="" />
                                <div>
                                    <div className="text-white font-bold text-xs group-hover:text-brand-400 transition">{user.username}</div>
                                    <div className="text-[10px] text-slate-500">{user.corp || "Unknown Corp"}</div>
                                </div>
                            </div>
                        ))}
                        {users.length === 0 && <div className="p-8 text-center text-slate-500 italic">No pilots found.</div>}
                    </div>

                    {/* Pagination */}
                    {pagination.num_pages > 1 && (
                        <div className="p-3 bg-white/5 border-t border-white/5 flex justify-between items-center text-xs shrink-0">
                            <button 
                                disabled={!pagination.has_previous}
                                onClick={() => setPage(p => p - 1)}
                                className="btn-secondary py-1 px-2 text-[10px] disabled:opacity-50"
                            >
                                Previous
                            </button>
                            <span className="text-slate-500 font-mono">Page {pagination.current_page} / {pagination.num_pages}</span>
                            <button 
                                disabled={!pagination.has_next}
                                onClick={() => setPage(p => p + 1)}
                                className="btn-secondary py-1 px-2 text-[10px] disabled:opacity-50"
                            >
                                Next
                            </button>
                        </div>
                    )}
                </div>

                {/* Right: Role Editor */}
                <div className={`lg:col-span-2 glass-panel overflow-hidden flex-col transition-all duration-300 h-full ${selectedUser ? 'flex' : 'hidden'}`}>
                    {selectedUser && (
                        <>
                            <div className="p-6 bg-white/5 border-b border-white/5 flex items-center gap-4 shrink-0">
                                <img src={`https://images.evetech.net/characters/${selectedUser.char_id}/portrait?size=128`} className="w-16 h-16 rounded-lg border-2 border-white/10 shadow-lg" alt="" />
                                <div>
                                    <h2 className="text-2xl font-bold text-white tracking-tight">{selectedUser.username}</h2>
                                    <p className="text-slate-400 text-sm">{selectedUser.corp}</p>
                                </div>
                            </div>

                            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8 overflow-y-auto custom-scrollbar flex-grow">
                                {/* Current Roles */}
                                <div>
                                    <h3 className="label-text flex items-center gap-2 mb-4">
                                        <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]"></span> Current Roles
                                    </h3>
                                    <div className="space-y-2">
                                        {userRoles.current_roles.map(role => (
                                            <button 
                                                key={role}
                                                onClick={() => updateRole(selectedUser.id, role, 'remove')}
                                                className="w-full text-left bg-white/5 hover:bg-red-900/20 border border-white/5 hover:border-red-500/30 p-3 rounded-lg flex justify-between items-center group transition"
                                            >
                                                <span className="text-slate-200 font-bold text-sm group-hover:text-red-200">{role}</span>
                                                <span className="badge badge-red opacity-0 group-hover:opacity-100 transition">Remove</span>
                                            </button>
                                        ))}
                                        {userRoles.current_roles.length === 0 && <div className="text-sm text-slate-500 italic">No special roles assigned.</div>}
                                    </div>
                                </div>

                                {/* Available Roles */}
                                <div>
                                    <h3 className="label-text flex items-center gap-2 mb-4">
                                        <span className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]"></span> Available to Assign
                                    </h3>
                                    <div className="space-y-2">
                                        {userRoles.available_roles.filter(r => !userRoles.current_roles.includes(r)).map(role => (
                                            <button 
                                                key={role}
                                                onClick={() => updateRole(selectedUser.id, role, 'add')}
                                                className="w-full text-left bg-white/5 hover:bg-blue-900/20 border border-white/5 hover:border-blue-500/30 p-3 rounded-lg flex justify-between items-center group transition"
                                            >
                                                <span className="text-slate-200 font-bold text-sm group-hover:text-blue-200">{role}</span>
                                                <span className="badge badge-brand opacity-0 group-hover:opacity-100 transition">Add</span>
                                            </button>
                                        ))}
                                        {userRoles.available_roles.length === 0 && <div className="text-sm text-slate-500 italic">No roles available to assign.</div>}
                                    </div>
                                    <p className="text-xs text-slate-500 mt-4 italic border-t border-white/5 pt-2">
                                        Note: You can only assign roles that are below your own rank in the hierarchy.
                                    </p>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ManagementRoles;