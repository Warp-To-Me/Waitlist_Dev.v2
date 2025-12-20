import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RefreshCw, Server, Activity, Database, AlertCircle, CheckCircle, Clock, Zap } from 'lucide-react';
import clsx from 'clsx';
import { wsConnect, wsDisconnect } from '../../store/middleware/socketMiddleware';
import { selectCeleryStatus, selectSystemConnectionStatus, selectActiveTasks, pruneTasks } from '../../store/slices/systemSlice';

const ManagementCelery = () => {
    const dispatch = useDispatch();
    const data = useSelector(selectCeleryStatus); // Now contains the JSON object
    const tasks = useSelector(selectActiveTasks);
    const status = useSelector(selectSystemConnectionStatus);
    const connected = status === 'connected';

    // Prune completed tasks periodically to remove them from DOM
    useEffect(() => {
        const interval = setInterval(() => {
            dispatch(pruneTasks());
        }, 1000);
        return () => clearInterval(interval);
    }, [dispatch]);

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

    // Helper to format time ago
    const timeAgo = (isoString) => {
        if (!isoString) return 'Never';
        const diff = Date.now() - new Date(isoString).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 60) return `${mins}m ago`;
        const hours = Math.floor(mins / 60);
        return `${hours}h ago`;
    };

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
                        <StatBox label="Idle Tokens" value={data.expired_token_count} color="blue" />
                        <StatBox label="Stale Characters (>1h)" value={data.stale_count} color="yellow" />
                        <StatBox label="Active Users (30d)" value={data.active_site_30d} color="blue" />
                        <StatBox label="ESI API Status" value={data.esi_server_status ? "ONLINE" : "DOWN"} color={data.esi_server_status ? "green" : "red"} />
                    </div>
                </div>
            </div>

            {/* Operational Health Section */}
            <div className="glass-panel p-6">
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <div className="w-1 h-6 bg-blue-500 rounded-full"></div>
                    Operational Health
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatBox 
                        label="Active Fleets" 
                        value={data.active_fleets_count} 
                        color={data.active_fleets_count > 0 ? "green" : "blue"} 
                    />
                    <StatBox 
                        label="Pilots Waiting" 
                        value={data.pending_pilots_count} 
                        color={data.pending_pilots_count > 10 ? "yellow" : "blue"} 
                    />
                    <StatBox 
                        label="Active Pilots" 
                        value={data.active_pilots_count} 
                        color="purple" 
                    />
                    <StatBox 
                        label="Fleet Activity (30d)" 
                        value={data.active_waitlist_30d} 
                        color="purple" 
                    />
                    <StatBox 
                        label="Last SRP Sync" 
                        value={timeAgo(data.last_srp_sync)} 
                        color={(!data.last_srp_sync || timeAgo(data.last_srp_sync).includes('h') && parseInt(timeAgo(data.last_srp_sync)) > 24) ? "red" : "green"} 
                    />
                </div>
            </div>

            {/* Queued Breakdowns & Workers */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="glass-panel p-6">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <Clock size={20} className="text-yellow-400"/>
                        Queued Tasks (Immediate)
                    </h3>
                    <QueueTable items={data.queued_breakdown} emptyMsg="No tasks currently queued." />
                </div>

                {/* Workers List */}
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

            {/* Real-time Task Stream */}
            <div className="glass-panel p-6">
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <Zap size={20} className="text-blue-400"/>
                        Live Task Stream
                </h3>

                <div className="space-y-2 h-[400px] overflow-y-auto pr-2 custom-scrollbar relative">
                    {tasks.length === 0 && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 italic">
                            <Activity className="mb-2 opacity-50" />
                            No active tasks processed recently.
                        </div>
                    )}

                    {tasks.map((task) => (
                        <TaskRow key={task.id} task={task} />
                    ))}
                </div>
            </div>
        </div>
    );
};

// --- Sub Components ---

const WorkerRow = ({ worker }) => {
    return (
        <div className="bg-slate-900/50 border border-white/10 rounded-lg p-4">
            <div className="flex flex-col md:flex-row justify-between md:items-center gap-4">
                 <div className="flex items-center gap-3">
                     <div className={clsx("w-3 h-3 rounded-full", worker.status === 'Active' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-red-500')}></div>
                     <div>
                         <div className="text-sm font-bold text-white">{worker.name}</div>
                         <div className="text-xs text-slate-500 font-mono">PID: {worker.pid} | Concurrency: {worker.concurrency}</div>
                     </div>
                 </div>
                 <div className="flex gap-4 text-xs">
                     <div className="bg-slate-700/50 text-slate-400 px-3 py-1 rounded border border-white/10">
                         Processed: <b>{worker.processed.toLocaleString()}</b>
                     </div>
                 </div>
            </div>
        </div>
    )
}

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

const TaskRow = ({ task }) => {
    const isFinished = !!task.finishedAt;
    const isSuccess = task.state === 'SUCCESS';
    const isFailure = task.state === 'FAILURE';

    return (
        <div
            className={clsx(
                "p-3 rounded-lg border transition-all duration-1000 flex items-center justify-between gap-4 text-xs",
                isFinished ? "opacity-0" : "opacity-100", // Fade out when finished
                isFailure ? "bg-red-500/10 border-red-500/20" :
                isSuccess ? "bg-green-500/10 border-green-500/20" :
                "bg-slate-800/50 border-white/5"
            )}
            style={{ transitionDuration: isFinished ? '5000ms' : '300ms' }}
        >
            <div className="flex items-center gap-3 overflow-hidden">
                <div className={clsx(
                    "w-2 h-2 rounded-full shrink-0",
                    isFailure ? "bg-red-500" :
                    isSuccess ? "bg-green-500" :
                    "bg-blue-400 animate-pulse"
                )}></div>
                <div className="flex flex-col overflow-hidden">
                    <div className="font-mono text-slate-300 truncate">{task.name}</div>
                    <div className="text-slate-500 flex gap-2 truncate">
                        <span>{task.id.slice(0, 8)}...</span>
                        {task.worker && <span>via {task.worker}</span>}
                    </div>
                </div>
            </div>

            {(task.enriched_name || task.enriched_info) && (
                 <div className="text-right shrink-0">
                    {task.enriched_name && <div className="font-bold text-brand-400">{task.enriched_name}</div>}
                    {task.enriched_info && <div className="text-slate-500 italic">{task.enriched_info}</div>}
                 </div>
            )}

            {isFinished && (
                <div className={clsx("font-bold uppercase tracking-wider text-[10px]", isSuccess ? "text-green-500" : "text-red-500")}>
                    {task.state}
                </div>
            )}
        </div>
    );
}

export default ManagementCelery;
