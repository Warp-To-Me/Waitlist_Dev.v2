import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Search, X, Shield, Wallet, BookOpen, Layers } from 'lucide-react';
import clsx from 'clsx';
import SmartPagination from '../../components/SmartPagination';
import { 
    fetchUsers, setQuery, setPage, setSort,
    fetchUserProfile, fetchUserRoles, clearInspect,
    selectUsersList, selectUsersQuery, selectUsersPagination, selectUsersSort, selectUsersLoading,
    selectInspectProfile, selectInspectLoading, selectUserRoles, selectUserRolesLoading
} from '../../store/slices/usersSlice';
import { selectHasCapability } from '../../store/slices/authSlice';

const ManagementUsers = () => {
    const dispatch = useDispatch();

    // Selectors
    const users = useSelector(selectUsersList);
    const query = useSelector(selectUsersQuery);
    const pagination = useSelector(selectUsersPagination);
    const sort = useSelector(selectUsersSort);
    const loading = useSelector(selectUsersLoading);

    // Inspect & Roles State
    const profile = useSelector(selectInspectProfile);
    const userRoles = useSelector(selectUserRoles);
    const inspectLoading = useSelector(selectInspectLoading);

    // Permissions
    const canPromote = useSelector(selectHasCapability('promote_demote_users'));
    const canViewSensitive = useSelector(selectHasCapability('view_sensitive_data'));

    // Local State
    const [selectedUser, setSelectedUser] = useState(null);
    const [activeTab, setActiveTab] = useState('profile'); // 'profile' | 'roles'

    // Initial Load & Debounce Search
    useEffect(() => {
        const timeout = setTimeout(() => {
            dispatch(fetchUsers({
                query,
                page: pagination.current,
                sort: sort.field,
                dir: sort.dir
            }));
        }, 300);
        return () => clearTimeout(timeout);
    }, [query, pagination.current, sort.field, sort.dir, dispatch]);

    // Cleanup on unmount
    useEffect(() => {
        return () => { dispatch(clearInspect()); };
    }, [dispatch]);

    // Handlers
    const handleSearch = (e) => dispatch(setQuery(e.target.value));
    const handleSort = (field) => dispatch(setSort(field));

    const handleInspect = (user) => {
        setSelectedUser(user);
        setActiveTab('profile');
        dispatch(fetchUserProfile(user.id));
        if (canPromote) {
            dispatch(fetchUserRoles(user.id));
        }
    };

    const handleCloseDrawer = () => {
        setSelectedUser(null);
        dispatch(clearInspect());
    };

    const handleRoleUpdate = (role, action) => {
        if (!selectedUser) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];

        fetch('/api/mgmt/update_role/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ user_id: selectedUser.id, role, action })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                dispatch(fetchUserRoles(selectedUser.id)); // Refresh roles
            } else {
                alert(data.error || "Failed to update role");
            }
        });
    };

    return (
        <div className="relative h-full flex flex-col">
            {/* Header */}
            <div className="flex justify-between items-center mb-6 shrink-0">
                <div>
                    <h1 className="heading-1">User Management</h1>
                    <p className="text-slate-400 text-sm mt-1">Manage pilots, permissions, and profiles.</p>
                </div>
                <div className="relative group">
                    <Search className="absolute left-3 top-2.5 text-slate-500 group-focus-within:text-brand-400 transition" size={16} />
                    <input 
                        type="text" 
                        placeholder="Search pilots..." 
                        className="input-field pl-10 w-64 focus:w-80 transition-all duration-300"
                        value={query}
                        onChange={handleSearch}
                    />
                </div>
            </div>

            {/* Main Table */}
            <div className="glass-panel overflow-hidden flex-grow relative flex flex-col">
                <div className="overflow-x-auto custom-scrollbar flex-grow">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-white/5 border-b border-white/5 text-xs text-slate-400 uppercase sticky top-0 backdrop-blur-md z-10">
                                <th onClick={() => handleSort('character')} className="p-4 font-bold cursor-pointer hover:text-white transition select-none">
                                    Character {sort.field === 'character' && (sort.dir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th onClick={() => handleSort('main')} className="p-4 font-bold cursor-pointer hover:text-white transition select-none">
                                    Main {sort.field === 'main' && (sort.dir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th onClick={() => handleSort('corporation')} className="p-4 font-bold cursor-pointer hover:text-white transition select-none">
                                    Corp {sort.field === 'corporation' && (sort.dir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th onClick={() => handleSort('linked')} className="p-4 font-bold cursor-pointer hover:text-white transition select-none">
                                    Alts {sort.field === 'linked' && (sort.dir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th className="p-4 font-bold text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-sm text-slate-300">
                            {users.map(u => (
                                <tr
                                    key={u.id}
                                    onClick={() => handleInspect(u)}
                                    className={clsx(
                                        "hover:bg-white/5 transition cursor-pointer group",
                                        selectedUser?.id === u.id && "bg-white/10"
                                    )}
                                >
                                    <td className="p-4 font-medium text-white flex items-center gap-3">
                                        <img src={`https://images.evetech.net/characters/${u.character_id}/portrait?size=32`} className="w-8 h-8 rounded-full border border-white/10" alt="" />
                                        {u.character_name}
                                    </td>
                                    <td className="p-4 text-brand-400 font-medium">
                                        {u.main_character_name}
                                    </td>
                                    <td className="p-4">{u.corporation_name}</td>
                                    <td className="p-4">
                                        <span className={clsx("badge", u.linked_count > 1 ? "badge-blue" : "bg-white/5 text-slate-500")}>
                                            {u.linked_count} Linked
                                        </span>
                                    </td>
                                    <td className="p-4 text-right">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleInspect(u); }}
                                            className="text-brand-400 hover:text-white transition font-medium text-xs uppercase tracking-wider"
                                        >
                                            Inspect
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {users.length === 0 && !loading && (
                                <tr>
                                    <td colSpan="5" className="p-8 text-center text-slate-500 italic">No pilots found.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                <div className="p-4 border-t border-white/5 flex justify-between items-center bg-black/20 shrink-0">
                    <span className="text-xs text-slate-500">Showing {users.length} of many</span>
                    <SmartPagination
                        current={pagination.current}
                        total={pagination.total}
                        onChange={(p) => dispatch(setPage(p))}
                    />
                </div>
            </div>

            {/* SLIDE-OVER DRAWER */}
            {selectedUser && (
                <div className="absolute inset-y-0 right-0 w-full md:w-[600px] glass-panel shadow-2xl border-l border-white/10 flex flex-col z-50 animate-in slide-in-from-right duration-300 bg-[#0f1014]">
                    {/* Drawer Header */}
                    <div className="p-6 border-b border-white/5 flex items-start justify-between bg-black/20 shrink-0">
                        <div className="flex items-center gap-4">
                            <img src={`https://images.evetech.net/characters/${selectedUser.character_id}/portrait?size=128`} className="w-16 h-16 rounded-lg border-2 border-white/10 shadow-lg" alt="" />
                            <div>
                                <h2 className="text-xl font-bold text-white">{profile?.username || selectedUser.character_name}</h2>
                                <p className="text-brand-400 text-sm">{profile?.active_char?.corporation_name || selectedUser.corporation_name}</p>
                            </div>
                        </div>
                        <button onClick={handleCloseDrawer} className="p-2 hover:bg-white/10 rounded-full transition text-slate-400 hover:text-white">
                            <X size={20} />
                        </button>
                    </div>

                    {/* Tabs */}
                    <div className="flex border-b border-white/5 shrink-0">
                        <button
                            onClick={() => setActiveTab('profile')}
                            className={clsx("flex-1 p-3 text-sm font-bold transition border-b-2", activeTab === 'profile' ? "border-brand-500 text-brand-500 bg-brand-500/5" : "border-transparent text-slate-400 hover:text-white")}
                        >
                            <div className="flex items-center justify-center gap-2">
                                <User size={14} /> Profile
                            </div>
                        </button>
                        {canPromote && (
                            <button
                                onClick={() => setActiveTab('roles')}
                                className={clsx("flex-1 p-3 text-sm font-bold transition border-b-2", activeTab === 'roles' ? "border-blue-500 text-blue-500 bg-blue-500/5" : "border-transparent text-slate-400 hover:text-white")}
                            >
                                <div className="flex items-center justify-center gap-2">
                                    <Shield size={14} /> Roles
                                </div>
                            </button>
                        )}
                    </div>

                    {/* Content */}
                    <div className="flex-grow overflow-y-auto custom-scrollbar p-6">
                        {inspectLoading ? (
                            <div className="flex items-center justify-center h-full text-slate-500 animate-pulse">Loading Profile...</div>
                        ) : activeTab === 'profile' ? (
                            <div className="space-y-6">
                                {/* Stats */}
                                <div className="grid grid-cols-3 gap-4">
                                    <div className="bg-white/5 p-3 rounded border border-white/5 text-center group hover:border-brand-500/30 transition">
                                        <div className="text-[10px] uppercase text-slate-500 font-bold mb-1 flex justify-center gap-1"><Wallet size={10} /> Wallet</div>
                                        <div className={clsx("font-mono text-sm", canViewSensitive ? "text-white" : "text-slate-500 blur-sm select-none")}>
                                            {canViewSensitive ? (profile?.totals?.wallet || 0).toLocaleString() : "9,999,999,999"}
                                        </div>
                                    </div>
                                    <div className="bg-white/5 p-3 rounded border border-white/5 text-center group hover:border-brand-500/30 transition">
                                        <div className="text-[10px] uppercase text-slate-500 font-bold mb-1 flex justify-center gap-1"><BookOpen size={10} /> SP</div>
                                        <div className="text-white font-mono text-sm">{(profile?.totals?.sp || 0).toLocaleString()}</div>
                                    </div>
                                    <div className="bg-white/5 p-3 rounded border border-white/5 text-center group hover:border-brand-500/30 transition">
                                        <div className="text-[10px] uppercase text-slate-500 font-bold mb-1 flex justify-center gap-1"><Layers size={10} /> LP</div>
                                        <div className="text-white font-mono text-sm">{(profile?.totals?.lp || 0).toLocaleString()}</div>
                                    </div>
                                </div>

                                {/* Characters */}
                                <div>
                                    <h3 className="label-text mb-2">Linked Characters</h3>
                                    <div className="space-y-2">
                                        {profile?.characters?.map(c => (
                                            <div key={c.character_id} className="flex items-center justify-between p-3 bg-white/5 rounded border border-white/5 hover:bg-white/10 transition">
                                                <div className="flex items-center gap-3">
                                                    <img src={`https://images.evetech.net/characters/${c.character_id}/portrait?size=32`} className="w-8 h-8 rounded" alt="" />
                                                    <div>
                                                        <div className="text-white text-sm font-medium">{c.character_name}</div>
                                                        <div className="text-xs text-slate-500">{c.corporation_name}</div>
                                                    </div>
                                                </div>
                                                {c.is_main ? <span className="badge badge-brand">Main</span> : <span className="text-xs text-slate-500">Alt</span>}
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Skills */}
                                <div>
                                    <h3 className="label-text mb-2">Skill Groups</h3>
                                    {profile?.grouped_skills && Object.entries(profile.grouped_skills).map(([group, skills]) => (
                                        <div key={group} className="mb-4">
                                            <h4 className="text-xs font-bold text-slate-400 uppercase mb-1 border-b border-white/5 pb-1">{group}</h4>
                                            <div className="grid grid-cols-2 gap-2">
                                                {skills.map(s => (
                                                    <div key={s.name} className="text-xs flex justify-between p-1 hover:bg-white/5 rounded transition">
                                                        <span className="text-slate-300 truncate pr-2">{s.name}</span>
                                                        <span className={clsx("font-mono", s.level === 5 ? "text-brand-400 font-bold" : "text-slate-500")}>Lvl {s.level}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                    {(!profile?.grouped_skills || Object.keys(profile.grouped_skills).length === 0) && (
                                        <div className="text-slate-500 text-sm italic">No skill data available.</div>
                                    )}
                                </div>
                            </div>
                        ) : (
                            // ROLES TAB
                            <div className="space-y-6">
                                <div>
                                    <h3 className="label-text flex items-center gap-2 mb-4">
                                        <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]"></span> Current Roles
                                    </h3>
                                    <div className="space-y-2">
                                        {userRoles.current_roles.map(role => (
                                            <button
                                                key={role}
                                                onClick={() => handleRoleUpdate(role, 'remove')}
                                                className="w-full text-left bg-white/5 hover:bg-red-900/20 border border-white/5 hover:border-red-500/30 p-3 rounded-lg flex justify-between items-center group transition"
                                            >
                                                <span className="text-slate-200 font-bold text-sm group-hover:text-red-200">{role}</span>
                                                <span className="badge badge-red opacity-0 group-hover:opacity-100 transition">Remove</span>
                                            </button>
                                        ))}
                                        {userRoles.current_roles.length === 0 && <div className="text-sm text-slate-500 italic p-2">No special roles assigned.</div>}
                                    </div>
                                </div>

                                <div>
                                    <h3 className="label-text flex items-center gap-2 mb-4">
                                        <span className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]"></span> Available Roles
                                    </h3>
                                    <div className="space-y-2">
                                        {userRoles.available_roles.filter(r => !userRoles.current_roles.includes(r)).map(role => (
                                            <button
                                                key={role}
                                                onClick={() => handleRoleUpdate(role, 'add')}
                                                className="w-full text-left bg-white/5 hover:bg-blue-900/20 border border-white/5 hover:border-blue-500/30 p-3 rounded-lg flex justify-between items-center group transition"
                                            >
                                                <span className="text-slate-200 font-bold text-sm group-hover:text-blue-200">{role}</span>
                                                <span className="badge badge-brand opacity-0 group-hover:opacity-100 transition">Add</span>
                                            </button>
                                        ))}
                                        {userRoles.available_roles.length === 0 && <div className="text-sm text-slate-500 italic p-2">No other roles available to assign.</div>}
                                    </div>
                                    <p className="text-xs text-slate-500 mt-4 italic border-t border-white/5 pt-2">
                                        Note: You can only assign roles that are below your own rank in the hierarchy.
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManagementUsers;
