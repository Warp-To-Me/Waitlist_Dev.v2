import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, X, Copy, RotateCcw } from 'lucide-react';
import clsx from 'clsx';

const ManagementHistory = () => {
    const { token } = useParams();
    const [fleet, setFleet] = useState(null);
    const [stats, setStats] = useState({ xups: 0, pilots: 0 });
    const [logs, setLogs] = useState([]);
    const [activeFilters, setActiveFilters] = useState(new Set());
    const [modalOpen, setModalOpen] = useState(false);
    const [modalData, setModalData] = useState(null);

    const filters = [
        { id: 'x_up', label: 'X-Up', icon: '✋' },
        { id: 'approved', label: 'Approved', icon: '✔' },
        { id: 'invited', label: 'Invited', icon: '📩' },
        { id: 'esi_join', label: 'Detected', icon: '🔗' },
        { id: 'left_waitlist', label: 'Left WL', icon: '🚪' },
        { id: 'left_fleet', label: 'Left Fleet', icon: '💨' },
        { id: 'fit_update', label: 'Update', icon: '🔄' },
        { id: 'ship_change', label: 'Reship', icon: '🚢' },
        { id: 'moved', label: 'Moved', icon: '↔' },
        { id: 'promoted', label: 'Promoted', icon: '⬆' },
        { id: 'demoted', label: 'Demoted', icon: '⬇' },
        { id: 'kicked', label: 'Kicked', icon: '🥾' },
        { id: 'denied', label: 'Denied', icon: '✖' },
    ];

    useEffect(() => {
        fetch(`/api/management/fleets/${token}/history/`)
            .then(res => res.json())
            .then(data => {
                setFleet(data.fleet);
                setStats(data.stats);
                setLogs(data.logs);
            });
    }, [token]);

    const toggleFilter = (id) => {
        const newFilters = new Set(activeFilters);
        if (newFilters.has(id)) newFilters.delete(id);
        else newFilters.add(id);
        setActiveFilters(newFilters);
    };

    const clearFilters = () => setActiveFilters(new Set());

    const openHistoryFit = (logId) => {
        setModalOpen(true);
        setModalData(null); // Loading state
        fetch(`/fleet/history/api/${logId}/`) // Assuming this endpoint works and returns JSON
            .then(res => res.json())
            .then(data => setModalData(data))
            .catch(() => setModalData({ error: "Error loading data" }));
    };

    const getActionColor = (action) => {
        switch(action) {
            case 'x_up': return 'bg-brand-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]';
            case 'approved': return 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]';
            case 'esi_join': return 'bg-blue-500';
            case 'left_waitlist': return 'bg-red-500';
            case 'denied': return 'bg-red-600';
            default: return 'bg-slate-600';
        }
    };

    const getStatusStyles = (status) => {
        switch (status) {
            case 'MATCH': return { border: 'border-transparent', bg: 'bg-transparent', icon: null, textClass: 'text-slate-400' };
            case 'UPGRADE': return { border: 'border-green-500/50', bg: 'bg-green-500/10', icon: 'UPGRADE', textClass: 'text-green-400' };
            case 'SIDEGRADE': return { border: 'border-blue-500/50', bg: 'bg-blue-500/10', icon: 'SIDEGRADE', textClass: 'text-blue-400' };
            case 'DOWNGRADE': return { border: 'border-amber-500/50', bg: 'bg-amber-500/10', icon: '⚠️', textClass: 'text-amber-400' };
            case 'MISSING': return { border: 'border-red-500/50', bg: 'bg-red-500/10', icon: 'MISSING', textClass: 'text-red-400' };
            case 'EXTRA': return { border: 'border-purple-500/50', bg: 'bg-purple-500/10', icon: 'EXTRA', textClass: 'text-purple-400' };
            default: return { border: 'border-white/10', bg: 'bg-transparent', icon: '?', textClass: 'text-slate-500' };
        }
    };

    if (!fleet) return <div className="p-12 text-center">Loading History...</div>;

    const filteredLogs = logs.filter(log => activeFilters.size === 0 || activeFilters.has(log.action));

    return (
        <div className="flex flex-col h-[calc(100vh-8rem)] bg-dark-950 overflow-hidden relative rounded-xl border border-white/5 shadow-2xl">
            {/* Header */}
            <div className="glass-header px-6 py-4 flex justify-between items-center shrink-0 z-40 bg-slate-900/90 backdrop-blur-md shadow-lg relative border-b border-white/10">
                <div className="flex items-center gap-4">
                    <Link to="/management/fleets" className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-2 group">
                        <ArrowLeft size={12} className="group-hover:-translate-x-1 transition" /> Fleets
                    </Link>
                    <div className="h-6 w-px bg-white/10"></div>
                    <div>
                        <h1 className="text-xl font-bold text-white tracking-tight">{fleet.name} <span className="text-slate-500 font-normal">History Log</span></h1>
                        <p className="text-xs text-slate-400 mt-0.5">Comprehensive audit trail of all fleet events.</p>
                    </div>
                </div>
                <div className="flex gap-4">
                    <div className="px-3 py-1 bg-white/5 border border-white/5 rounded-full flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-brand-500"></span>
                        <span className="text-xs text-slate-400 uppercase font-bold tracking-wider">X-Ups</span>
                        <span className="text-sm font-bold text-white font-mono">{stats.xups}</span>
                    </div>
                    <div className="px-3 py-1 bg-white/5 border border-white/5 rounded-full flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                        <span className="text-xs text-slate-400 uppercase font-bold tracking-wider">Unique Pilots</span>
                        <span className="text-sm font-bold text-white font-mono">{stats.pilots}</span>
                    </div>
                    <Link to={`/fleet/${fleet.join_token}`} className="btn-primary text-xs py-1 px-3 shadow-brand-500/20">
                        Open Board ↗
                    </Link>
                </div>
            </div>

            {/* Filters */}
            <div className="px-6 py-3 border-b border-white/5 bg-slate-900/50 backdrop-blur-md flex-shrink-0 flex flex-wrap gap-2 items-center relative z-30 overflow-x-auto no-scrollbar shadow-sm">
                <button onClick={clearFilters} className="p-1.5 rounded-md border border-red-500/30 text-red-400 hover:bg-red-500/20 transition mr-2" title="Clear Filters">
                    <RotateCcw size={16} />
                </button>
                {filters.map(f => (
                    <button
                        key={f.id}
                        onClick={() => toggleFilter(f.id)}
                        className={clsx(
                            "flex items-center gap-1.5 px-2.5 py-1 rounded border text-[10px] uppercase font-bold transition select-none",
                            activeFilters.has(f.id)
                                ? "bg-brand-500 text-white border-brand-400"
                                : "bg-white/5 text-slate-400 border-white/10 hover:text-white hover:border-slate-500"
                        )}
                    >
                        <span>{f.icon}</span> {f.label}
                    </button>
                ))}
            </div>

            {/* Timeline */}
            <div className="flex-grow overflow-y-auto custom-scrollbar p-6 relative z-0 bg-dark-950/50">
                <div className="max-w-5xl mx-auto space-y-4">
                    {filteredLogs.map((log, index) => (
                        <div key={log.id} className="flex gap-4 group">
                            <div className="w-24 pt-3 text-right flex-shrink-0">
                                <div className="text-xs font-mono font-bold text-slate-400">{new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</div>
                                <div className="text-[10px] text-slate-600">{new Date(log.timestamp).toLocaleDateString([], {month:'short', day:'numeric'})}</div>
                            </div>
                            <div className="flex flex-col items-center relative">
                                <div className={`w-2 h-2 rounded-full mt-4 z-10 ${getActionColor(log.action)}`}></div>
                                {index !== filteredLogs.length - 1 && <div className="w-px bg-white/10 flex-grow h-full absolute top-5 bottom-0"></div>}
                            </div>
                            <div className="flex-grow pb-4">
                                <div className="glass-panel p-3 border border-white/5 hover:border-white/10 transition flex justify-between items-center bg-slate-900/80">
                                    <div className="flex items-center gap-4">
                                        <img src={`https://images.evetech.net/characters/${log.character_id}/portrait?size=64`} className="w-10 h-10 rounded border border-white/10 opacity-80 group-hover:opacity-100 transition" alt="" />
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm font-bold text-slate-200">{log.character_name}</span>
                                                {/* Badge logic simplified for brevity, assume maps to label */}
                                                <span className="badge badge-slate text-[9px]">{log.action.toUpperCase().replace('_', ' ')}</span>
                                            </div>
                                            <div className="text-xs text-slate-500 mt-0.5 flex gap-2 items-center">
                                                {log.ship_name && (
                                                    <span className="flex items-center gap-1">
                                                        <span>🚀</span> {log.ship_name}
                                                    </span>
                                                )}
                                                {log.details && (
                                                    <>
                                                        <span className="opacity-50">|</span>
                                                        <span className="italic text-slate-400">{log.details}</span>
                                                    </>
                                                )}
                                                {log.fit_eft && (
                                                    <>
                                                        <span className="opacity-50">|</span>
                                                        <button onClick={() => openHistoryFit(log.id)} className="text-brand-400 hover:text-brand-300 underline font-bold flex items-center gap-1">
                                                            <span>🔍</span> View Fit
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    {log.actor_name && log.actor_name !== log.character_name && (
                                        <div className="text-right">
                                            <span className="text-[10px] text-slate-500 uppercase tracking-wider block">By</span>
                                            <span className="text-xs font-bold text-slate-300">{log.actor_name}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                    {filteredLogs.length === 0 && <div className="p-12 text-center text-slate-500 italic">No history recorded or matching filter.</div>}
                </div>
            </div>

            {/* Modal */}
            {modalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dark-950/80 backdrop-blur-sm">
                    <div className="relative transform rounded-xl bg-slate-900 border border-white/10 shadow-2xl sm:w-full sm:max-w-5xl max-h-[90vh] flex flex-col w-full h-full">
                        <div className="glass-header px-6 py-4 flex justify-between items-center shrink-0">
                            {modalData && !modalData.error ? (
                                <div className="flex items-center gap-4">
                                    <img src={`https://images.evetech.net/types/${modalData.hull_id}/icon?size=64`} className="w-14 h-14 rounded-lg border border-white/10 bg-dark-900 shadow-lg" alt="" />
                                    <div>
                                        <h3 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                                            <span className="text-brand-500">{modalData.character_name}</span>
                                            <span className="text-slate-600 text-lg">vs.</span>
                                            <span className="text-slate-300">{modalData.fit_name || "Historical Fit"}</span>
                                        </h3>
                                        <p className="text-sm text-slate-400 font-mono mt-0.5">{modalData.ship_name} ({modalData.corp_name})</p>
                                    </div>
                                </div>
                            ) : (
                                <h3>Loading...</h3>
                            )}
                            <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-white transition p-2 hover:bg-white/5 rounded-full">
                                <X size={24} />
                            </button>
                        </div>

                        <div className="px-6 py-6 grid grid-cols-1 md:grid-cols-3 gap-8 overflow-hidden h-full bg-dark-950">
                            {modalData && !modalData.error ? (
                                <>
                                    <div className="md:col-span-1 flex flex-col h-full overflow-hidden">
                                        <div className="glass-panel p-4 mb-4 flex-grow overflow-y-auto custom-scrollbar bg-black/30 border-white/5">
                                            <pre className="text-[10px] text-slate-400 font-mono whitespace-pre-wrap break-all select-all">{modalData.raw_eft}</pre>
                                        </div>
                                        <button onClick={() => navigator.clipboard.writeText(modalData.raw_eft)} className="btn-secondary w-full text-xs py-2 shrink-0">
                                            <Copy size={14} /> Copy to Clipboard
                                        </button>
                                    </div>
                                    <div className="md:col-span-2 glass-panel p-4 overflow-y-auto custom-scrollbar border-white/5 bg-slate-900/50">
                                        {modalData.slots?.map((group, idx) => (
                                            <div key={idx} className="mb-2">
                                                <div className="flex items-center gap-3 mb-1 border-b border-white/5 pb-1">
                                                    <h5 className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">{group.name}</h5>
                                                    {group.is_hardpoint && <span className="text-[9px] text-slate-600 font-mono bg-white/5 px-1.5 rounded">({group.used} / {group.total})</span>}
                                                </div>
                                                <div className="space-y-1">
                                                    {group.modules.map((mod, mIdx) => {
                                                        const styles = getStatusStyles(mod.status);
                                                        const bgClass = mIdx % 2 === 0 ? 'bg-white/5' : 'bg-transparent';
                                                        const finalBg = mod.status === 'MATCH' ? bgClass : styles.bg;
                                                        return (
                                                            <div key={mIdx} className={`flex items-center gap-2 px-1.5 py-0.5 rounded border ${styles.border} ${finalBg} min-h-[2rem]`}>
                                                                <img src={`https://images.evetech.net/types/${mod.id}/icon?size=32`} className="w-6 h-6 rounded border border-black/50 shadow-inner flex-shrink-0" alt="" />
                                                                <div className="flex-grow min-w-0">
                                                                    <div className="flex justify-between items-center">
                                                                        <span className="text-xs font-bold text-slate-200 truncate">{mod.name}</span>
                                                                        {styles.icon && <span className={`text-[10px] ${styles.textClass}`}>{styles.icon}</span>}
                                                                    </div>
                                                                </div>
                                                                {mod.quantity > 1 && <span className="text-[10px] text-brand-400 font-mono px-1.5 bg-brand-900/20 rounded border border-brand-500/30">x{mod.quantity}</span>}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                <div className="col-span-3 text-center text-slate-500">
                                    {modalData?.error || "Loading..."}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManagementHistory;