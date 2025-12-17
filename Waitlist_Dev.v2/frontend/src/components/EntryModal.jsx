import React, { useState, useEffect } from 'react';
import { apiCall } from '../utils/api';
import clsx from 'clsx';
import { Copy, AlertTriangle, CheckCircle, HelpCircle } from 'lucide-react';

export const EntryModal = ({ isOpen, onClose, entryId, isFC }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch data when modal opens or ID changes
    useEffect(() => {
        if (isOpen && entryId) {
            setLoading(true);
            setError(null);
            setData(null);

            apiCall(`/fleet/entry/api/${entryId}/`)
                .then(r => {
                    if (r.status === 403) throw new Error("Unauthorized Access");
                    if (r.status === 500) throw new Error("Server Error (500): Check SDE Data");
                    if (!r.ok) throw new Error(`HTTP Error ${r.status}`);
                    return r.json();
                })
                .then(d => {
                    setData(d);
                    setLoading(false);
                })
                .catch(err => {
                    setError(err.message);
                    setLoading(false);
                });
        }
    }, [isOpen, entryId]);

    const handleCopyEft = () => {
        if (data?.raw_eft) navigator.clipboard.writeText(data.raw_eft);
    };

    const handleAction = (action) => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall(`/fleet/action/${entryId}/${action}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf }
        })
        .then(r => r.json())
        .then(d => {
            if (!d.success) alert("Error: " + d.error);
            else onClose();
        })
        .catch(alert);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dark-950/80 backdrop-blur-sm" onClick={onClose}>
            <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl w-full max-w-4xl h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>
                
                {/* Header */}
                <div className="p-4 border-b border-white/10 flex justify-between items-start bg-black/20">
                    {loading ? (
                        <div className="animate-pulse flex items-center gap-4">
                            <div className="w-16 h-16 bg-white/5 rounded-lg"></div>
                            <div className="space-y-2">
                                <div className="h-6 w-48 bg-white/5 rounded"></div>
                                <div className="h-4 w-32 bg-white/5 rounded"></div>
                            </div>
                        </div>
                    ) : error ? (
                         <div className="text-red-400 font-bold flex items-center gap-2">
                            <AlertTriangle /> {error}
                         </div>
                    ) : (
                        <div className="flex items-center gap-4">
                            <div className="relative">
                                <img src={`https://images.evetech.net/types/${data.hull_id}/icon?size=64`} className="w-16 h-16 rounded-lg border border-white/10 bg-black/50" alt="" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-white leading-none">{data.character_name}</h2>
                                <p className="text-brand-400 text-sm mt-1 font-mono">{data.corp_name}</p>
                                <div className="flex items-center gap-2 mt-2 text-xs text-slate-400">
                                    <span className="font-bold text-slate-300">{data.ship_name}</span>
                                    <span className="opacity-50">|</span>
                                    <span>{data.fit_name}</span>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="flex gap-2">
                         <button onClick={handleCopyEft} className="btn-secondary py-2 px-3 text-xs" title="Copy EFT">
                            <Copy size={14} />
                        </button>
                        <button onClick={onClose} className="btn-secondary py-2 px-3 text-xs hover:bg-red-500/20 hover:text-red-400 hover:border-red-500/30">
                            ✕
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-grow overflow-y-auto custom-scrollbar bg-slate-900/50" id="entry-slots">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-4">
                            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
                            <p className="font-mono text-sm animate-pulse">Scanning module attributes...</p>
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center justify-center h-full text-center px-6">
                            <div className="text-4xl mb-2">💥</div>
                            <h4 className="text-red-400 font-bold mb-1">Analysis Failed</h4>
                            <p className="text-slate-500 text-xs">{error}</p>
                        </div>
                    ) : (
                        <>
                            {data.slots && data.slots.length > 0 ? (
                                data.slots.map((group, i) => (
                                    <SlotGroup key={i} group={group} />
                                ))
                            ) : (
                                <div className="p-8 text-center text-slate-500 italic">No slot data available.</div>
                            )}
                        </>
                    )}
                </div>

                {/* Footer Actions (FC) */}
                {isFC && !loading && !error && (
                    <div className="p-4 border-t border-white/10 bg-black/20 grid grid-cols-4 gap-4">
                        <button onClick={() => handleAction('approve')} className="btn-success py-3 shadow-lg shadow-green-500/10">Approve</button>
                        <button onClick={() => handleAction('invite')} className="btn-primary py-3 shadow-lg shadow-blue-500/10">Invite</button>
                        <button onClick={() => handleAction('deny')} className="btn-danger py-3">Reject</button>
                        <button onClick={() => handleAction('remove')} className="btn-secondary py-3 text-red-400 border-red-500/20 hover:bg-red-500/10">Kick</button>
                    </div>
                )}
            </div>
        </div>
    );
};

const SlotGroup = ({ group }) => {
    // Hide Subsystems if empty
    if (group.key === 'subsystem' && group.total === 0) return null;

    return (
        <div>
            {/* Header */}
            <div className="bg-slate-900/90 backdrop-blur-sm px-4 py-1.5 border-b border-white/5 flex justify-between items-center sticky top-0 z-10 shadow-sm">
                <h5 className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">{group.name}</h5>
                {group.is_hardpoint && (
                    <span className="text-[9px] text-slate-600 font-mono tracking-tight">({group.used}/{group.total})</span>
                )}
            </div>
            
            {/* Modules */}
            <div className="px-4 py-1 space-y-px">
                {group.modules.map((mod, index) => (
                    <ModuleRow key={index} mod={mod} index={index} groupName={group.name} />
                ))}
                
                {/* Empty Slots */}
                {group.is_hardpoint && Array.from({ length: group.empties_count }).map((_, i) => (
                    <div key={`empty-${i}`} className="flex items-center gap-2 px-2 py-0.5 opacity-30 select-none">
                        <div className="w-4 h-4 rounded bg-white/10 ml-0.5"></div>
                        <span className="text-[9px] text-slate-500 font-mono italic">[Empty Slot]</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

const ModuleRow = ({ mod, index, groupName }) => {
    const [showDiffs, setShowDiffs] = useState(false);
    const hasDiffs = mod.diffs && mod.diffs.length > 0;
    
    // Determine Styles based on status
    const getStyles = (status) => {
        switch (status) {
            case 'MATCH': return { border: 'border-transparent hover:border-white/10', bg: 'bg-transparent', icon: null, text: 'text-slate-400' };
            case 'UPGRADE': return { border: 'border-green-500/50', bg: 'bg-green-500/10', icon: 'UPGRADE', text: 'text-green-400' };
            case 'SIDEGRADE': return { border: 'border-blue-500/50', bg: 'bg-blue-500/10', icon: 'SIDEGRADE', text: 'text-blue-400' };
            case 'DOWNGRADE': return { border: 'border-amber-500/50', bg: 'bg-amber-500/10', icon: 'DOWNGRADE', text: 'text-amber-400' };
            case 'MISSING': return { border: 'border-red-500/50', bg: 'bg-red-500/10', icon: 'MISSING', text: 'text-red-400' };
            case 'EXTRA': return { border: 'border-purple-500/50', bg: 'bg-purple-500/10', icon: 'EXTRA', text: 'text-purple-400' };
            default: return { border: 'border-white/10', bg: 'bg-transparent', icon: '?', text: 'text-slate-500' };
        }
    };

    const styles = getStyles(mod.status);
    const bgClass = index % 2 === 0 ? 'bg-white/5' : 'bg-transparent';
    const finalBg = mod.status === 'MATCH' ? bgClass : styles.bg;

    return (
        <div className="relative group/mod">
            <div 
                className={clsx(
                    "flex items-center gap-2 px-2 py-0.5 rounded border transition-all duration-300",
                    styles.border, finalBg,
                    hasDiffs ? "cursor-pointer hover:brightness-125" : ""
                )}
                onClick={() => hasDiffs && setShowDiffs(!showDiffs)}
            >
                <img 
                    src={`https://images.evetech.net/types/${mod.id}/icon?size=32`} 
                    className="w-4 h-4 rounded shadow-inner flex-shrink-0" 
                    onError={(e) => e.target.style.opacity = 0} 
                    alt=""
                />

                <div className="flex-grow min-w-0 text-[11px]">
                    <div className="flex justify-between items-center">
                        <span className="font-medium text-slate-300 truncate group-hover/mod:text-white leading-tight">
                            {mod.name}
                        </span>

                        <div className="text-right shrink-0 ml-2 flex items-center gap-2">
                            {mod.quantity > 1 && (
                                <span className="text-[9px] text-brand-400 font-mono leading-none bg-brand-900/20 px-1 rounded border border-brand-500/20">
                                    x{mod.quantity}
                                </span>
                            )}
                            {styles.icon && (
                                <span className={clsx("text-[9px] font-bold leading-none", styles.text)}>
                                    {styles.icon}
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Flag Count */}
                    {hasDiffs && (
                        <div className={clsx("text-[9px] opacity-80 leading-none mt-0.5 text-right font-mono tracking-tight", styles.text)}>
                            {mod.diffs.length} flags ↓
                        </div>
                    )}

                    {/* Comparison Subtext */}
                    {mod.status !== 'MATCH' && (
                        <div className="text-[9px] text-slate-500 flex items-center gap-1 mt-0.5 leading-none">
                            <span>vs</span>
                            <span className={styles.text}>{mod.doctrine_name || 'Empty'}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Diffs Box */}
            {hasDiffs && showDiffs && (
                <div className={clsx(
                    "mt-0.5 ml-2 mr-2 mb-1 p-2 rounded text-[9px] font-mono border animate-fade-in shadow-inner",
                    mod.status === 'DOWNGRADE' ? 'bg-amber-900/20 border-amber-500/30 text-amber-200' :
                    mod.status === 'UPGRADE' ? 'bg-green-900/20 border-green-500/30 text-green-200' :
                    'bg-slate-800 border-slate-700 text-slate-300'
                )}>
                    {mod.diffs.map((diff, i) => (
                        <div key={i} className="flex justify-between items-center mb-0.5 last:mb-0">
                            <span className="flex items-center gap-1 opacity-80">
                                {diff.is_pass ? '✔' : '⚠'} {diff.attribute}
                            </span>
                            <span className={clsx("text-right", diff.is_pass ? 'text-green-400' : 'text-red-400')}>
                                {diff.pilot_val} <span className="opacity-50 tracking-tighter">(Req: {diff.doctrine_val})</span>
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
