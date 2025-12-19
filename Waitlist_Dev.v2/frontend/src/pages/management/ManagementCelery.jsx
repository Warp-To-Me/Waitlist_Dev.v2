import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RefreshCw, Server, Activity, Database, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import clsx from 'clsx';
import { wsConnect, wsDisconnect } from '../../store/middleware/socketMiddleware';
import { selectCeleryStatus, selectSystemConnectionStatus } from '../../store/slices/systemSlice';

const ManagementCelery = () => {
    const dispatch = useDispatch();
    const data = useSelector(selectCeleryStatus); // Now contains the JSON object
    const status = useSelector(selectSystemConnectionStatus);
    const connected = status === 'connected';

    useEffect(() => {
        dispatch(wsConnect('/ws/system/monitor/', 'system'));
        return () => {
            dispatch(wsDisconnect('system'));
        };
    }, [dispatch]);

    if (!data) {
        return (
            <div className="space-y-6">
                 <div className="flex justify-between items-center border-b border-white/5 pb-6">
                    <div className="flex items-center gap-4">
                        <h1 className="heading-1">System Monitor</h1>
                        <span className="badge badge-slate flex items-center gap-2 normal-case font-normal">
                             <span className="w-2 h-2 rounded-full bg-slate-500 animate-pulse"></span> Connecting...
                        </span>
                    </div>
                </div>
                <div className="p-12 text-center text-slate-500 italic flex flex-col items-center gap-4">
                     <Activity className="animate-spin text-slate-700" size={48} />
                     Waiting for telemetry...
                </div>
            </div>
        );
    }

    // Helper to format large numbers
    const fmt = (n) => n?.toLocaleString() || 0;

    return (
        <div className="space-y-8 animate-fade-in">
             {/* Header */}
             <div className="flex justify-between items-center border-b border-white/5 pb-6">
                <div className="flex items-center gap-4">
                    <h1 className="heading-1">System Monitor</h1>
                    <span className={clsx("badge flex items-center gap-2 normal-case font-normal transition-all duration-300", connected ? "badge-green" : "badge-red")}>
                        <span className={clsx("w-2 h-2 rounded-full", connected ? "bg-green-500 animate-pulse" : "bg-red-500")}></span> 
                        {connected ? "Live Stream" : "Disconnected"}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                        Latency: {data.redis_latency}ms
                    </span>
                </div>
                <button onClick={() => window.location.reload()} className="btn-secondary text-xs py-1.5 shadow-lg">
                    <RefreshCw size={16} /> Reload Page
                </button>
            </div>

            {/* Top Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatusCard 
                    label="Redis Status" 
                    value={data.redis_status} 
                    sub={data.redis_error ? "Error detected" : "Operational"}
                    icon={<Database size={20} />}
                    color={data.redis_status === 'ONLINE' ? 'green' : 'red'}
                />
                 <StatusCard 
                    label="Message Queue" 
                    value={fmt(data.queue_length)} 
                    sub="Pending tasks"
                    icon={<Server size={20} />}
                    color={data.queue_length > 100 ? 'yellow' : 'blue'}
                />
                 <StatusCard 
                    label="Processed" 
                    value={fmt(data.total_processed)} 
                    sub="Tasks handled"
                    icon={<CheckCircle size={20} />}
                    color="purple"
                />
                 <StatusCard 
                    label="Load" 
                    value={`${data.system_load_percent}%`}
                    sub="Queue Capacity"
                    icon={<Activity size={20} />}
                    color={data.system_load_percent > 80 ? 'red' : 'emerald'}
                />
            </div>

            {/* ESI Health Section */}
            <div className="glass-panel p-6">
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <div className="w-1 h-6 bg-brand-500 rounded-full"></div>
                    ESI Token Health
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {/* Gauge / Overview */}
                    <div className="flex flex-col items-center justify-center p-4 bg-white/5 rounded-xl border border-white/5">
                         <div className="text-4xl font-black text-white mb-1">{data.esi_health_percent}%</div>
                         <div className="text-xs text-slate-400 uppercase tracking-widest font-bold">Health Score</div>
                         <div className="w-full bg-slate-800 h-2 rounded-full mt-4 overflow-hidden">
                             <div 
                                className="h-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 transition-all duration-500"
                                style={{ width: `${data.esi_health_percent}%` }}
                             ></div>
                         </div>
                         <div className="flex justify-between w-full mt-4 text-sm text-slate-300">
                             <span>Total Characters:</span>
                             <span className="font-mono text-white">{fmt(data.total_characters)}</span>
                         </div>
                    </div>

                    {/* Stats Breakdown */}
                    <div className="md:col-span-2 grid grid-cols-2 gap-4">
                        <StatBox label="Total Tokens" value={data.total_tokens} color="purple" />
                        <StatBox label="Missing Tokens" value={data.missing_token_count} color="red" />
                        <StatBox label="Expired Tokens" value={data.expired_token_count} color={data.expired_token_count > 0 ? "yellow" : "green"} />
                        <StatBox label="Stale Characters (>1h)" value={data.stale_count} color="yellow" />
                        <StatBox label="Active (30d)" value={data.active_30d_count} color="blue" />
                        <StatBox label="ESI API Status" value={data.esi_server_status ? "ONLINE" : "DOWN"} color={data.esi_server_status ? "green" : "red"} />
                    </div>
                </div>
            </div>

            {/* Queued Breakdowns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="glass-panel p-6">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <Clock size={20} className="text-yellow-400"/>
                        Queued Tasks (Immediate)
                    </h3>
                    <QueueTable items={data.queued_breakdown} emptyMsg="No tasks currently queued." />
                </div>
                <div className="glass-panel p-6">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                         <Clock size={20} className="text-blue-400"/>
                         Delayed / Throttled
                    </h3>
                    <QueueTable items={data.delayed_breakdown} emptyMsg="No delayed tasks." />
                </div>
            </div>

            {/* Workers Section */}
            <div className="glass-panel p-6">
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <div className="w-1 h-6 bg-purple-500 rounded-full"></div>
                    Celery Workers ({data.worker_count})
                </h3>
                
                {data.workers && data.workers.length > 0 ? (
                    <div className="grid grid-cols-1 gap-4">
                        {data.workers.map((worker) => (
                            <WorkerRow key={worker.name} worker={worker} />
                        ))}
                    </div>
                ) : (
                    <div className="p-8 text-center text-slate-500 bg-white/5 rounded-lg border border-white/5 border-dashed">
                        No workers detected.
                    </div>
                )}
            </div>
        </div>
    );
};

// --- Sub Components ---

const StatusCard = ({ label, value, sub, icon, color }) => {
    const colorClasses = {
        green: "text-green-400 bg-green-400/10 border-green-400/20",
        red: "text-red-400 bg-red-400/10 border-red-400/20",
        yellow: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
        blue: "text-blue-400 bg-blue-400/10 border-blue-400/20",
        purple: "text-purple-400 bg-purple-400/10 border-purple-400/20",
        emerald: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
    }[color] || "text-slate-400 bg-slate-400/10 border-slate-400/20";

    return (
        <div className="glass-panel p-4 flex items-center gap-4 hover:bg-white/5 transition-colors">
            <div className={`p-3 rounded-xl border ${colorClasses}`}>
                {icon}
            </div>
            <div>
                <div className="text-sm text-slate-400 font-medium">{label}</div>
                <div className="text-xl font-bold text-white leading-tight">{value}</div>
                <div className="text-xs text-slate-500 mt-0.5">{sub}</div>
            </div>
        </div>
    );
}

const StatBox = ({ label, value, color }) => {
     const textColor = {
        green: "text-green-400",
        red: "text-red-400",
        yellow: "text-yellow-400",
        blue: "text-blue-400",
    }[color] || "text-white";

    return (
        <div className="bg-slate-900/50 p-3 rounded-lg border border-white/5 flex flex-col justify-center">
            <span className={`text-xl font-mono font-bold ${textColor}`}>{value}</span>
            <span className="text-xs text-slate-500 uppercase font-bold tracking-wider">{label}</span>
        </div>
    )
}

const QueueTable = ({ items, emptyMsg }) => {
    if (!items || items.length === 0) {
        return <div className="text-sm text-slate-500 italic p-4 text-center border border-white/5 rounded-lg border-dashed">{emptyMsg}</div>
    }
    return (
        <div className="overflow-hidden rounded-lg border border-white/5">
            <table className="w-full text-sm text-left">
                <thead className="bg-white/5 text-slate-400 uppercase text-xs font-bold">
                    <tr>
                        <th className="px-4 py-2">Task Type</th>
                        <th className="px-4 py-2 text-right">Count</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                    {items.map((item, i) => (
                        <tr key={i} className="hover:bg-white/5">
                            <td className="px-4 py-2 text-slate-300 font-mono">{item.endpoint_name}</td>
                            <td className="px-4 py-2 text-right text-white font-bold">{item.pending_count}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}

const WorkerRow = ({ worker }) => {
    return (
        <div className="bg-slate-900/50 border border-white/10 rounded-lg p-4">
            <div className="flex flex-col md:flex-row justify-between md:items-center gap-4 mb-4">
                 <div className="flex items-center gap-3">
                     <div className={clsx("w-3 h-3 rounded-full", worker.status === 'Active' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-red-500')}></div>
                     <div>
                         <div className="text-sm font-bold text-white">{worker.name}</div>
                         <div className="text-xs text-slate-500 font-mono">PID: {worker.pid} | Concurrency: {worker.concurrency}</div>
                     </div>
                 </div>
                 <div className="flex gap-4 text-xs">
                     <div className="bg-blue-500/10 text-blue-400 px-3 py-1 rounded border border-blue-500/20">
                         Active: <b>{worker.active_count}</b>
                     </div>
                     <div className="bg-orange-500/10 text-orange-400 px-3 py-1 rounded border border-orange-500/20">
                         Reserved: <b>{worker.reserved_count}</b>
                     </div>
                     <div className="bg-slate-700/50 text-slate-400 px-3 py-1 rounded border border-white/10">
                         Processed: <b>{worker.processed.toLocaleString()}</b>
                     </div>
                 </div>
            </div>

            {/* Active Tasks Detail */}
            {worker.active_tasks && worker.active_tasks.length > 0 && (
                 <div className="space-y-2 mt-2 bg-black/20 p-3 rounded border border-white/5">
                     <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-2">Processing Now</div>
                     {worker.active_tasks.map((task) => (
                         <div key={task.id} className="flex justify-between items-center text-xs border-b border-white/5 last:border-0 pb-1 last:pb-0">
                             <span className="text-slate-300 truncate max-w-[60%]">{task.name}</span>
                             <div className="flex items-center gap-2">
                                {task.enriched_name && <span className="text-brand-400 font-bold">{task.enriched_name}</span>}
                                {task.enriched_info && <span className="text-slate-500 italic">({task.enriched_info})</span>}
                             </div>
                         </div>
                     ))}
                 </div>
            )}
        </div>
    )
}

export default ManagementCelery;
