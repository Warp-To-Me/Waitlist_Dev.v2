import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { Search, X, Shield, Wallet, BookOpen, Layers, User } from 'lucide-react';
import clsx from 'clsx';
import SmartPagination from '../../components/SmartPagination';
import { apiCall } from '../../utils/api';
import { 
    fetchUsers, setQuery, setPage, setSort, 
    fetchUserProfile, fetchUserRoles, clearInspect,
    selectUsersList, selectUsersQuery, selectUsersPagination, selectUsersSort, selectUsersLoading,
    selectInspectProfile, selectInspectLoading, selectUserRoles, selectUserRolesLoading 
} from '../../store/slices/usersSlice';
import { selectHasCapability } from '../../store/slices/authSlice';

const ManagementUsers = () => {
    const dispatch = useDispatch();
    const navigate = useNavigate();
    
    // Selectors
    const users = useSelector(selectUsersList);
    const query = useSelector(selectUsersQuery);
    const pagination = useSelector(selectUsersPagination);
    const sort = useSelector(selectUsersSort);
    const loading = useSelector(selectUsersLoading);
    
    // Inspect & Roles State
    const userRoles = useSelector(selectUserRoles);
    
    // Permissions
    const canPromote = useSelector(selectHasCapability('promote_demote_users'));
    const canViewSensitive = useSelector(selectHasCapability('view_sensitive_data'));

    // Local State
    const [selectedUser, setSelectedUser] = useState(null);

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
    
    const handleRowClick = (user) => {
        if (canPromote) {
            setSelectedUser(user);
            dispatch(fetchUserRoles(user.id));
        }
    };
    
    const handleInspectProfile = (user) => {
        navigate(`/profile?user_id=${user.id}`);
    };

    const handleCloseDrawer = () => {
        setSelectedUser(null);
        dispatch(clearInspect());
    };

    const handleRoleUpdate = (role, action) => {
        if (!selectedUser) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        
        apiCall('/api/mgmt/update_role/', {
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
                                    Character (Main) {sort.field === 'character' && (sort.dir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th onClick={() => handleSort('corporation')} className="p-4 font-bold cursor-pointer hover:text-white transition select-none">
                                    Corp {sort.field === 'corporation' && (sort.dir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th onClick={() => handleSort('linked')} className="p-4 font-bold cursor-pointer hover:text-white transition select-none w-1/3">
                                    Alts {sort.field === 'linked' && (sort.dir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th className="p-4 font-bold text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-sm text-slate-300">
                            {users.map(u => (
                                <tr 
                                    key={u.id} 
                                    onClick={() => handleRowClick(u)}
                                    className={clsx(
                                        "hover:bg-white/5 transition group",
                                        canPromote ? "cursor-pointer" : "cursor-default",
                                        selectedUser?.id === u.id && "bg-white/10"
                                    )}
                                >
                                    <td className="p-4 font-medium text-white flex items-center gap-3">
                                        <img src={`https://images.evetech.net/characters/${u.character_id}/portrait?size=32`} className="w-8 h-8 rounded-full border border-white/10" alt="" />
                                        <div>
                                            <div className="font-bold text-white">{u.character_name}</div>
                                            {u.linked_count > 1 && (
                                                <div className="text-xs text-slate-500 mt-0.5">{u.linked_count - 1} alts</div>
                                            )}
                                        </div>
                                    </td>
                                    <td className="p-4 text-slate-300">{u.corporation_name}</td>
                                    <td className="p-4">
                                        <div className="flex flex-wrap gap-2">
                                            {u.alts && u.alts.length > 0 ? (
                                                u.alts.map(alt => (
                                                    <span key={alt.character_id} className="badge bg-white/5 hover:bg-white/10 text-slate-300 border border-white/5 transition px-2 py-1 rounded text-xs flex items-center gap-2">
                                                        <img src={`https://images.evetech.net/characters/${alt.character_id}/portrait?size=32`} className="w-4 h-4 rounded-full opacity-75" alt="" />
                                                        {alt.character_name}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-xs text-slate-600 italic">No Alts Registered</span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="p-4 text-right">
                                        <button 
                                            onClick={(e) => { e.stopPropagation(); handleInspectProfile(u); }}
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

            {/* ROLE MANAGEMENT MODAL */}
            {selectedUser && canPromote && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={handleCloseDrawer}>
                    <div
                        onClick={(e) => e.stopPropagation()}
                        className="glass-panel w-full max-w-5xl max-h-[85vh] flex flex-col shadow-2xl bg-[#0f1014] animate-in zoom-in-95 duration-200"
                    >
                        {/* Modal Header */}
                        <div className="p-6 border-b border-white/5 flex items-start justify-between bg-black/20 shrink-0">
                            <div className="flex items-center gap-4">
                                <img src={`https://images.evetech.net/characters/${selectedUser.character_id}/portrait?size=128`} className="w-16 h-16 rounded-lg border-2 border-white/10 shadow-lg" alt="" />
                                <div>
                                    <h2 className="text-xl font-bold text-white">{selectedUser.character_name}</h2>
                                    <p className="text-brand-400 text-sm">{selectedUser.corporation_name}</p>
                                </div>
                            </div>
                            <button onClick={handleCloseDrawer} className="p-2 hover:bg-white/10 rounded-full transition text-slate-400 hover:text-white">
                                <X size={20} />
                            </button>
                        </div>

                        {/* Tabs (Single Tab for Roles) */}
                        <div className="flex border-b border-white/5 shrink-0">
                            <div className="flex-1 p-3 text-sm font-bold border-b-2 border-blue-500 text-blue-500 bg-blue-500/5 flex items-center justify-center gap-2">
                                <Shield size={14} /> Roles Management
                            </div>
                        </div>

                        {/* Content Grid */}
                        <div className="flex-grow overflow-y-auto custom-scrollbar p-6">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                {/* Current Roles Column */}
                                <div className="bg-white/5 rounded-lg p-4 border border-white/5">
                                    <h3 className="label-text flex items-center gap-2 mb-4 pb-2 border-b border-white/5">
                                        <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]"></span> Current Roles
                                    </h3>
                                    <div className="space-y-1">
                                        {userRoles.current_roles.map(role => (
                                            <button
                                                key={role}
                                                onClick={() => handleRoleUpdate(role, 'remove')}
                                                className="w-full text-left bg-black/20 hover:bg-red-900/20 border border-white/5 hover:border-red-500/30 p-2 rounded flex justify-between items-center group transition"
                                            >
                                                <span className="text-slate-200 font-bold text-xs group-hover:text-red-200">{role}</span>
                                                <span className="badge badge-red opacity-0 group-hover:opacity-100 transition text-[10px] py-0.5 px-1.5">Remove</span>
                                            </button>
                                        ))}
                                        {userRoles.current_roles.length === 0 && <div className="text-xs text-slate-500 italic p-2 text-center">No special roles assigned.</div>}
                                    </div>
                                </div>

                                {/* Available Roles Column */}
                                <div className="bg-white/5 rounded-lg p-4 border border-white/5 flex flex-col">
                                    <h3 className="label-text flex items-center gap-2 mb-4 pb-2 border-b border-white/5">
                                        <span className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]"></span> Available Roles
                                    </h3>
                                    <div className="space-y-1 flex-grow overflow-y-auto custom-scrollbar max-h-[400px]">
                                        {userRoles.available_roles.filter(r => !userRoles.current_roles.includes(r)).map(role => (
                                            <button
                                                key={role}
                                                onClick={() => handleRoleUpdate(role, 'add')}
                                                className="w-full text-left bg-black/20 hover:bg-blue-900/20 border border-white/5 hover:border-blue-500/30 p-2 rounded flex justify-between items-center group transition"
                                            >
                                                <span className="text-slate-200 font-bold text-xs group-hover:text-blue-200">{role}</span>
                                                <span className="badge badge-brand opacity-0 group-hover:opacity-100 transition text-[10px] py-0.5 px-1.5">Add</span>
                                            </button>
                                        ))}
                                        {userRoles.available_roles.length === 0 && <div className="text-xs text-slate-500 italic p-2 text-center">No other roles available.</div>}
                                    </div>
                                    <p className="text-[10px] text-slate-500 mt-4 italic pt-2 border-t border-white/5">
                                        Note: You can only assign roles that are below your own rank.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManagementUsers;