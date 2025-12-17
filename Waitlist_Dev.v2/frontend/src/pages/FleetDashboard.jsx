import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { Shield, Crosshair, Zap, Anchor, Clock, Settings, Scroll, Plus } from 'lucide-react';
import clsx from 'clsx';
import { 
    setFleetData, setFleetError, selectFleetData, selectFleetColumns, 
    selectFleetPermissions, selectFleetLoading, selectFleetError, selectConnectionStatus 
} from '../store/slices/fleetSlice';
import { wsConnect, wsDisconnect } from '../store/middleware/socketMiddleware';

const FleetDashboard = () => {
    const { token } = useParams();
    const dispatch = useDispatch();
    const navigate = useNavigate();

    // Redux State
    const fleet = useSelector(selectFleetData);
    const columns = useSelector(selectFleetColumns);
    const permissions = useSelector(selectFleetPermissions);
    const loading = useSelector(selectFleetLoading);
    const error = useSelector(selectFleetError);
    const connectionStatus = useSelector(selectConnectionStatus);

    const [xupModalOpen, setXupModalOpen] = useState(false);

    // Initial Fetch & WebSocket Connect
    useEffect(() => {
        // 1. Initial Fetch to get state quickly
        fetch(`/api/fleet/${token}/dashboard/`)
            .then(res => {
                if (res.status === 404) throw new Error("Fleet not found or you do not have access.");
                if (!res.ok) throw new Error("Failed to load fleet data.");
                return res.json();
            })
            .then(data => {
                dispatch(setFleetData(data));
                
                // 2. Connect WebSocket after we know fleet exists
                // Use the token or ID for the channel path
                // Assuming backend expects /ws/fleet/<id>/ or <token>/
                // Using token here as per URL params
                dispatch(wsConnect(`/ws/fleet/${token}/`, 'fleet'));
            })
            .catch(err => {
                console.error(err);
                dispatch(setFleetError(err.message));
            });

        // Cleanup: Disconnect WS when component unmounts
        return () => {
            dispatch(wsDisconnect('fleet'));
        };
    }, [token, dispatch]);

    const handleXup = (hullId) => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch(`/api/fleet/${token}/xup/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ hull_id: hullId }) // Assuming simplified XUP for now
        }).then(res => res.json()).then(d => {
            if (d.success) setXupModalOpen(false); else alert(d.error);
        });
    };

    if (loading) return (
        <div className="absolute inset-0 flex items-center justify-center bg-dark-950">
            <div className="text-center animate-pulse">
                <div className="text-4xl mb-4">📡</div>
                <div className="text-slate-400 font-mono text-sm">Establishing Uplink...</div>
            </div>
        </div>
    );

    if (error) return (
        <div className="absolute inset-0 flex items-center justify-center bg-dark-950">
            <div className="text-center">
                <div className="text-4xl mb-4 text-red-500">⚠</div>
                <h2 className="text-xl font-bold text-white">Connection Lost</h2>
                <p className="text-slate-500 mt-2">{error}</p>
                <Link to="/" className="btn-secondary mt-6 inline-flex">Return to Landing</Link>
            </div>
        </div>
    );

    // If data loaded but fields missing, show safe fallback
    if (!fleet) return null;

    return (
        <div className="absolute inset-0 flex flex-col overflow-hidden bg-dark-950 opacity-0 animate-fade-in" style={{opacity: 1}}> {/* Forced opacity 1 for React rendering */}
            
            {/* Header Bar */}
            <div className="glass-header p-4 relative flex justify-center items-center z-20 shrink-0 min-h-[4rem]">
                
                {/* Left Actions (FC) */}
                {permissions.is_fc && (
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 hidden md:flex items-center gap-2">
                        <Link to={`/management/fleets/${token}/history`} className="btn-secondary py-1.5 px-3 text-xs gap-2 shadow-lg">
                            <Scroll size={14} /> History Log
                        </Link>
                        <Link to={`/management/fleets/${token}/settings`} className="btn-secondary py-1.5 px-3 text-xs gap-2 shadow-lg border-brand-500/30 text-brand-400 hover:bg-brand-500/10">
                            <Settings size={14} /> Manage Fleet
                        </Link>
                    </div>
                )}

                {/* Center Title */}
                <div className="flex items-center gap-6">
                    <div className="bg-brand-500/10 p-2.5 rounded-lg border border-brand-500/20 hidden sm:block shadow-[0_0_15px_rgba(245,158,11,0.2)]">
                        <span className="text-2xl">🛸</span>
                    </div>
                    <div className="text-center">
                        <h1 className="heading-1 leading-none text-2xl md:text-3xl">{fleet.name}</h1>
                        <p className="text-xs text-slate-400 mt-2 flex justify-center items-center gap-3 font-mono">
                            <span className="label-text mb-0 text-[10px]">FC</span>
                            <span className="text-white font-bold">{fleet.commander_name}</span>
                            
                            {fleet.esi_fleet_id && (
                                <>
                                    <span className="text-slate-600">|</span>
                                    <span className="label-text mb-0 text-[10px]">ID</span>
                                    <span 
                                        className="text-brand-400 font-bold cursor-copy hover:text-white transition" 
                                        title="Copy Fleet ID" 
                                        onClick={() => navigator.clipboard.writeText(fleet.esi_fleet_id)}
                                    >
                                        {fleet.esi_fleet_id}
                                    </span>
                                </>
                            )}

                            {/* Status Indicator */}
                            <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse transition-all duration-500" title="Live"></span>
                        </p>
                    </div>
                </div>

                {/* Right Actions */}
                <div className="absolute right-4 top-1/2 -translate-y-1/2">
                    <button 
                        onClick={() => setXupModalOpen(true)}
                        className="btn-primary py-2 px-6 shadow-brand-500/20 flex items-center gap-2"
                    >
                        <Plus size={18} /> <span className="hidden md:inline">X-UP</span>
                    </button>
                </div>
            </div>

            {/* Main Board */}
            <div className="flex-grow overflow-x-auto overflow-y-hidden p-4 custom-scrollbar relative">
                <div className="flex gap-2 h-full min-w-max mx-auto w-fit">
                    <Column title="X-UP" color="amber" entries={columns.pending} icon={Clock} isPending={true} />
                    <Column title="LOGI" color="green" entries={columns.logi} icon={Shield} />
                    <Column title="DPS" color="green" entries={columns.dps} icon={Crosshair} />
                    <Column title="SNIPER" color="green" entries={columns.sniper} icon={Zap} />
                    <Column title="OTHER" color="green" entries={columns.other} icon={Anchor} />
                    
                    {/* Fleet Overview (Stub for now, requires complex ESI logic) */}
                    {permissions.is_fc && (
                        <div className="w-80 flex flex-col glass-panel overflow-hidden h-full ml-2 border-white/10 shadow-xl bg-slate-900/90">
                            <div className="bg-blue-600/10 border-b border-blue-500/20 p-3 flex justify-between items-center">
                                <h3 className="label-text text-blue-400 mb-0">Fleet Overview</h3>
                                <div className="flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 rounded-full bg-slate-500"></span>
                                    <span className="text-[10px] text-slate-500 font-mono">Syncing...</span>
                                </div>
                            </div>
                            <div className="flex-grow overflow-y-auto p-2 custom-scrollbar flex items-center justify-center text-slate-500 opacity-50 flex-col gap-2">
                                <div className="w-6 h-6 border-2 border-slate-500 border-t-transparent rounded-full animate-spin"></div>
                                <p className="text-xs">Waiting for stream...</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* X-UP Modal (Simple Placeholder) */}
            {xupModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dark-950/80 backdrop-blur-sm" onClick={() => setXupModalOpen(false)}>
                    <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
                        <h2 className="text-xl font-bold text-white mb-4">Join Waitlist</h2>
                        <p className="text-slate-400 text-sm mb-6">Select your ship to X-up for this fleet.</p>
                        <div className="space-y-2">
                            {/* In a real implementation, this would fetch available ships from the backend */}
                            <button onClick={() => handleXup(1)} className="w-full btn-secondary justify-start">Use Active Ship</button>
                        </div>
                        <div className="mt-6 flex justify-end">
                            <button onClick={() => setXupModalOpen(false)} className="btn-ghost">Cancel</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

const Column = ({ title, color, entries, icon: Icon, isPending }) => {
    // Map color props to Tailwind classes matching templates
    const headerColor = {
        amber: 'bg-amber-600/10 border-amber-500/20 text-amber-400',
        green: 'bg-green-600/10 border-green-500/20 text-green-400',
        red: 'bg-red-600/10 border-red-500/20 text-red-400',
    }[color] || 'bg-slate-600/10 border-slate-500/20 text-slate-400';

    return (
        <div className="w-80 flex flex-col glass-panel overflow-hidden h-full shadow-xl bg-slate-900/80 backdrop-blur-sm transition-all duration-300">
            {/* Header */}
            <div className={`p-3 border-b flex justify-between items-center ${headerColor}`}>
                <div className="flex items-center gap-2">
                    <Icon size={14} />
                    <h3 className="text-xs font-bold uppercase tracking-widest">{title}</h3>
                </div>
                <span className="badge badge-slate bg-black/20 border-black/10">{entries.length}</span>
            </div>

            {/* List */}
            <div className="flex-grow overflow-y-auto p-2 custom-scrollbar space-y-1.5 relative">
                {entries.map(entry => (
                    <EntryCard key={entry.id} entry={entry} isPending={isPending} />
                ))}
                {entries.length === 0 && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center opacity-20 pointer-events-none">
                        <Icon size={48} className="text-slate-500 mb-2" />
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">Empty</span>
                    </div>
                )}
            </div>
        </div>
    );
};

const EntryCard = ({ entry, isPending }) => {
    return (
        <div className="glass-panel p-1 relative group hover:border-brand-500/50 hover:bg-slate-800/60 transition-all duration-300 mb-0.5 cursor-pointer border border-white/5 shadow-lg shadow-black/20">
            <div className="flex gap-2">
                {/* Portrait */}
                <div className="relative shrink-0">
                    <img src={`https://images.evetech.net/characters/${entry.character.id}/portrait?size=64`} className="w-10 h-10 rounded border border-white/10 bg-black" alt="" />
                    {/* Time Badge */}
                    <div className="absolute -bottom-1 -right-1 bg-slate-900 text-[9px] text-slate-400 px-1 rounded border border-slate-700 font-mono shadow-sm">
                        {new Date(entry.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                    </div>
                </div>

                {/* Content */}
                <div className="flex-grow min-w-0 flex flex-col justify-center">
                    <div className="flex justify-between items-start">
                        <span className="text-xs font-bold text-slate-200 truncate leading-tight group-hover:text-white transition">
                            {entry.character.name}
                        </span>
                        {/* Tag Indicators */}
                        <div className="flex gap-0.5">
                            {entry.tags?.map(tag => (
                                <div key={tag} className="w-1.5 h-1.5 rounded-full bg-blue-500" title={tag}></div>
                            ))}
                        </div>
                    </div>
                    
                    <div className="text-[10px] text-slate-400 truncate flex items-center gap-1 mt-0.5">
                        <span className="text-slate-500">🚀</span> {entry.hull.name}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default FleetDashboard;