import React, { useEffect, useState, useRef } from 'react';
import { Trash, Plus, X } from 'lucide-react';
import clsx from 'clsx';
import { apiCall } from '../../utils/api';

const ManagementSkills = () => {
    const [view, setView] = useState('assignments'); // assignments, groups, tiers
    const [fits, setFits] = useState([]);
    const [tiers, setTiers] = useState([]);
    const [groups, setGroups] = useState([]);
    const [requirements, setRequirements] = useState([]);
    const [hullSearchResults, setHullSearchResults] = useState([]);
    const [selectedGroup, setSelectedGroup] = useState(null);
    const [groupMembers, setGroupMembers] = useState([]);

    // Forms
    const [targetType, setTargetType] = useState('fit');
    const [targetId, setTargetId] = useState('');
    const [reqType, setReqType] = useState('skill');
    const [skillName, setSkillName] = useState('');
    const [skillLevel, setSkillLevel] = useState(5);
    const [reqGroupId, setReqGroupId] = useState('');
    const [tierId, setTierId] = useState('');
    const [hullSearch, setHullSearch] = useState('');

    // Tier Form
    const [newTier, setNewTier] = useState({ name: '', order: 0, badge_class: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50', hex_color: '#EAB308' });

    // Group Member Form
    const [newMemberSkill, setNewMemberSkill] = useState('');
    const [newMemberLevel, setNewMemberLevel] = useState(5);

    useEffect(() => {
        fetchData();
        const hash = window.location.hash.replace('#', '');
        if (['assignments', 'groups', 'tiers'].includes(hash)) setView(hash);
    }, []);

    const fetchData = () => {
        apiCall('/api/management/skills/data/')
            .then(res => res.json())
            .then(data => {
                setFits(data.fits || []);
                setTiers(data.tiers || []);
                setGroups(data.groups || []);
                setRequirements(data.requirements || []);
                if (data.groups.length > 0 && !selectedGroup) {
                    // Try restore selection logic or default
                }
            });
    };

    const handleHullSearch = (q) => {
        setHullSearch(q);
        if (q.length < 3) {
            setHullSearchResults([]);
            return;
        }
        apiCall(`/api/search_hull/?q=${encodeURIComponent(q)}`)
            .then(res => res.json())
            .then(data => setHullSearchResults(data.results || []));
    };

    const addRule = () => {
        const payload = {
            target_type: targetType,
            target_id: targetId,
            req_type: reqType,
            tier_id: tierId,
            ...(reqType === 'skill' ? { skill_name: skillName, level: skillLevel } : { group_id: reqGroupId })
        };

        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/skill_req/add/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify(payload)
        }).then(res => res.json()).then(data => {
            if (data.success) {
                fetchData();
                setSkillName('');
            } else alert(data.error);
        });
    };

    const deleteRule = (id) => {
        if (!confirm("Delete rule?")) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/skill_req/delete/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ req_id: id })
        }).then(res => res.json()).then(data => {
            if (data.success) fetchData();
        });
    };

    const createGroup = () => {
        const name = prompt("Enter Group Name:");
        if (!name) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/skill_group/manage/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action: 'create', name })
        }).then(res => res.json()).then(data => {
            if (data.success) fetchData(); else alert(data.error);
        });
    };

    const deleteGroup = () => {
        if (!confirm("Delete group?")) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/skill_group/manage/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action: 'delete', group_id: selectedGroup.id })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                setSelectedGroup(null);
                fetchData();
            }
        });
    };

    const selectGroup = (group) => {
        setSelectedGroup(group);
        setGroupMembers(group.members || []); // Assuming API returns members nested or we fetch separately
        // If not nested, we might need a separate fetch. Let's assume nested for simplicity or fetch here.
        // Actually the template uses `groupsData` which is populated server side.
        // We should fetch members when selecting.
        apiCall(`/api/skill_group/${group.id}/members/`).then(r=>r.json()).then(d=>setGroupMembers(d.members||[]));
    };

    const addGroupMember = () => {
        if (!newMemberSkill) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/skill_group/member/add/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ group_id: selectedGroup.id, skill_name: newMemberSkill, level: newMemberLevel })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                setNewMemberSkill('');
                selectGroup(selectedGroup); // Refresh
                fetchData(); // Update counts
            } else alert(data.error);
        });
    };

    const removeGroupMember = (memberId) => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/skill_group/member/remove/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ member_id: memberId })
        }).then(res => res.json()).then(data => {
            if (data.success) selectGroup(selectedGroup);
        });
    };

    const createTier = () => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/skill_tier/manage/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action: 'create', ...newTier })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                setNewTier({ name: '', order: 0, badge_class: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50', hex_color: '#EAB308' });
                fetchData();
            } else alert(data.error);
        });
    };

    const deleteTier = (id) => {
        if (!confirm("Delete tier?")) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/skill_tier/manage/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action: 'delete', tier_id: id })
        }).then(res => res.json()).then(data => {
            if (data.success) fetchData();
        });
    };

    return (
        <div className="flex flex-col gap-6 h-full pb-20">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-white/5 pb-6 shrink-0">
                <div>
                    <h1 className="heading-1">Skill Management</h1>
                    <p className="text-slate-400 text-sm mt-1">Configure mandatory skills, tiers, and reusable groups.</p>
                </div>
                <div className="flex bg-black/40 p-1 rounded-lg border border-white/10">
                    {['assignments', 'groups', 'tiers'].map(t => (
                        <button 
                            key={t}
                            onClick={() => setView(t)}
                            className={clsx(
                                "px-4 py-1.5 rounded-md text-xs font-bold transition capitalize",
                                view === t ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
                            )}
                        >
                            {t}
                        </button>
                    ))}
                </div>
            </div>

            {/* Assignments View */}
            {view === 'assignments' && (
                <div className="flex flex-col gap-6">
                    <div className="glass-panel p-6">
                        <h3 className="label-text mb-4">Assign Requirement</h3>
                        <div className="flex flex-col gap-4">
                            <div className="flex flex-col md:flex-row gap-4 items-end">
                                <div className="md:w-1/4 w-full">
                                    <label className="label-text">Target Type</label>
                                    <select value={targetType} onChange={(e) => setTargetType(e.target.value)} className="select-field">
                                        <option value="fit">Specific Doctrine Fit</option>
                                        <option value="hull">Hull (Any Fit)</option>
                                    </select>
                                </div>
                                <div className="flex-grow w-full relative">
                                    <label className="label-text">Target</label>
                                    {targetType === 'fit' ? (
                                        <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="select-field">
                                            <option value="">Select Fit...</option>
                                            {fits.map(f => (
                                                <option key={f.id} value={f.id}>{f.ship_name} - {f.name}</option>
                                            ))}
                                        </select>
                                    ) : (
                                        <>
                                            <input 
                                                type="text" 
                                                value={hullSearch} 
                                                onChange={(e) => handleHullSearch(e.target.value)}
                                                className="input-field" 
                                                placeholder="e.g. Guardian..." 
                                            />
                                            {hullSearchResults.length > 0 && (
                                                <div className="absolute top-full left-0 w-full bg-slate-800 border border-slate-700 z-50 rounded-b-lg max-h-48 overflow-y-auto">
                                                    {hullSearchResults.map(h => (
                                                        <div 
                                                            key={h.id} 
                                                            className="p-2 hover:bg-slate-700 cursor-pointer text-xs text-white"
                                                            onClick={() => { setTargetId(h.id); setHullSearch(h.name); setHullSearchResults([]); }}
                                                        >
                                                            {h.name}
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                                <div className="md:w-1/4 w-full">
                                    <label className="label-text">Tier</label>
                                    <select value={tierId} onChange={(e) => setTierId(e.target.value)} className="select-field">
                                        <option value="">Minimum (Mandatory)</option>
                                        {tiers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                                    </select>
                                </div>
                            </div>

                            <div className="flex flex-col md:flex-row gap-4 items-end border-t border-white/5 pt-4">
                                <div className="md:w-1/4 w-full">
                                    <label className="label-text">Requirement Type</label>
                                    <select value={reqType} onChange={(e) => setReqType(e.target.value)} className="select-field">
                                        <option value="skill">Single Skill</option>
                                        <option value="group">Skill Group</option>
                                    </select>
                                </div>
                                {reqType === 'skill' ? (
                                    <div className="flex-grow w-full flex gap-4">
                                        <div className="flex-grow">
                                            <label className="label-text">Skill Name</label>
                                            <input type="text" value={skillName} onChange={(e) => setSkillName(e.target.value)} className="input-field" placeholder="e.g. Logistics" />
                                        </div>
                                        <div className="w-24">
                                            <label className="label-text">Level</label>
                                            <select value={skillLevel} onChange={(e) => setSkillLevel(e.target.value)} className="select-field">
                                                {[1,2,3,4,5].map(l => <option key={l} value={l}>{l}</option>)}
                                            </select>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex-grow w-full">
                                        <label className="label-text">Select Group</label>
                                        <select value={reqGroupId} onChange={(e) => setReqGroupId(e.target.value)} className="select-field">
                                            <option value="">Select Group...</option>
                                            {groups.map(g => <option key={g.id} value={g.id}>{g.name} ({g.count} skills)</option>)}
                                        </select>
                                    </div>
                                )}
                                <button onClick={addRule} className="btn-primary whitespace-nowrap">Add Rule</button>
                            </div>
                        </div>
                    </div>

                    <div className="glass-panel overflow-hidden">
                        <table className="w-full text-sm text-left text-slate-400">
                            <thead className="text-xs uppercase bg-white/5 text-slate-300 font-bold border-b border-white/5">
                                <tr>
                                    <th className="px-6 py-4">Target</th>
                                    <th className="px-6 py-4">Tier</th>
                                    <th className="px-6 py-4">Type</th>
                                    <th className="px-6 py-4">Required Skill / Group</th>
                                    <th className="px-6 py-4 text-center">Level</th>
                                    <th className="px-6 py-4 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {requirements.map(req => (
                                    <tr key={req.id} className="hover:bg-white/5 transition group">
                                        <td className="px-6 py-4 font-bold text-white">
                                            {req.fit_name ? `${req.ship_name} - ${req.fit_name}` : req.ship_name}
                                        </td>
                                        <td className="px-6 py-4">
                                            {req.tier ? (
                                                <span className="badge" style={{ backgroundColor: `${req.tier.hex}20`, color: req.tier.hex, borderColor: `${req.tier.hex}50` }}>{req.tier.name}</span>
                                            ) : (
                                                <span className="badge badge-red">MINIMUM</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {req.fit_name ? <span className="badge badge-brand">FIT</span> : <span className="badge badge-slate">HULL</span>}
                                        </td>
                                        <td className="px-6 py-4 text-slate-300">
                                            {req.group_name ? (
                                                <span className="text-blue-400 font-bold flex items-center gap-2"><span>📚</span> {req.group_name}</span>
                                            ) : req.skill_name}
                                        </td>
                                        <td className="px-6 py-4 text-center font-mono font-bold text-white">
                                            {req.group_name ? '-' : req.level}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button onClick={() => deleteRule(req.id)} className="text-slate-500 hover:text-red-400 transition">✕</button>
                                        </td>
                                    </tr>
                                ))}
                                {requirements.length === 0 && <tr><td colSpan="6" className="p-8 text-center italic">No explicit rules defined.</td></tr>}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Groups View */}
            {view === 'groups' && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
                    <div className="glass-panel p-4 flex flex-col gap-4 max-h-[600px] overflow-hidden">
                        <div className="flex justify-between items-center pb-2 border-b border-white/5">
                            <h3 className="label-text mb-0">Skill Groups</h3>
                            <button onClick={createGroup} className="btn-secondary text-[10px] py-1 px-2">+ New</button>
                        </div>
                        <div className="overflow-y-auto custom-scrollbar space-y-2 pr-1">
                            {groups.map(g => (
                                <div key={g.id} className={clsx("p-3 rounded border cursor-pointer group transition flex justify-between items-center", selectedGroup?.id === g.id ? "bg-brand-900/20 border-brand-500/50" : "bg-white/5 border-white/5 hover:border-brand-500")} onClick={() => selectGroup(g)}>
                                    <span className="font-bold text-slate-200 group-hover:text-white">{g.name}</span>
                                    <span className="badge badge-slate text-[10px]">{g.count}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className={clsx("md:col-span-2 glass-panel p-6 flex flex-col h-full", !selectedGroup && "hidden")}>
                        {selectedGroup && (
                            <>
                                <div className="flex justify-between items-start mb-6 border-b border-white/5 pb-4">
                                    <div>
                                        <h2 className="text-2xl font-bold text-white">{selectedGroup.name}</h2>
                                    </div>
                                    <button onClick={deleteGroup} className="btn-danger text-xs py-1.5 px-3">Delete Group</button>
                                </div>
                                <div className="flex gap-2 items-end mb-6">
                                    <div className="flex-grow">
                                        <label className="label-text">Add Skill to Group</label>
                                        <input type="text" value={newMemberSkill} onChange={(e) => setNewMemberSkill(e.target.value)} className="input-field" placeholder="e.g. Armor Layering" />
                                    </div>
                                    <div className="w-24">
                                        <label className="label-text">Level</label>
                                        <select value={newMemberLevel} onChange={(e) => setNewMemberLevel(e.target.value)} className="select-field">
                                            {[1,2,3,4,5].map(l => <option key={l} value={l}>{l}</option>)}
                                        </select>
                                    </div>
                                    <button onClick={addGroupMember} className="btn-primary">Add</button>
                                </div>
                                <div className="space-y-1 overflow-y-auto custom-scrollbar flex-grow bg-black/20 p-2 rounded border border-white/5 h-64">
                                    {groupMembers.map(m => (
                                        <div key={m.id} className="flex justify-between items-center p-2 bg-white/5 rounded border border-transparent hover:border-white/10 group">
                                            <span className="text-slate-300 text-xs font-bold">{m.name}</span>
                                            <div className="flex items-center gap-4">
                                                <span className="font-mono text-white text-xs">Lvl {m.level}</span>
                                                <button onClick={() => removeGroupMember(m.id)} className="text-slate-500 hover:text-red-400 px-2 transition"><X size={14} /></button>
                                            </div>
                                        </div>
                                    ))}
                                    {groupMembers.length === 0 && <div className="text-slate-500 text-xs text-center py-4">No skills in this group yet.</div>}
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* Tiers View */}
            {view === 'tiers' && (
                <div className="flex flex-col gap-6">
                    <div className="glass-panel p-6">
                        <h3 className="label-text mb-4">Create Tier</h3>
                        <div className="flex items-end gap-4">
                            <div className="flex-grow">
                                <label className="label-text">Tier Name</label>
                                <input type="text" value={newTier.name} onChange={(e) => setNewTier({...newTier, name: e.target.value})} className="input-field" placeholder="e.g. Elite" />
                            </div>
                            <div className="w-24">
                                <label className="label-text">Order</label>
                                <input type="number" value={newTier.order} onChange={(e) => setNewTier({...newTier, order: e.target.value})} className="input-field" />
                            </div>
                            <div className="flex-grow">
                                <label className="label-text">Badge Classes</label>
                                <input type="text" value={newTier.badge_class} onChange={(e) => setNewTier({...newTier, badge_class: e.target.value})} className="input-field" />
                            </div>
                            <div className="w-32">
                                <label className="label-text">Hex</label>
                                <input type="color" value={newTier.hex_color} onChange={(e) => setNewTier({...newTier, hex_color: e.target.value})} className="input-field h-10 p-1" />
                            </div>
                            <button onClick={createTier} className="btn-primary">Create</button>
                        </div>
                    </div>
                    <div className="glass-panel p-6">
                        <h3 className="label-text mb-4">Active Tiers</h3>
                        <div className="space-y-2">
                            {tiers.map(tier => (
                                <div key={tier.id} className="flex justify-between items-center p-3 bg-white/5 rounded border border-white/10">
                                    <div className="flex items-center gap-4">
                                        <span className="font-mono text-slate-500 font-bold">#{tier.order}</span>
                                        <span className={`px-3 py-1 rounded text-xs font-bold uppercase border ${tier.badge_class}`} style={{ boxShadow: `0 0 10px ${tier.hex_color}40`, borderColor: `${tier.hex_color}50` }}>{tier.name}</span>
                                    </div>
                                    <button onClick={() => deleteTier(tier.id)} className="text-red-400 hover:text-red-300">Delete</button>
                                </div>
                            ))}
                            {tiers.length === 0 && <div className="text-slate-500 italic">No tiers defined.</div>}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManagementSkills;