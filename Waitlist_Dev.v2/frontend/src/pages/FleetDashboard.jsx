import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Shield, Crosshair, Zap, Anchor, Clock } from 'lucide-react';

const FleetDashboard = () => {
    const { token } = useParams();
    const [fleetData, setFleetData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchFleet = () => {
            fetch(`/api/fleet/${token}/dashboard/`)
                .then(res => {
                    if (!res.ok) throw new Error("Failed to load fleet");
                    return res.json();
                })
                .then(data => {
                    setFleetData(data);
                    setLoading(false);
                })
                .catch(err => {
                    setError(err.message);
                    setLoading(false);
                });
        };

        fetchFleet();
        // Poll every 5 seconds for now (simulating real-time)
        const interval = setInterval(fetchFleet, 5000);
        return () => clearInterval(interval);
    }, [token]);

    if (loading) return <div className="p-10 text-center animate-pulse">Establishing Uplink...</div>;
    if (error) return <div className="p-10 text-center text-red-500">Signal Lost: {error}</div>;

    const { fleet, columns, permissions } = fleetData;

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Header */}
            <div className="bg-dark-900 border-b border-white/5 p-4 flex justify-between items-center shadow-md z-10">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        {fleet.type}
                        <span className={`badge ${fleet.is_active ? 'badge-green' : 'badge-red'}`}>
                            {fleet.is_active ? 'ACTIVE' : 'CLOSED'}
                        </span>
                    </h1>
                    <div className="text-sm text-slate-400 mt-1 flex items-center gap-4">
                        <span>FC: <strong className="text-white">{fleet.commander_name}</strong></span>
                        <span className="font-mono text-xs opacity-50">UID: {fleet.token}</span>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Action Buttons */}
                    <button className="btn-primary" onClick={() => alert("X-Up Modal Placeholder")}>
                        <Zap size={18} /> X-Up
                    </button>
                    {permissions.is_fc && (
                        <button className="btn-secondary">
                            <SettingsIcon /> Settings
                        </button>
                    )}
                </div>
            </div>

            {/* Columns Container */}
            <div className="flex-1 overflow-x-auto overflow-y-hidden p-4">
                <div className="flex h-full gap-4 min-w-[1200px]">
                     <WaitlistColumn title="Pending" entries={columns.pending} icon={Clock} color="slate" />
                     <WaitlistColumn title="Logistics" entries={columns.logi} icon={Shield} color="green" />
                     <WaitlistColumn title="DPS" entries={columns.dps} icon={Crosshair} color="red" />
                     <WaitlistColumn title="Specialist" entries={columns.sniper} icon={Zap} color="brand" />
                     <WaitlistColumn title="Other" entries={columns.other} icon={Anchor} color="slate" />
                </div>
            </div>
        </div>
    );
};

const WaitlistColumn = ({ title, entries, icon: Icon, color }) => {
    const colorStyles = {
        slate: 'border-slate-500/20 bg-slate-900/20',
        green: 'border-green-500/20 bg-green-900/10',
        red: 'border-red-500/20 bg-red-900/10',
        brand: 'border-brand-500/20 bg-brand-900/10',
    }[color];

    return (
        <div className={`flex-1 flex flex-col rounded-xl border ${colorStyles} overflow-hidden backdrop-blur-sm`}>
            {/* Header */}
            <div className="p-3 border-b border-white/5 flex justify-between items-center bg-white/5">
                <div className="flex items-center gap-2 font-bold text-slate-200 uppercase tracking-wide text-sm">
                    <Icon size={16} /> {title}
                </div>
                <div className="badge badge-slate">{entries.length}</div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2">
                 {entries.map(entry => (
                     <PilotCard key={entry.id} entry={entry} />
                 ))}
            </div>
        </div>
    );
};

const PilotCard = ({ entry }) => {
    return (
        <div className="bg-dark-900/80 p-3 rounded border border-white/5 hover:border-brand-500/50 transition group relative">
             <div className="flex justify-between items-start mb-1">
                 <div className="font-bold text-white text-sm truncate">{entry.character.name}</div>
                 <div className="flex gap-1">
                     {entry.other_categories.map(cat => (
                         <div key={cat} className={`w-2 h-2 rounded-full bg-${getCategoryColor(cat)}-500`} title={cat} />
                     ))}
                 </div>
             </div>

             <div className="text-xs text-slate-400 mb-2 truncate">
                 {entry.hull.name}
             </div>

             <div className="flex justify-between items-center text-[10px] text-slate-500 font-mono">
                <span>{entry.stats.hull_hours}h in Hull</span>
                <span>{new Date(entry.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
             </div>
        </div>
    );
};

const getCategoryColor = (cat) => {
    switch(cat) {
        case 'logi': return 'green';
        case 'dps': return 'red';
        case 'sniper': return 'yellow'; // brand
        default: return 'slate';
    }
}

const SettingsIcon = () => (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
);

export default FleetDashboard;