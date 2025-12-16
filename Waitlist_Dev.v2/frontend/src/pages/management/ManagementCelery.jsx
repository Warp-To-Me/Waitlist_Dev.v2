import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RefreshCw } from 'lucide-react';
import clsx from 'clsx';
import { wsConnect, wsDisconnect } from '../../store/middleware/socketMiddleware';
import { selectCeleryStatus, selectSystemConnectionStatus } from '../../store/slices/systemSlice';

const ManagementCelery = () => {
    const dispatch = useDispatch();
    const data = useSelector(selectCeleryStatus);
    const status = useSelector(selectSystemConnectionStatus);
    const connected = status === 'connected';

    useEffect(() => {
        // Redux handles the connection logic
        dispatch(wsConnect('/ws/system/monitor/'));
        return () => {
            dispatch(wsDisconnect());
        };
    }, [dispatch]);

    // If we receive raw HTML, we render it. 
    // This supports the legacy "server-side rendered partial via websocket" pattern.
    if (data) {
        return (
            <div className="space-y-6">
                <div className="flex justify-between items-center border-b border-white/5 pb-6">
                    <div className="flex items-center gap-4">
                        <h1 className="heading-1">System Monitor</h1>
                        <span className={clsx("badge flex items-center gap-2 normal-case font-normal transition-all duration-300", connected ? "badge-green" : "badge-red")}>
                            <span className={clsx("w-2 h-2 rounded-full animate-pulse", connected ? "bg-green-500" : "bg-red-500")}></span> 
                            {connected ? "Live Stream" : "Connecting..."}
                        </span>
                    </div>
                    {/* Using window.location.reload() to hard refresh if needed, though Redux should keep it fresh */}
                    <button onClick={() => window.location.reload()} className="btn-secondary text-xs py-1.5 shadow-lg">
                        <RefreshCw size={16} /> Reload Page
                    </button>
                </div>
                
                <div dangerouslySetInnerHTML={{ __html: data }} className="space-y-8" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center border-b border-white/5 pb-6">
                <div className="flex items-center gap-4">
                    <h1 className="heading-1">System Monitor</h1>
                    <span className="badge badge-slate flex items-center gap-2 normal-case font-normal">
                        <span className="w-2 h-2 rounded-full bg-slate-500"></span> Connecting...
                    </span>
                </div>
            </div>
            <div className="p-12 text-center text-slate-500 italic">
                Waiting for stream...
            </div>
        </div>
    );
};

export default ManagementCelery;