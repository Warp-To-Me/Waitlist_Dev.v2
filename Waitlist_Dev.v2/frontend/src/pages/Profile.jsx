import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Search, X, LogIn, AlertTriangle, ShieldAlert } from 'lucide-react';
import clsx from 'clsx';

const Profile = () => {
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('service');
    const [pilotModalOpen, setPilotModalOpen] = useState(false);
    const [pilotSearch, setPilotSearch] = useState('');
    const [serviceFilters, setServiceFilters] = useState(new Set());
    const [isRefreshing, setIsRefreshing] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        fetchProfile();
    }, []);

    const fetchProfile = () => {
        fetch('/api/profile/')
            .then(res => {
                if (res.status === 401) {
                    window.location.href = '/sso/login';
                    return null;
                }
                return res.json();
            })
            .then(data => {
                if (data) {
                    setProfile(data);
                    setLoading(false);
                }
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    };

    const handleSwitchChar = (charId) => {
        fetch(`/api/profile/switch/${charId}/`, { method: 'POST' }) // Assuming POST for switch
            .then(res => {
                if (res.ok) window.location.reload();
            });
    };

    const handleUnlink = (charId, name) => {
        if (!confirm(`Are you sure you want to unlink ${name}?`)) return;
        fetch('/api/profile/unlink/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({ character_id: charId })
        }).then(res => res.json()).then(d => {
            if (d.success) fetchProfile(); else alert(d.error);
        });
    };

    const triggerRefresh = () => {
        setIsRefreshing(true);
        fetch(`/api/profile/refresh/${profile.active_char.character_id}/`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    setTimeout(() => {
                        fetchProfile();
                        setIsRefreshing(false);
                    }, 2000); // Mock poll delay
                }
            });
    };

    const getCookie = (name) => {
        const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        if (match) return match[2];
    }

    if (loading) return <div className="p-10 text-center animate-pulse text-slate-500">Loading Pilot Data...</div>;
    if (!profile) return null;

    const { active_char, characters, esi, service_record, account_totals, is_inspection_mode } = profile;

    // Filter Logic
    const filteredLogs = (service_record?.history_logs || []).filter(log => serviceFilters.size === 0 || serviceFilters.has(log.action));
    const filteredPilots = characters.filter(c =>
        pilotSearch === '' ||
        c.character_name.toLowerCase().includes(pilotSearch.toLowerCase()) ||
        (c.corporation_name || '').toLowerCase().includes(pilotSearch.toLowerCase())
    );

    return (
        <div className="absolute inset-0 overflow-y-auto custom-scrollbar">
            <div className="container mx-auto p-4 md:p-8 relative">

                {/* Inspection Banner */}
                {is_inspection_mode && (
                    <div className="absolute top-0 left-0 w-full bg-blue-600/90 text-white text-xs font-bold px-2 py-0.5 z-50 text-center backdrop-blur">
                        READ-ONLY INSPECTION MODE
                    </div>
                )}

                {/* Header & Character Switcher */}
                <div className="glass-panel mb-8 relative overflow-hidden flex flex-col lg:flex-row">

                    {/* Left: Character List */}
                    <div className="w-full lg:w-auto lg:flex-1 lg:min-w-0 p-6 border-b lg:border-b-0 lg:border-r border-white/5 relative flex flex-col justify-center">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                👥 Pilots <span className="badge badge-slate">{characters.length}</span>
                            </h2>
                            {!is_inspection_mode && (
                                <a href="/auth/add_alt/" className="btn-primary text-xs px-3 py-1.5 shadow-lg shadow-brand-500/20 inline-flex items-center gap-2">
                                    <PlusIcon /> Link Alt
                                </a>
                            )}
                        </div>

                        <div className="flex flex-wrap gap-4">
                            {/* Main Character */}
                            {characters.filter(c => c.is_main).map(char => (
                                <CharacterCard
                                    key={char.character_id}
                                    char={char}
                                    isActive={char.character_id === active_char.character_id}
                                    onClick={() => handleSwitchChar(char.character_id)}
                                    isInspection={is_inspection_mode}
                                />
                            ))}
                            {/* Active Alt (if Main not active) */}
                            {!active_char.is_main && (
                                <CharacterCard
                                    char={active_char}
                                    isActive={true}
                                    isInspection={is_inspection_mode}
                                />
                            )}
                        </div>

                        {/* Recent Alts */}
                        {characters.length > 1 && (
                            <div className="flex flex-wrap gap-2 items-center pt-2 border-t border-white/5 mt-4">
                                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider mr-1">Recent</span>
                                {characters.filter(c => !c.is_main && c.character_id !== active_char.character_id).slice(0, 8).map(char => (
                                    <button
                                        key={char.character_id}
                                        onClick={() => handleSwitchChar(char.character_id)}
                                        className="flex items-center gap-2 p-1 pr-3 rounded-lg border border-white/5 bg-white/5 hover:bg-white/10 hover:border-white/20 transition group"
                                        title={char.character_name}
                                    >
                                        <img src={`https://images.evetech.net/characters/${char.character_id}/portrait?size=32`} className="w-6 h-6 rounded border border-slate-600 group-hover:border-slate-400 transition" alt="" />
                                        <div className="text-xs font-bold text-slate-400 group-hover:text-white truncate max-w-[80px]">{char.character_name}</div>
                                    </button>
                                ))}
                                {characters.length > 5 && (
                                    <button onClick={() => setPilotModalOpen(true)} className="ml-auto btn-secondary text-[10px] px-2 py-1 h-8 border-white/10 hover:border-white/30 text-slate-400 hover:text-white flex items-center gap-1">
                                        <Search size={12} /> All Pilots
                                    </button>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Right: Account Totals */}
                    <div className="w-full lg:w-80 flex-shrink-0 p-6 bg-black/20 flex flex-col justify-center border-t lg:border-t-0 border-white/5">
                        <h3 className="label-text mb-4 pb-2 border-b border-white/5 flex items-center gap-2">
                            <span>📊</span> Account Aggregate
                        </h3>
                        <div className="space-y-4">
                            <StatRow label="Total Pilots" value={characters.length} badge />
                            <StatRow label="Total Skillpoints" value={account_totals.sp?.toLocaleString()} highlight="brand" />
                            <StatRow label="Total Wealth" value={`${account_totals.wallet?.toLocaleString()} ISK`} highlight="green" obfuscated={profile.obfuscate_financials} />
                            <StatRow label="Concord LP" value={`${account_totals.lp?.toLocaleString()} LP`} highlight="purple" obfuscated={profile.obfuscate_financials} />
                        </div>
                    </div>
                </div>

                {/* Main Profile View */}
                <div className="glass-panel mb-8 relative overflow-hidden flex flex-col lg:flex-row">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-brand-500 via-brand-400 to-brand-600"></div>

                    {/* Left: Active Char Stats */}
                    <div className="p-6 flex-grow border-b lg:border-b-0 lg:border-r border-white/5">
                        <div className="flex flex-col md:flex-row gap-6 h-full items-start">
                            <div className="flex flex-col items-center md:items-start min-w-[140px]">
                                <img src={`https://images.evetech.net/characters/${active_char.character_id}/portrait?size=128`} className="w-28 h-28 rounded-lg border-2 border-white/10 shadow-2xl mb-2" alt="" />
                                <h1 className="text-xl font-bold text-white text-center md:text-left leading-tight">{active_char.character_name}</h1>
                                <div className="text-[10px] text-slate-500 mt-1 mb-2 flex items-center gap-1">
                                    Updated: {isRefreshing ? <span className="animate-pulse text-brand-400">Syncing...</span> : new Date(active_char.last_updated).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                                </div>
                                {!is_inspection_mode && (
                                    <button onClick={triggerRefresh} disabled={isRefreshing} className="text-[10px] btn-secondary py-1 px-2">
                                        <RefreshCw size={10} className={isRefreshing ? "animate-spin" : ""} /> Refresh
                                    </button>
                                )}
                            </div>

                            <div className="flex-grow grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-sm">
                                <StatsBox label="Corporation" value={active_char.corporation_name || "Unknown"} />
                                <StatsBox label="Alliance" value={active_char.alliance_name || "-"} />
                                <StatsBox label="Wallet" value={`${active_char.wallet_balance?.toLocaleString()} ISK`} color="text-green-400" font="mono" obfuscated={profile.obfuscate_financials} />
                                <StatsBox label="CONCORD LP" value={`${active_char.concord_lp?.toLocaleString()} LP`} color="text-purple-400" font="mono" obfuscated={profile.obfuscate_financials} />
                                <div className="col-span-1 sm:col-span-2 bg-white/5 p-3 rounded-lg border border-white/5 flex items-center justify-between gap-4">
                                    <div>
                                        <div className="label-text mb-0">Skill Points</div>
                                        <div className="text-brand-400 font-mono text-lg font-bold leading-tight">{active_char.total_sp?.toLocaleString() || 0} SP</div>
                                    </div>
                                    <div className="flex items-center gap-3 text-right">
                                        <div className="overflow-hidden">
                                            <div className="label-text mb-0">Active Ship</div>
                                            <div className="text-white font-medium truncate text-xs">{active_char.current_ship_name || "Unknown"}</div>
                                            <div className="text-[10px] text-slate-400 truncate">{active_char.ship_type_name}</div>
                                        </div>
                                        {active_char.current_ship_type_id && (
                                            <img src={`https://images.evetech.net/types/${active_char.current_ship_type_id}/icon?size=32`} className="w-10 h-10 rounded border border-white/10" alt="" />
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Right: Implants */}
                    <div className="p-4 lg:w-72 bg-black/20 flex flex-col border-l border-white/5">
                        <div className="flex justify-between items-center mb-3">
                            <h3 className="label-text mb-0 flex items-center gap-2">🧠 Implants</h3>
                            <span className="text-[10px] text-slate-500">{esi.implants.length} Active</span>
                        </div>
                        <div className="grid grid-cols-2 gap-1">
                            {esi.implants.length > 0 ? esi.implants.map(imp => (
                                <div key={imp.id} className="flex items-center gap-1.5 bg-white/5 px-1.5 py-1 rounded border border-white/5 overflow-hidden hover:border-white/20 transition group" title={imp.name}>
                                    <img src={`https://images.evetech.net/types/${imp.id}/icon?size=32`} className="w-4 h-4 rounded-sm border border-white/10 opacity-80 group-hover:opacity-100 flex-shrink-0" alt="" />
                                    <span className="text-[10px] text-slate-400 group-hover:text-slate-200 truncate leading-none">{imp.name}</span>
                                </div>
                            )) : (
                                <div className="col-span-2 text-slate-600 text-xs italic text-center py-2 bg-white/5 rounded border border-white/5 border-dashed">No implants.</div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Tabs */}
                <div className="mb-6 border-b border-white/10">
                    <nav className="flex space-x-8 overflow-x-auto">
                        {['service', 'skills', 'queue', 'history', 'skill-history'].map(tab => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={clsx(
                                    "border-b-2 py-4 px-1 font-bold text-sm transition capitalize whitespace-nowrap",
                                    activeTab === tab ? "border-brand-500 text-brand-500" : "border-transparent text-slate-400 hover:text-white"
                                )}
                            >
                                {tab.replace('-', ' ')}
                            </button>
                        ))}
                    </nav>
                </div>

                {/* Tab Content */}
                <div className="min-h-[400px]">
                    {activeTab === 'service' && (
                        <div className="flex flex-col lg:flex-row gap-8">
                            <div className="lg:w-80 space-y-6 flex-shrink-0">
                                <div className="glass-panel p-6 bg-gradient-to-br from-slate-900 to-black/50 border-brand-500/20">
                                    <h3 className="label-text text-brand-500 flex items-center gap-2">
                                        Total Time in Fleet
                                        {service_record.active_session_start && <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.8)]"></span>}
                                    </h3>
                                    <div className="text-4xl font-mono font-bold text-white mt-2">
                                        {service_record.total_hours}<span className="text-sm text-slate-500 ml-1">hrs</span>
                                    </div>
                                    <div className="w-full bg-dark-900/50 h-1 mt-4 rounded-full overflow-hidden">
                                        <div className="bg-brand-500 h-full w-full opacity-80"></div>
                                    </div>
                                </div>
                                <div className="glass-panel p-6">
                                    <h3 className="label-text mb-4">Hull Breakdown</h3>
                                    <div className="space-y-3">
                                        {service_record.hull_breakdown.map(([hull, duration]) => (
                                            <div key={hull} className="group">
                                                <div className="flex justify-between items-end mb-1">
                                                    <span className="text-sm font-bold text-slate-300 group-hover:text-white transition">{hull}</span>
                                                    <span className="text-xs font-mono text-slate-500">{(duration/3600).toFixed(1)}h</span>
                                                </div>
                                                <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                                                    <div className="bg-blue-500 h-full rounded-full opacity-60 group-hover:opacity-100 transition" style={{width: `${(duration / service_record.total_seconds) * 100}%`}}></div>
                                                </div>
                                            </div>
                                        ))}
                                        {service_record.hull_breakdown.length === 0 && <p className="text-xs text-slate-500 italic">No hull data recorded.</p>}
                                    </div>
                                </div>
                            </div>
                            <div className="flex-grow glass-panel overflow-hidden flex flex-col">
                                <div className="p-4 bg-white/5 border-b border-white/5 flex justify-between items-center">
                                    <h3 className="font-bold text-white">Recent Activity</h3>
                                    <div className="flex flex-wrap gap-1.5">
                                        <button onClick={() => setServiceFilters(new Set())} className="p-1 rounded border border-red-500/30 text-red-400 hover:bg-red-500/20"><X size={12} /></button>
                                        {['x_up', 'approved', 'invited', 'esi_join', 'left_fleet', 'denied'].map(action => (
                                            <button
                                                key={action}
                                                onClick={() => {
                                                    const next = new Set(serviceFilters);
                                                    if(next.has(action)) next.delete(action); else next.add(action);
                                                    setServiceFilters(next);
                                                }}
                                                className={clsx("px-2 py-0.5 rounded border text-[9px] uppercase font-bold transition", serviceFilters.has(action) ? "bg-brand-500 text-white border-brand-400" : "bg-white/5 text-slate-400 border-white/10 hover:text-white")}
                                            >
                                                {action.replace('_', ' ')}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <div className="overflow-y-auto custom-scrollbar max-h-[600px] p-4 space-y-3">
                                    {filteredLogs.map((log, idx) => (
                                        <div key={idx} className="flex gap-4 group">
                                            <div className="w-16 pt-1 text-right flex-shrink-0">
                                                <div className="text-xs font-bold text-slate-400">{new Date(log.timestamp).toLocaleDateString([], {month:'short', day:'numeric'})}</div>
                                                <div className="text-[10px] text-slate-600 font-mono">{new Date(log.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
                                            </div>
                                            <div className="flex flex-col items-center relative">
                                                <div className={clsx("w-2 h-2 rounded-full mt-1.5 z-10", getActionColor(log.action))}></div>
                                                {idx !== filteredLogs.length - 1 && <div className="w-px bg-white/5 flex-grow h-full absolute top-2 bottom-0"></div>}
                                            </div>
                                            <div className="flex-grow pb-2">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs font-bold text-slate-200">{log.action.toUpperCase().replace('_', ' ')}</span>
                                                    <span className="text-[10px] bg-white/5 px-1.5 py-0.5 rounded text-slate-500 border border-white/5">{log.fleet_name || "SYSTEM"}</span>
                                                </div>
                                                <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2 flex-wrap">
                                                    {log.ship_name && <span className="text-slate-400">🚀 {log.ship_name}</span>}
                                                    {log.details && <span className="italic">| {log.details}</span>}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                    {filteredLogs.length === 0 && <div className="text-center py-12 text-slate-500 italic">No history found.</div>}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Other Tabs Placeholder Logic (Skills, Queue, History) */}
                    {/* Implementing full skills grid rendering would replicate the template logic loop */}
                    {activeTab === 'skills' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {Object.entries(profile.grouped_skills || {}).map(([group, skills]) => (
                                <div key={group} className="glass-panel overflow-hidden border-white/5">
                                    <div className="bg-white/5 px-4 py-2 border-b border-white/5 flex justify-between items-center">
                                        <h3 className="font-bold text-slate-200 text-sm">{group}</h3>
                                        <span className="badge badge-slate">{skills.length}</span>
                                    </div>
                                    <div className="p-2 space-y-1">
                                        {skills.map(skill => (
                                            <div key={skill.id} className="flex justify-between items-center px-2 py-1.5 hover:bg-white/5 rounded group">
                                                <span className="text-sm text-slate-300 group-hover:text-white transition">{skill.name}</span>
                                                <div className="flex gap-[2px]">
                                                    {[1,2,3,4,5].map(lvl => (
                                                        <div key={lvl} className={clsx("w-3 h-3 rounded-sm border border-slate-600/50", lvl <= skill.level ? "bg-slate-200 shadow-[0_0_5px_rgba(255,255,255,0.5)]" : "bg-dark-900/50")}></div>
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                            {Object.keys(profile.grouped_skills || {}).length === 0 && <div className="col-span-full text-center py-12 text-slate-500 italic">No skills loaded.</div>}
                        </div>
                    )}
                </div>
            </div>

            {/* Pilot Modal */}
            {pilotModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dark-950/90 backdrop-blur-sm" onClick={() => setPilotModalOpen(false)}>
                    <div className="relative transform rounded-xl bg-slate-900 border border-white/10 shadow-2xl w-full max-w-4xl flex flex-col max-h-[85vh]" onClick={e => e.stopPropagation()}>
                        <div className="glass-header px-6 py-4 flex flex-col gap-4 border-b border-white/5">
                            <div className="flex justify-between items-center">
                                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                                    <span>👥</span> Pilot Directory <span className="badge badge-slate">{characters.length}</span>
                                </h3>
                                <button onClick={() => setPilotModalOpen(false)} className="text-slate-400 hover:text-white text-xl leading-none">&times;</button>
                            </div>
                            <div className="relative w-full">
                                <Search className="absolute left-3 top-3 w-5 h-5 text-slate-500" />
                                <input
                                    type="text"
                                    value={pilotSearch}
                                    onChange={(e) => setPilotSearch(e.target.value)}
                                    className="w-full bg-dark-950 border border-white/10 rounded-lg py-3 pl-10 text-white placeholder-slate-500 focus:border-brand-500 outline-none"
                                    placeholder="Filter pilots..."
                                />
                            </div>
                        </div>
                        <div className="flex-grow overflow-y-auto custom-scrollbar p-6 bg-dark-900/50">
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                {filteredPilots.map(char => (
                                    <div
                                        key={char.character_id}
                                        onClick={() => handleSwitchChar(char.character_id)}
                                        className="flex items-center gap-3 p-3 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 hover:border-brand-500/30 transition cursor-pointer group"
                                    >
                                        <div className="relative">
                                            <img src={`https://images.evetech.net/characters/${char.character_id}/portrait?size=64`} className="w-12 h-12 rounded-lg border border-white/10 bg-black group-hover:scale-105 transition" alt="" />
                                            {char.character_id === active_char.character_id && <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 border-2 border-slate-900 rounded-full"></div>}
                                        </div>
                                        <div className="flex-grow min-w-0">
                                            <div className="flex justify-between items-start">
                                                <h4 className="font-bold text-slate-200 group-hover:text-white truncate">{char.character_name}</h4>
                                                {char.is_main && <span className="text-[9px] font-bold text-brand-400 bg-brand-900/20 px-1.5 py-0.5 rounded border border-brand-500/20 uppercase">Main</span>}
                                            </div>
                                            <div className="text-xs text-slate-500 truncate mt-0.5">{char.corporation_name || "Unknown Corp"}</div>
                                            <div className="text-[10px] text-slate-600 font-mono mt-1">{(char.total_sp || 0).toLocaleString()} SP</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {filteredPilots.length === 0 && <div className="text-center py-12 text-slate-500 italic">No pilots found.</div>}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// Sub-components for cleaner code
const CharacterCard = ({ char, isActive, isInspection, onClick }) => (
    <div
        onClick={!isActive && !isInspection ? onClick : undefined}
        className={clsx(
            "relative group p-1.5 rounded-xl border flex items-center gap-3 pr-5 min-w-[200px] transition",
            isActive
                ? "bg-gradient-to-br from-brand-500/20 to-brand-900/40 border-brand-500/50 shadow-[0_0_15px_rgba(245,158,11,0.15)] cursor-default"
                : "bg-white/5 border-white/10 hover:bg-brand-500/10 hover:border-brand-500/50 cursor-pointer"
        )}
    >
        <img src={`https://images.evetech.net/characters/${char.character_id}/portrait?size=64`} className="w-12 h-12 rounded-lg border border-brand-400/50 bg-dark-900" alt="" />
        <div>
            <div className="text-sm font-bold text-white leading-none">{char.character_name}</div>
            <div className="flex gap-2 mt-1">
                <span className={clsx("text-[9px] font-bold px-1.5 rounded uppercase tracking-wider", char.is_main ? "bg-brand-500 text-white" : "bg-slate-600 text-slate-300")}>
                    {char.is_main ? "Main" : "Alt"}
                </span>
                {isActive && <span className="text-[9px] font-bold text-green-400 uppercase tracking-wider flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span> Active</span>}
                {!isActive && <span className="text-[9px] font-bold text-slate-500 group-hover:text-brand-300 uppercase tracking-wider transition">Switch</span>}
            </div>
        </div>
    </div>
);

const StatRow = ({ label, value, badge, highlight, obfuscated }) => (
    <div className="flex justify-between items-center group">
        <span className="text-slate-400 text-sm group-hover:text-white transition">{label}</span>
        {badge ? (
            <span className="badge badge-slate">{value}</span>
        ) : (
            <span className={clsx("font-mono font-bold", highlight === "brand" ? "text-brand-400" : highlight === "green" ? "text-green-400" : highlight === "purple" ? "text-purple-400" : "text-white")}>
                {obfuscated ? <span className="blur-sm select-none">******</span> : value}
            </span>
        )}
    </div>
);

const StatsBox = ({ label, value, color = "text-slate-200", font = "sans", obfuscated }) => (
    <div className="bg-white/5 p-3 rounded-lg border border-white/5 flex flex-col justify-center space-y-1">
        <div>
            <div className="label-text mb-0">{label}</div>
            <div className={clsx("font-medium truncate leading-tight", color, font === "mono" && "font-mono")}>
                {obfuscated ? <span className="blur-sm select-none">******</span> : value}
            </div>
        </div>
    </div>
);

const PlusIcon = () => <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"/></svg>;

const getActionColor = (action) => {
    switch(action) {
        case 'x_up': return 'bg-brand-500';
        case 'approved': return 'bg-green-500';
        case 'esi_join': return 'bg-blue-500';
        case 'left_fleet': return 'bg-red-500';
        case 'denied': return 'bg-red-600';
        default: return 'bg-slate-600';
    }
}

export default Profile;