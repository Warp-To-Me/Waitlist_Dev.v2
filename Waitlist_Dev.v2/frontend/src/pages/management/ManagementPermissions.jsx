import React, { useEffect, useState } from 'react';
import { ChevronUp, ChevronDown, Plus, Edit, Trash, Save } from 'lucide-react';
import { apiCall } from '../../utils/api';

const ManagementPermissions = () => {
    const [groups, setGroups] = useState([]);
    const [capabilities, setCapabilities] = useState([]);
    const [orderDirty, setOrderDirty] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalData, setModalData] = useState({ action: 'create', id: '', name: '' });

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = () => {
        apiCall('/api/management/permissions/')
            .then(res => res.json())
            .then(data => {
                setGroups(data.groups || []);
                setCapabilities(data.capabilities || []);
                setOrderDirty(false);
            });
    };

    const togglePermission = (groupId, capId) => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        
        // Optimistic update
        const updatedGroups = groups.map(g => {
            if (g.id === groupId) {
                const hasCap = g.capabilities.includes(capId);
                return {
                    ...g,
                    capabilities: hasCap 
                        ? g.capabilities.filter(c => c !== capId)
                        : [...g.capabilities, capId]
                };
            }
            return g;
        });
        setGroups(updatedGroups);

        apiCall('/api/mgmt/permissions/toggle/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ group_id: groupId, cap_id: capId })
        }).then(res => res.json()).then(data => {
            if (!data.success) {
                alert(data.error);
                fetchData(); // Revert
            }
        });
    };

    const moveGroup = (index, direction) => {
        const newGroups = [...groups];
        if (direction === 'up' && index > 0) {
            [newGroups[index - 1], newGroups[index]] = [newGroups[index], newGroups[index - 1]];
        } else if (direction === 'down' && index < newGroups.length - 1) {
            [newGroups[index + 1], newGroups[index]] = [newGroups[index], newGroups[index + 1]];
        }
        setGroups(newGroups);
        setOrderDirty(true);
    };

    const saveOrder = () => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/mgmt/roles/reorder/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ ordered_ids: groups.map(g => g.id) })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                setOrderDirty(false);
            } else {
                alert(data.error);
            }
        });
    };

    const handleModalSubmit = () => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/mgmt/groups/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify(modalData)
        }).then(res => res.json()).then(data => {
            if (data.success) {
                setModalOpen(false);
                fetchData();
            } else {
                alert(data.error);
            }
        });
    };

    const deleteGroup = (id, name) => {
        if (!confirm(`Delete group "${name}"?`)) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/mgmt/groups/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action: 'delete', id })
        }).then(res => res.json()).then(data => {
            if (data.success) fetchData(); else alert(data.error);
        });
    };

    return (
        <div className="flex flex-col gap-6 animate-fade-in pb-20">
            {/* Header */}
            <div className="flex justify-between items-end border-b border-white/5 pb-6">
                <div>
                    <h1 className="heading-1">Access Control Matrix</h1>
                    <p className="text-slate-400 text-sm mt-1">Manage groups and capabilities dynamically.</p>
                </div>
                <div className="flex gap-2">
                    {orderDirty && (
                        <button onClick={saveOrder} className="btn-success py-2 px-4 text-xs shadow-green-500/20 animate-pulse flex items-center gap-2">
                            <Save size={14} /> Save Order
                        </button>
                    )}
                    <button onClick={() => { setModalData({ action: 'create', id: '', name: '' }); setModalOpen(true); }} className="btn-primary py-2 px-4 text-xs shadow-brand-500/20 flex items-center gap-2">
                        <Plus size={14} /> Create Group
                    </button>
                </div>
            </div>

            {/* Matrix */}
            <div className="glass-panel overflow-hidden flex flex-col">
                <div className="overflow-x-auto custom-scrollbar relative">
                    <table className="w-full text-sm text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-900/90 text-xs uppercase tracking-wider text-slate-300">
                                <th className="p-4 sticky left-0 z-30 bg-slate-900/95 border-r border-b border-white/10 w-72 shadow-xl backdrop-blur-md">
                                    Role / Group
                                </th>
                                {capabilities.map(cap => (
                                    <th key={cap.id} className="p-2 text-center min-w-[60px] max-w-[100px] border-r border-b border-white/10 group relative hover:bg-white/5 transition align-bottom pb-4">
                                        <div className="absolute inset-0 group-hover:bg-white/5 transition z-0"></div>
                                        <div 
                                            className="writing-mode-vertical transform rotate-180 text-[10px] font-bold tracking-widest text-slate-400 group-hover:text-white transition cursor-help h-48 flex items-center justify-start relative z-10" 
                                            title={cap.description}
                                        >
                                            {cap.name}
                                        </div>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {groups.map((group, index) => (
                                <tr key={group.id} className="hover:bg-white/5 transition group/row">
                                    <td className="p-4 sticky left-0 z-20 bg-slate-900/95 border-r border-white/10 group-hover/row:bg-white/10 transition backdrop-blur-md shadow-xl">
                                        <div className="flex justify-between items-center gap-2">
                                            <div className="flex items-center gap-3">
                                                <div className="flex flex-col gap-0.5 opacity-0 group-hover/row:opacity-100 transition">
                                                    <button onClick={() => moveGroup(index, 'up')} className="text-slate-600 hover:text-brand-400 leading-none">
                                                        <ChevronUp size={12} />
                                                    </button>
                                                    <button onClick={() => moveGroup(index, 'down')} className="text-slate-600 hover:text-brand-400 leading-none">
                                                        <ChevronDown size={12} />
                                                    </button>
                                                </div>
                                                <span className="font-bold text-white text-sm truncate" title={group.name}>{group.name}</span>
                                            </div>

                                            <div className="flex gap-1 opacity-0 group-hover/row:opacity-100 transition shrink-0">
                                                <button onClick={() => { setModalData({ action: 'update', id: group.id, name: group.name }); setModalOpen(true); }} className="p-1 hover:bg-blue-500/20 rounded text-slate-500 hover:text-blue-400 transition" title="Rename">
                                                    <Edit size={12} />
                                                </button>
                                                {group.name !== 'Admin' && (
                                                    <button onClick={() => deleteGroup(group.id, group.name)} className="p-1 hover:bg-red-500/20 rounded text-slate-500 hover:text-red-400 transition" title="Delete">
                                                        <Trash size={12} />
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </td>
                                    {capabilities.map(cap => (
                                        <td 
                                            key={cap.id} 
                                            className="p-0 border-r border-white/5 last:border-r-0 relative cursor-pointer hover:bg-white/10 transition"
                                            onClick={() => togglePermission(group.id, cap.id)}
                                            title={`${group.name} -> ${cap.name}`}
                                        >
                                            <div className="w-full h-full min-h-[48px] flex items-center justify-center">
                                                {group.capabilities.includes(cap.id) ? (
                                                    <div className="w-3 h-3 rounded-sm bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)] transition-all duration-300 transform scale-100"></div>
                                                ) : (
                                                    <div className="w-1 h-1 rounded-full bg-slate-800 transition-all duration-300 transform scale-100 opacity-50"></div>
                                                )}
                                            </div>
                                        </td>
                                    ))}
                                </tr>
                            ))}
                            {groups.length === 0 && (
                                <tr><td colSpan="100%" className="p-8 text-center text-slate-500 italic">No groups found.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Modal */}
            {modalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark-950/80 backdrop-blur-sm px-4">
                    <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-fade-in">
                        <div className="glass-header px-6 py-4 border-b border-white/5 flex justify-between items-center">
                            <h3 className="font-bold text-white text-lg">{modalData.action === 'create' ? 'Create New Group' : 'Rename Group'}</h3>
                            <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
                        </div>
                        <div className="p-6 space-y-4">
                            <div>
                                <label className="label-text">Group Name</label>
                                <input 
                                    type="text" 
                                    className="input-field" 
                                    placeholder="e.g. Logistics Commander" 
                                    value={modalData.name}
                                    onChange={(e) => setModalData({ ...modalData, name: e.target.value })}
                                />
                            </div>
                            <div className="flex justify-end gap-2 pt-2">
                                <button onClick={() => setModalOpen(false)} className="btn-ghost text-xs">Cancel</button>
                                <button onClick={handleModalSubmit} className="btn-primary text-xs px-6">Save</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                .writing-mode-vertical {
                    writing-mode: vertical-rl;
                    text-orientation: mixed;
                }
            `}</style>
        </div>
    );
};

export default ManagementPermissions;