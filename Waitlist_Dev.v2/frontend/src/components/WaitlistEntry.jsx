import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import clsx from 'clsx';
import { selectFleetPermissions, selectSiblingCategories } from '../store/slices/fleetSlice';
import { useAuth } from '../context/AuthContext';
import { selectUser } from '../store/slices/authSlice';

// Icons/Dots
// For multi-fit indicators (Logi/DPS/Sniper dots)

const WaitlistEntry = ({ entry, onAction, onOpenEntry, onOpenUpdate }) => {
    const { user: currentUser } = useAuth();
    const permissions = useSelector(selectFleetPermissions);
    const otherCategories = useSelector(state => selectSiblingCategories(state, entry.character.id, entry.id));
    
    // Check ownership
    const isOwner = currentUser?.id === entry.character.user_id;
    
    // FC Permission Check
    const isFC = permissions.is_fc;

    // Permissions to view/click
    const canInspect = isOwner || permissions.can_view_overview || isFC;

    // Time Formatting
    const [timeWaiting, setTimeWaiting] = useState(entry.time_waiting);

    useEffect(() => {
        // If created_at is available, calculate local time difference
        if (entry.created_at) {
            const calculateTime = () => {
                const now = new Date();
                const created = new Date(entry.created_at);
                const diffMs = now - created;
                const minutes = Math.floor(diffMs / 60000);
                setTimeWaiting(minutes > 0 ? minutes : 0);
            };

            calculateTime(); // Initial calc
            const interval = setInterval(calculateTime, 30000); // Update every 30s
            return () => clearInterval(interval);
        } else {
             // Fallback to static if no timestamp
             setTimeWaiting(entry.time_waiting);
        }
    }, [entry.created_at, entry.time_waiting]);

    const isLongWait = timeWaiting > 15;

    // Handle Clicks
    const handleClick = () => {
        if (canInspect && onOpenEntry) {
            onOpenEntry(entry.id);
        }
    };

    return (
        <div 
            id={`entry-${entry.id}`}
            onClick={handleClick}
            className={clsx(
                "glass-panel p-1 relative group transition-all duration-300 mb-0.5 border border-white/5 shadow-lg shadow-black/20",
                canInspect ? "cursor-pointer hover:border-brand-500/50 hover:bg-slate-800/60" : "cursor-default opacity-90"
            )}
        >
            {/* Time Indicator & Badges */}
            <div className="absolute top-2 right-2 flex items-center gap-2 z-10">
                
                {/* SKILL WARNING (FC Only) */}
                {!entry.can_fly && isFC && (
                    <div className="group/skill relative">
                        <span className="badge badge-red animate-pulse cursor-help text-[9px]">
                            ⚠ SKILL
                        </span>
                        {/* Tooltip */}
                        <div className="absolute right-0 top-full mt-1 hidden group-hover/skill:block z-50 whitespace-nowrap bg-black border border-red-500/50 rounded p-2 text-[9px] text-red-200 shadow-xl">
                            <div className="font-bold border-b border-red-500/30 mb-1 pb-1">Missing Skills</div>
                            {entry.missing_skills.map((s, i) => <div key={i}>{s}</div>)}
                        </div>
                    </div>
                )}

                {/* TIER BADGE */}
                {entry.tier && isFC && (
                    <div className="group/tier relative">
                        <span 
                            className={clsx("px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide border", entry.tier.badge_class)}
                            style={{ boxShadow: `0 0 8px ${entry.tier.hex_color}30` }}
                        >
                            {entry.tier.name}
                        </span>
                    </div>
                )}

                {/* WAIT TIME */}
                <span className={clsx(
                    "text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border",
                    isLongWait ? "bg-red-900/30 text-red-400 border-red-500/30" : "bg-amber-900/30 text-amber-400 border-amber-500/30"
                )}>
                    {timeWaiting}m
                </span>
            </div>

            {/* Pilot Info */}
            <div className="flex items-center gap-3 mb-2">
                <div className="relative shrink-0">
                    <img 
                        src={`https://images.evetech.net/characters/${entry.character.id}/portrait?size=64`}
                        className="w-8 h-8 rounded-lg border border-white/10 shadow-sm bg-black/50" 
                        alt="" 
                    />
                </div>
                <div className="flex-grow min-w-0">
                    <div className="font-bold text-sm text-slate-200 truncate group-hover:text-white transition leading-none">
                        {entry.character.name}
                    </div>
                    <div className="text-[10px] text-slate-500 truncate mt-0.5 font-medium">
                        {entry.character.corporation_name}
                    </div>
                </div>
            </div>

            {/* Ship & Fit Section */}
            <div className="flex items-center gap-3 bg-black/20 p-1.5 rounded-lg border border-white/5 relative group/fit">
                {/* Ship Icon */}
                <div className="relative flex-shrink-0">
                    <img 
                        src={`https://images.evetech.net/types/${entry.hull.id}/icon?size=32`}
                        className="w-6 h-6 rounded border border-white/10 bg-slate-900/50" 
                        alt="" 
                    />
                </div>

                {/* Details */}
                <div className="flex-grow min-w-0 pr-6">
                    <div className="text-xs font-bold text-brand-400 truncate leading-tight">
                        {entry.hull.name}
                    </div>
                    <div className="text-[10px] text-slate-400 truncate mt-0.5 font-mono opacity-80 group-hover/fit:opacity-100 transition">
                        {entry.fit.name}
                    </div>
                </div>

                {/* Multi-Fit Indicators (Anchored Right Center) */}
                {otherCategories && otherCategories.length > 0 && (
                    <div className="flex flex-col gap-1 absolute right-2 top-1/2 -translate-y-1/2 justify-center items-center h-full py-1">
                        {otherCategories.includes('logi') && (
                             <IndicatorDot color="blue" label="Logistics" />
                        )}
                        {otherCategories.includes('dps') && (
                             <IndicatorDot color="red" label="DPS" />
                        )}
                        {otherCategories.includes('sniper') && (
                             <IndicatorDot color="green" label="Sniper" />
                        )}
                    </div>
                )}
            </div>

            {/* Footer Stats */}
            <div className="flex justify-between items-center text-[9px] text-slate-500 uppercase font-bold tracking-wider mt-1.5 px-1">
                <div className="flex items-center gap-1.5">
                    <span className="opacity-50">Total</span>
                    <span className="text-slate-300 font-mono">{entry.display_stats?.total_hours || 0}h</span>
                </div>
                <div className="w-px h-2 bg-white/10"></div>
                <div className="flex items-center gap-1.5">
                    <span className="opacity-50">Hull</span>
                    <span className="text-slate-300 font-mono">{entry.display_stats?.hull_hours || 0}h</span>
                </div>
            </div>

            {/* OWNER ACTIONS */}
            {isOwner && (
                <div className="mt-1.5 pt-1.5 border-t border-white/5 grid grid-cols-2 gap-2" onClick={e => e.stopPropagation()}>
                    <button 
                        onClick={() => onOpenUpdate(entry.id)} 
                        className="bg-blue-600 hover:bg-blue-500 text-white text-[9px] py-0.5 rounded font-bold transition shadow-lg shadow-blue-500/20"
                    >
                        Update
                    </button>
                    <button 
                        onClick={() => onAction(entry.id, 'leave')} 
                        className="bg-white/5 hover:bg-red-500/20 text-slate-400 hover:text-red-400 border border-white/10 hover:border-red-500/30 text-[9px] py-0.5 rounded font-bold transition"
                    >
                        Leave
                    </button>
                </div>
            )}

            {/* FC ACTIONS */}
            {isFC && (
                <div className="mt-1.5 pt-1.5 border-t border-white/5 flex gap-1.5" onClick={e => e.stopPropagation()}>
                    {entry.status === 'pending' ? (
                        <>
                            <button 
                                onClick={() => onAction(entry.id, 'approve')} 
                                className="flex-1 bg-green-600 hover:bg-green-500 text-white text-[9px] py-0.5 rounded font-bold transition shadow-lg shadow-green-500/20"
                            >
                                Approve
                            </button>
                            <button 
                                onClick={() => onAction(entry.id, 'deny')} 
                                className="flex-1 bg-white/5 hover:bg-red-500/20 text-slate-400 hover:text-red-400 border border-white/10 hover:border-red-500/30 text-[9px] py-0.5 rounded font-bold transition"
                            >
                                Reject
                            </button>
                        </>
                    ) : (
                        <>
                            <button 
                                onClick={() => onAction(entry.id, 'invite')} 
                                className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-[9px] py-0.5 rounded font-bold transition shadow-lg shadow-blue-500/20"
                            >
                                Invite
                            </button>
                            <button 
                                onClick={() => onAction(entry.id, 'deny')} 
                                className="flex-1 bg-white/5 hover:bg-red-500/20 text-slate-400 hover:text-red-400 border border-white/10 hover:border-red-500/30 text-[9px] py-0.5 rounded font-bold transition"
                            >
                                Kick
                            </button>
                        </>
                    )}
                </div>
            )}
        </div>
    );
};

const IndicatorDot = ({ color, label }) => {
    const colorClasses = {
        blue: "bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.8)]",
        red: "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.8)]",
        green: "bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.8)]"
    }[color] || "bg-slate-500";

    return (
        <div className="group/tooltip relative">
            <div className={`w-1.5 h-1.5 rounded-full ${colorClasses} animate-pulse hover:scale-125 transition`}></div>
            <div className="absolute right-4 top-1/2 -translate-y-1/2 hidden group-hover/tooltip:block z-50 whitespace-nowrap">
                <div className="bg-slate-900 text-slate-200 text-[10px] px-2 py-1 rounded border border-white/10 shadow-xl">
                    Has <strong>{label}</strong> Fit
                </div>
            </div>
        </div>
    );
};

export default WaitlistEntry;
