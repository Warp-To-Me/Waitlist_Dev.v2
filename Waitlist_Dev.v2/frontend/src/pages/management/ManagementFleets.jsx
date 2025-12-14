import React, { useEffect, useState } from 'react';
import { Play, Square, Trash2, Clock } from 'lucide-react';

const ManagementFleets = () => {
    const [fleets, setFleets] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchFleets = () => {
        fetch('/api/management/fleets/')
            .then(res => res.json())
            .then(data => {
                setFleets(data.fleets || []);
                setLoading(false);
            });
    };

    useEffect(() => {
        fetchFleets();
    }, []);

    const handleAction = (action, fleetId = null, name = null) => {
        const body = { action, fleet_id: fleetId, name };
        fetch('/api/management/fleets/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') // Function needed
            },
            body: JSON.stringify(body)
        }).then(res => {
            if (res.ok) fetchFleets();
        });
    };

    const getCookie = (name) => {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="heading-1">Fleet Management</h1>
                <button
                    onClick={() => {
                        const name = prompt("Enter Fleet Name/Type:");
                        if(name) handleAction('create', null, name);
                    }}
                    className="btn-primary text-sm"
                >
                    <Play size={16} /> Start New Fleet
                </button>
            </div>

            <div className="glass-panel overflow-hidden">
                <table className="w-full text-left">
                    <thead>
                        <tr className="bg-white/5 border-b border-white/5 text-xs text-slate-400 uppercase">
                            <th className="p-4">Status</th>
                            <th className="p-4">Name / Type</th>
                            <th className="p-4">Commander</th>
                            <th className="p-4">Members</th>
                            <th className="p-4">Created</th>
                            <th className="p-4 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-sm text-slate-300">
                        {fleets.map(f => (
                            <tr key={f.id} className="hover:bg-white/5 transition">
                                <td className="p-4">
                                    <span className={`badge ${f.is_active ? 'badge-green' : 'badge-slate'}`}>
                                        {f.is_active ? 'ACTIVE' : 'CLOSED'}
                                    </span>
                                </td>
                                <td className="p-4 font-bold text-white">{f.name}</td>
                                <td className="p-4 text-brand-400">{f.commander}</td>
                                <td className="p-4">{f.member_count}</td>
                                <td className="p-4 text-xs font-mono text-slate-500">
                                    {new Date(f.created_at).toLocaleString()}
                                </td>
                                <td className="p-4 text-right flex items-center justify-end gap-2">
                                    {f.is_active && (
                                        <button
                                            onClick={() => handleAction('close', f.id)}
                                            className="btn-secondary p-1.5 text-xs"
                                            title="Close Fleet"
                                        >
                                            <Square size={14} /> Close
                                        </button>
                                    )}
                                    <button
                                        onClick={() => {
                                            if(confirm("Delete fleet history?")) handleAction('delete', f.id);
                                        }}
                                        className="btn-danger p-1.5 text-xs"
                                        title="Delete History"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ManagementFleets;