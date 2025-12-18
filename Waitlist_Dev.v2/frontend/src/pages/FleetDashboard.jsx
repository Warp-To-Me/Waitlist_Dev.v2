import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { Shield, Crosshair, Zap, Anchor, Clock, Settings, Scroll, Plus, RefreshCw } from 'lucide-react';
import clsx from 'clsx';
import { 
    setFleetData, setFleetError, selectFleetData, selectFleetColumns, selectFleetOverview,
    selectFleetPermissions, selectFleetLoading, selectFleetError, selectConnectionStatus,
    takeOverFleet
} from '../store/slices/fleetSlice';
import { wsConnect, wsDisconnect } from '../store/middleware/socketMiddleware';
import { apiCall } from '../utils/api';

// Components
import WaitlistEntry from '../components/WaitlistEntry';
import FleetOverview from '../components/FleetOverview';
import { XUpModal, UpdateModal } from '../components/FleetModals';
import { EntryModal } from '../components/EntryModal';

const FleetDashboard = () => {
    const { token } = useParams();
    const dispatch = useDispatch();

    // Redux State
    const fleet = useSelector(selectFleetData);
    const columns = useSelector(selectFleetColumns);
    const overview = useSelector(selectFleetOverview);
    const permissions = useSelector(selectFleetPermissions);
    const loading = useSelector(selectFleetLoading);
    const error = useSelector(selectFleetError);
    const connectionStatus = useSelector(selectConnectionStatus);

    // Local Modal State
    const [xupModalOpen, setXupModalOpen] = useState(false);
    const [updateModalId, setUpdateModalId] = useState(null);
    const [entryModalId, setEntryModalId] = useState(null);

    // Initial Fetch & WebSocket Connect
    useEffect(() => {
        // 1. Initial Fetch
        apiCall(`/api/fleet/${token}/dashboard/`)
            .then(res => {
                if (res.status === 404) throw new Error("Fleet not found or you do not have access.");
                if (res.status === 403) throw new Error("Unauthorized.");
                if (!res.ok) throw new Error("Failed to load fleet data.");
                return res.json();
            })
            .then(data => {
                dispatch(setFleetData(data));
                dispatch(wsConnect(`/ws/fleet/${token}/`, 'fleet'));
            })
            .catch(err => {
                console.error(err);
                dispatch(setFleetError(err.message));
            });

        return () => {
            dispatch(wsDisconnect('fleet'));
        };
    }, [token, dispatch]);

    // Handlers
    const handleEntryAction = (entryId, action) => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall(`/api/fleet/action/${entryId}/${action}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf }
        })
        .then(r => r.json())
        .then(d => {
            if (!d.success) alert("Error: " + d.error);
        })
        .catch(err => alert("Network Error"));
    };

    const handleTakeOver = () => {
        if (confirm("Are you sure you want to take over this fleet? This will set you as the FC and attempt to link your current in-game fleet.")) {
            dispatch(takeOverFleet(token));
        }
    };

    if (loading && !fleet) return (
        <div className="absolute inset-0 flex items-center justify-center bg-dark-950">
            <div className="text-center animate-pulse">
                <div className="text-4xl mb-4">📡</div>
                <div className="text-slate-400 font-mono text-sm">Establishing Uplink...</div>
            </div>
        </div>
    );

    // Only block on error if we have NO fleet data
    if (error && !fleet) return (
        <div className="absolute inset-0 flex items-center justify-center bg-dark-950">
            <div className="text-center">
                <div className="text-4xl mb-4 text-red-500">⚠</div>
                <h2 className="text-xl font-bold text-white">Connection Lost</h2>
                <p className="text-slate-500 mt-2">{error}</p>
                <Link to="/" className="btn-secondary mt-6 inline-flex">Return to Landing</Link>
            </div>
        </div>
    );

    if (!fleet) return null;

    const isFC = permissions.is_fc;

    return (
        <div className="absolute inset-0 flex flex-col overflow-hidden bg-dark-950 opacity-100"> 
            
            {/* Header Bar */}
            <div className="glass-header p-4 relative flex justify-center items-center z-20 shrink-0 min-h-[4rem]">
                
                {/* Left Actions (FC) */}
                {isFC && (
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
                            <span 
                                className={clsx(
                                    "w-2.5 h-2.5 rounded-full transition-all duration-500",
                                    (connectionStatus === 'connected' && !error) ? "bg-green-500 shadow-green-500/50" : "bg-red-500 animate-pulse"
                                )}
                                title={error ? error : "Live"}
                            ></span>

                            {/* Take Over Button */}
                            {isFC && (
                                <button
                                    onClick={handleTakeOver}
                                    className={clsx(
                                        "ml-2 text-[10px] px-2 py-0.5 rounded border flex items-center gap-1 transition-colors",
                                        error
                                            ? "bg-red-500/20 hover:bg-red-500/30 text-red-400 border-red-500/30"
                                            : "bg-slate-700/50 hover:bg-slate-700 text-slate-300 border-slate-600"
                                    )}
                                    title="Take Over Command"
                                >
                                    <RefreshCw size={10} /> Take Over
                                </button>
                            )}
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
                    <Column 
                        title="X-UP" color="amber" entries={columns.pending} icon={Clock} isPending={true}
                        onAction={handleEntryAction} onOpenEntry={setEntryModalId} onOpenUpdate={setUpdateModalId}
                    />
                    <Column 
                        title="LOGI" color="blue" entries={columns.logi} icon={Shield} 
                        onAction={handleEntryAction} onOpenEntry={setEntryModalId} onOpenUpdate={setUpdateModalId}
                    />
                    <Column 
                        title="DPS" color="red" entries={columns.dps} icon={Crosshair} 
                        onAction={handleEntryAction} onOpenEntry={setEntryModalId} onOpenUpdate={setUpdateModalId}
                    />
                    <Column 
                        title="SNIPER" color="green" entries={columns.sniper} icon={Zap} 
                        onAction={handleEntryAction} onOpenEntry={setEntryModalId} onOpenUpdate={setUpdateModalId}
                    />
                    <Column 
                        title="OTHER" color="green" entries={columns.other} icon={Anchor} 
                        onAction={handleEntryAction} onOpenEntry={setEntryModalId} onOpenUpdate={setUpdateModalId}
                    />
                    
                    {/* Fleet Overview Column */}
                    {permissions.can_view_overview && (
                        <div className="w-80 flex flex-col glass-panel overflow-hidden h-full ml-2 border-white/10 shadow-xl bg-slate-900/90">
                            <div className="bg-blue-600/10 border-b border-blue-500/20 p-3 flex justify-between items-center">
                                <h3 className="label-text text-blue-400 mb-0">Fleet Overview</h3>
                                <div className="flex items-center gap-2">
                                    <span className={clsx("w-1.5 h-1.5 rounded-full transition-colors duration-300", overview ? "bg-green-500" : "bg-slate-500")}></span>
                                    <span className="text-[10px] text-slate-500 font-mono">
                                        {overview ? "Live" : "Syncing..."}
                                    </span>
                                </div>
                            </div>
                            <FleetOverview overview={overview} />
                        </div>
                    )}
                </div>
            </div>

            {/* Modals */}
            <XUpModal isOpen={xupModalOpen} onClose={() => setXupModalOpen(false)} fleetToken={token} />
            <UpdateModal isOpen={!!updateModalId} onClose={() => setUpdateModalId(null)} entryId={updateModalId} />
            <EntryModal isOpen={!!entryModalId} onClose={() => setEntryModalId(null)} entryId={entryModalId} isFC={isFC} />
        </div>
    );
};

const Column = ({ title, color, entries, icon: Icon, isPending, onAction, onOpenEntry, onOpenUpdate }) => {
    // Map color props to Tailwind classes matching templates
    const headerColor = {
        amber: 'bg-amber-600/10 border-amber-500/20 text-amber-400 border-b-amber-500',
        green: 'bg-green-600/10 border-green-500/20 text-green-400 border-b-green-500',
        red: 'bg-red-600/10 border-red-500/20 text-red-400 border-b-red-500',
        blue: 'bg-blue-600/10 border-blue-500/20 text-blue-400 border-b-blue-500',
    }[color] || 'bg-slate-600/10 border-slate-500/20 text-slate-400';

    return (
        <div className="w-72 flex flex-col glass-panel overflow-hidden h-full shadow-xl bg-slate-900/40 backdrop-blur-md rounded-xl border border-white/10 flex-shrink-0">
            {/* Header */}
            <div className={`p-3 border-b-2 flex justify-between items-center bg-slate-900/60 rounded-t-xl ${headerColor}`}>
                <div className="flex items-center gap-2">
                    {/* <Icon size={14} /> */}
                    <h3 className="text-sm font-bold uppercase tracking-wider text-white">{title}</h3>
                </div>
                <span className="bg-white/10 text-slate-300 text-xs font-mono px-2 py-0.5 rounded border border-white/5">{entries.length}</span>
            </div>

            {/* List */}
            <div className="flex-grow overflow-y-auto p-1 custom-scrollbar relative">
                {entries.map(entry => (
                    <WaitlistEntry 
                        key={entry.id} 
                        entry={entry} 
                        onAction={onAction}
                        onOpenEntry={onOpenEntry}
                        onOpenUpdate={onOpenUpdate}
                    />
                ))}
            </div>
        </div>
    );
};

export default FleetDashboard;
