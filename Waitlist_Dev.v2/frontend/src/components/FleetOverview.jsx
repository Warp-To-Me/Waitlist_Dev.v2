import React, { useState } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import clsx from 'clsx';

const FleetOverview = ({ overview }) => {
    // If no data yet
    if (!overview || !overview.hierarchy) {
        return (
            <div className="flex-grow overflow-y-auto p-2 custom-scrollbar flex items-center justify-center text-slate-500 opacity-50 flex-col gap-2 h-full">
                <div className="w-6 h-6 border-2 border-slate-500 border-t-transparent rounded-full animate-spin"></div>
                <p className="text-xs">Waiting for stream...</p>
            </div>
        );
    }

    const { hierarchy, member_count } = overview;

    return (
        <div className="flex-grow overflow-y-auto p-2 custom-scrollbar space-y-2 h-full">
            <div className="text-[10px] text-slate-500 font-bold uppercase mb-2 pl-2">
                Fleet: {member_count} Pilots
            </div>

            {/* Fleet Commander */}
            {hierarchy.commander && (
                <MemberRow member={hierarchy.commander} roleLabel="Fleet Commander" colorClass="text-amber-500" />
            )}

            {/* Wings */}
            {hierarchy.wings && hierarchy.wings.map(wing => (
                <WingNode key={wing.id} wing={wing} />
            ))}
        </div>
    );
};

const WingNode = ({ wing }) => {
    const [collapsed, setCollapsed] = useState(false);

    return (
        <div className="mb-1">
            <div 
                className="flex items-center gap-2 cursor-pointer hover:bg-white/5 p-1 rounded transition select-none group"
                onClick={() => setCollapsed(!collapsed)}
            >
                {collapsed ? <ChevronRight size={12} className="text-slate-500" /> : <ChevronDown size={12} className="text-slate-500" />}
                <span className="text-xs font-bold text-slate-300 group-hover:text-white shrink-0">{wing.name}</span>
                
                {/* Collapsed Commander Preview */}
                {collapsed && wing.commander && (
                    <div className="flex items-center gap-2 ml-auto opacity-70 group-hover:opacity-100 transition mr-1">
                        <span className="text-[9px] text-slate-400 font-bold hidden sm:inline truncate max-w-[80px]">
                            {wing.commander.name}
                        </span>
                        <img 
                            src={`https://images.evetech.net/characters/${wing.commander.character_id}/portrait?size=32`} 
                            className="w-4 h-4 rounded-full border border-slate-600" 
                            alt=""
                        />
                    </div>
                )}
            </div>

            {!collapsed && (
                <div className="ml-2 pl-2 border-l border-white/5 animate-fade-in">
                    {wing.commander && (
                        <MemberRow member={wing.commander} roleLabel="Wing Commander" colorClass="text-slate-400" />
                    )}
                    {wing.squads.map(squad => (
                        <SquadNode key={squad.id} squad={squad} />
                    ))}
                </div>
            )}
        </div>
    );
};

const SquadNode = ({ squad }) => {
    const [collapsed, setCollapsed] = useState(false);

    return (
        <div className="mb-1">
            <div 
                className="flex items-center gap-2 cursor-pointer hover:bg-white/5 p-1 rounded transition select-none group"
                onClick={() => setCollapsed(!collapsed)}
            >
                {collapsed ? <ChevronRight size={12} className="text-slate-600" /> : <ChevronDown size={12} className="text-slate-600" />}
                <span className="text-xs font-bold text-slate-400 group-hover:text-white shrink-0">{squad.name}</span>
                
                {collapsed && squad.commander && (
                     <div className="flex items-center gap-2 ml-auto opacity-70 group-hover:opacity-100 transition mr-1">
                        <span className="text-[9px] text-slate-400 font-bold hidden sm:inline truncate max-w-[80px]">
                            {squad.commander.name}
                        </span>
                        <img 
                            src={`https://images.evetech.net/characters/${squad.commander.character_id}/portrait?size=32`} 
                            className="w-4 h-4 rounded-full border border-slate-600" 
                            alt=""
                        />
                    </div>
                )}
            </div>

            {!collapsed && (
                <div className="ml-2 pl-2 border-l border-white/5 animate-fade-in">
                    {squad.commander && (
                        <MemberRow member={squad.commander} roleLabel="Squad Commander" colorClass="text-slate-500" />
                    )}
                    {squad.members.length > 0 && (
                        <div className="ml-3 pl-2 border-l border-white/5 mt-1 space-y-0.5">
                            {squad.members.map(m => (
                                <MemberRow key={m.character_id} member={m} colorClass="text-slate-500" />
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

const MemberRow = ({ member, roleLabel, colorClass }) => {
    return (
        <div className="flex items-center justify-between p-1 hover:bg-white/5 rounded group/member">
            <div className="flex items-center gap-2 overflow-hidden">
                <img 
                    src={`https://images.evetech.net/characters/${member.character_id}/portrait?size=32`} 
                    className="w-5 h-5 rounded-full border border-white/10" 
                    alt="" 
                    loading="lazy" 
                />
                <div className="flex flex-col truncate">
                    <span className={clsx("text-[10px] font-bold leading-none", colorClass || 'text-slate-300')}>
                        {member.name}
                    </span>
                    {roleLabel && (
                        <span className="text-[9px] text-brand-500 leading-none mt-0.5">{roleLabel}</span>
                    )}
                </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                <span className="text-[9px] text-slate-500 group-hover/member:text-slate-300 transition truncate max-w-[100px]">
                    {member.ship_name}
                </span>
                <img 
                    src={`https://images.evetech.net/types/${member.ship_type_id}/icon?size=32`} 
                    className="w-4 h-4 rounded-sm border border-white/10" 
                    alt="" 
                    loading="lazy" 
                />
            </div>
        </div>
    );
};

export default FleetOverview;
