import React, { useEffect, useState } from 'react';
import { ShieldAlert, Plus, Trash, RotateCcw } from 'lucide-react';

const ManagementBans = () => {
    const [bans, setBans] = useState([]);
    const [filter, setFilter] = useState('all'); // all, active, expired, permanent

    const fetchBans = () => {
        fetch(`/api/management/bans/?filter=${filter}`)
            .then(res => res.json())
            .then(data => setBans(data.bans || []));
    };

    useEffect(() => {
        fetchBans();
    }, [filter]);

    const handleBanAction = (action, banId) => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch('/api/mgmt/bans/update/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action, ban_id: banId })
        }).then(res => {
            if (res.ok) fetchBans();
        });
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="heading-1">Ban Management</h1>
                <button
                    onClick={() => alert("To ban a user, go to User Management > Inspect User")}
                    className="btn-primary text-sm"
                >
                    <Plus size={16} /> Ban User
                </button>
            </div>

            {/* Filter Tabs */}
            <div className="flex gap-2 border-b border-white/10 pb-4">
                {['all', 'active', 'permanent', 'expired'].map(f => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`px-4 py-2 rounded-lg text-sm font-bold capitalize transition ${filter === f ? 'bg-brand-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
                    >
                        {f}
                    </button>
                ))}
            </div>

            <div className="glass-panel overflow-hidden">
                <table className="w-full text-left">
                    <thead>
                        <tr className="bg-white/5 border-b border-white/5 text-xs text-slate-400 uppercase">
                            <th className="p-4">User</th>
                            <th className="p-4">Issuer</th>
                            <th className="p-4">Reason</th>
                            <th className="p-4">Expires</th>
                            <th className="p-4 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-sm text-slate-300">
                        {bans.map(b => (
                            <tr key={b.id} className="hover:bg-white/5 transition">
                                <td className="p-4 font-bold text-white">
                                    {b.user_name}
                                    <div className="text-xs text-slate-500 font-mono">UID: {b.user_id}</div>
                                </td>
                                <td className="p-4 text-brand-400">{b.issuer_name}</td>
                                <td className="p-4 text-slate-200">{b.reason}</td>
                                <td className="p-4">
                                    {b.expires_at ? (
                                        <span className={new Date(b.expires_at) < new Date() ? 'text-slate-500' : 'text-yellow-400'}>
                                            {new Date(b.expires_at).toLocaleString()}
                                        </span>
                                    ) : (
                                        <span className="badge badge-red">PERMANENT</span>
                                    )}
                                </td>
                                <td className="p-4 text-right">
                                    <button
                                        onClick={() => handleBanAction('remove', b.id)}
                                        className="btn-ghost text-red-400 hover:text-red-300 p-2"
                                        title="Lift Ban"
                                    >
                                        <Trash size={16} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {bans.length === 0 && <div className="p-8 text-center text-slate-500">No bans found matching filter.</div>}
            </div>
        </div>
    );
};

export default ManagementBans;