import React, { useEffect, useState } from 'react';
import { ShieldAlert, Plus, Trash, RotateCcw, Search, Edit } from 'lucide-react';
import { apiCall } from '../../utils/api';

const ManagementBans = () => {
    const [bans, setBans] = useState([]);
    const [filter, setFilter] = useState('active'); // active, permanent
    const [modalOpen, setModalOpen] = useState(false);
    const [editBanId, setEditBanId] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [selectedUser, setSelectedUser] = useState(null);
    const [reason, setReason] = useState('');
    const [duration, setDuration] = useState('permanent');

    const fetchBans = () => {
        apiCall(`/api/management/bans/?filter=${filter}`)
            .then(res => res.json())
            .then(data => setBans(data.bans || []));
    };

    useEffect(() => {
        fetchBans();
    }, [filter]);

    // Search Users
    useEffect(() => {
        if (searchQuery.length < 3) {
            setSearchResults([]);
            return;
        }
        const timer = setTimeout(() => {
            apiCall(`/api/mgmt/search_users/?q=${encodeURIComponent(searchQuery)}`)
                .then(r => r.json())
                .then(data => setSearchResults(data.results || []));
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    const openModal = (ban = null) => {
        if (ban) {
            setEditBanId(ban.id);
            setSelectedUser({ id: ban.user_id, username: ban.user_name });
            setReason(ban.reason);
            setDuration('permanent'); // Simplifying for edit as per template behavior
        } else {
            setEditBanId(null);
            setSelectedUser(null);
            setReason('');
            setDuration('permanent');
            setSearchQuery('');
            setSearchResults([]);
        }
        setModalOpen(true);
    };

    const submitBan = () => {
        if (!selectedUser && !editBanId) return alert("Please select a user.");
        if (!reason) return alert("Please provide a reason.");

        const payload = {
            reason,
            duration,
            action: editBanId ? 'update' : 'add'
        };

        if (editBanId) {
            payload.ban_id = editBanId;
        } else {
            payload.user_id = selectedUser.id;
        }

        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall(editBanId ? '/api/mgmt/bans/update/' : '/api/mgmt/bans/add/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify(payload)
        }).then(res => res.json()).then(data => {
            if (data.success) {
                setModalOpen(false);
                fetchBans();
            } else {
                alert(data.error);
            }
        });
    };

    const removeBan = (banId, username) => {
        if (!confirm(`Are you sure you want to remove the ban for ${username}?`)) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/mgmt/bans/update/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action: 'remove', ban_id: banId })
        }).then(res => res.json()).then(data => {
            if (data.success) fetchBans();
            else alert(data.error);
        });
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="heading-1">Ban Management</h1>
                    <p className="text-slate-400 mt-1 text-sm">Manage user bans and restrictions.</p>
                </div>
                <div className="flex space-x-3">
                    {/* Check perm logic in real app, showing always as per instructions */}
                    <a href="/management/bans/audit" className="btn-secondary text-xs py-2 px-4 flex items-center gap-2">
                        <span>📜</span> Audit Log
                    </a>
                    <button onClick={() => openModal()} className="btn-danger text-xs py-2 px-4 shadow-lg shadow-red-900/20 flex items-center gap-2">
                        <span>🚫</span> Ban User
                    </button>
                </div>
            </div>

            {/* Filter Bar */}
            <div className="flex gap-2">
                {['active', 'permanent'].map(f => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition border ${filter === f ? 'bg-brand-500 text-white border-brand-400' : 'bg-white/5 text-slate-400 border-white/10 hover:text-white hover:border-white/30'}`}
                    >
                        {f}
                    </button>
                ))}
            </div>

            {/* Active Bans Table */}
            <div className="glass-panel overflow-hidden">
                <div className="p-6 border-b border-white/5">
                    <h3 className="font-bold text-slate-200 capitalize">
                        {filter === 'active' ? 'Active Bans' : 'Permanent Bans Only'}
                    </h3>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-slate-400">
                        <thead className="text-xs uppercase bg-white/5 text-slate-300 font-bold">
                            <tr>
                                <th className="px-6 py-4">User</th>
                                <th className="px-6 py-4">Reason</th>
                                <th className="px-6 py-4">Issued By</th>
                                <th className="px-6 py-4">Issued At</th>
                                <th className="px-6 py-4">Expires</th>
                                <th className="px-6 py-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-slate-300">
                            {bans.map(ban => (
                                <tr key={ban.id} className={`hover:bg-white/5 transition ${!ban.is_active ? 'opacity-50' : ''}`}>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400 overflow-hidden">
                                                {ban.user_char_id ? (
                                                    <img src={`https://images.evetech.net/characters/${ban.user_char_id}/portrait?size=64`} alt="" className="w-full h-full object-cover" />
                                                ) : (
                                                    (ban.user_name || '?').slice(0, 2).toUpperCase()
                                                )}
                                            </div>
                                            <div>
                                                <div className="font-bold text-slate-200">{ban.user_char_name || ban.user_name}</div>
                                                <div className="text-xs text-slate-500">ID: {ban.user_char_id || ban.user_name}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 max-w-xs truncate" title={ban.reason}>
                                        {ban.reason}
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="badge badge-slate">
                                            {ban.issuer_char_name || ban.issuer_name || "System"}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-slate-400 text-xs font-mono">
                                        {new Date(ban.created_at).toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4 text-xs font-mono">
                                        {ban.expires_at ? (
                                            <span className={ban.is_active ? 'text-brand-400' : 'text-green-400'}>
                                                {new Date(ban.expires_at).toLocaleString()}
                                            </span>
                                        ) : (
                                            <span className="text-red-400 font-bold uppercase">Permanent</span>
                                        )}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex justify-end gap-2">
                                            <button onClick={() => openModal(ban)} className="btn-secondary p-1.5" title="Edit Ban">
                                                <Edit size={16} />
                                            </button>
                                            <button onClick={() => removeBan(ban.id, ban.user_char_name || ban.user_name)} className="btn-secondary p-1.5 hover:text-green-400 hover:border-green-500/50" title="Lift Ban">
                                                <RotateCcw size={16} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            {bans.length === 0 && (
                                <tr>
                                    <td colSpan="6" className="p-12 text-center text-slate-500 italic">
                                        No bans found matching filter.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Ban Modal */}
            {modalOpen && (
                <div className="fixed inset-0 bg-dark-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl w-full max-w-lg transform transition-all scale-100">
                        <div className="glass-header px-6 py-4 flex justify-between items-center border-b border-white/5">
                            <h3 className="text-xl font-bold text-white">{editBanId ? 'Update Ban' : 'Ban User'}</h3>
                            <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-white transition">✕</button>
                        </div>

                        <div className="p-6 space-y-4">
                            {/* User Search (Only for New Ban) */}
                            {!editBanId && (
                                <div>
                                    <label className="label-text">Target User</label>
                                    <div className="relative">
                                        <input 
                                            type="text" 
                                            className="input-field pl-10"
                                            placeholder="Search by character name..." 
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                        />
                                        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                                            <Search className="w-5 h-5 text-slate-500" />
                                        </div>
                                        {searchResults.length > 0 && (
                                            <div className="absolute w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 max-h-48 overflow-y-auto custom-scrollbar">
                                                {searchResults.map(user => (
                                                    <div 
                                                        key={user.id}
                                                        className="px-4 py-2 hover:bg-slate-700 cursor-pointer border-b border-slate-700 last:border-0 transition"
                                                        onClick={() => {
                                                            setSelectedUser(user);
                                                            setSearchQuery(user.username);
                                                            setSearchResults([]);
                                                        }}
                                                    >
                                                        <div className="font-bold text-slate-200 text-sm">{user.username}</div>
                                                        <div className="text-xs text-slate-400">{user.corp}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                    {selectedUser && <input type="hidden" value={selectedUser.id} />}
                                </div>
                            )}

                            {/* User Display (For Edit Mode) */}
                            {editBanId && (
                                <div>
                                    <label className="label-text">Target User</label>
                                    <input type="text" readOnly className="input-field bg-slate-800 text-slate-400 cursor-not-allowed border-slate-700" value={selectedUser?.username || ''} />
                                </div>
                            )}

                            {/* Reason */}
                            <div>
                                <label className="label-text">Reason</label>
                                <textarea 
                                    rows="3"
                                    className="input-field resize-none"
                                    placeholder="Why is this user being banned?"
                                    value={reason}
                                    onChange={(e) => setReason(e.target.value)}
                                ></textarea>
                            </div>

                            {/* Duration */}
                            <div>
                                <label className="label-text">Duration</label>
                                <select className="select-field" value={duration} onChange={(e) => setDuration(e.target.value)}>
                                    <option value="5">5 Minutes</option>
                                    <option value="60">1 Hour</option>
                                    <option value="1440">24 Hours</option>
                                    <option value="10080">1 Week</option>
                                    <option value="43200">1 Month</option>
                                    <option value="525600">1 Year</option>
                                    <option value="permanent">Permanent</option>
                                </select>
                            </div>
                        </div>

                        <div className="p-6 border-t border-white/5 bg-slate-900/50 flex justify-end gap-2">
                            <button onClick={() => setModalOpen(false)} className="btn-ghost text-xs">Cancel</button>
                            <button onClick={submitBan} className="btn-danger text-xs px-6 shadow-lg shadow-red-900/20">
                                Confirm Ban
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManagementBans;