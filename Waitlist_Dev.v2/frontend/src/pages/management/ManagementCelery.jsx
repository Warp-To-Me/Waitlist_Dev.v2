import React, { useEffect, useState, useRef } from 'react';
import { RefreshCw, Zap, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import clsx from 'clsx';

const ManagementCelery = () => {
    const [data, setData] = useState(null);
    const [connected, setConnected] = useState(false);
    const socketRef = useRef(null);

    const connectSocket = () => {
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const host = window.location.host; // In dev this might need adjustment if proxying
        // For development with proxy, we might need to target the backend port directly or configured proxy path
        // Assuming /ws/ is proxied correctly as per previous instructions
        const path = `${protocol}${host}/ws/system/monitor/`;

        if (socketRef.current) socketRef.current.close();

        socketRef.current = new WebSocket(path);

        socketRef.current.onopen = () => {
            console.log('System Monitor: Connected');
            setConnected(true);
        };

        socketRef.current.onmessage = (e) => {
            const msg = JSON.parse(e.data);
            if (msg.html) {
                // The django template sends HTML. We need to parse this or, ideally, the backend should send JSON data.
                // Since I cannot easily change the backend to send JSON without potentially breaking other things (though I could),
                // I will try to fetch the initial data via API if available, OR I will assume the user wants me to render the HTML string
                // But React rendering raw HTML is dangerous.

                // WAIT: The instructions are "update all new and existing react pages to show identical views".
                // If the backend sends HTML, I can use dangerouslySetInnerHTML, but it's not "React-y".
                // However, the backend code `core/consumers.py` likely sends this.

                // Let's look at `celery_status.html` again. It uses `partials/celery_content.html`.
                // If I want to implement this properly in React, I should probably expose a JSON endpoint or update the consumer to send JSON.
                // But the user said "Can you look at the old template html and update...".
                // Modifying the backend to support JSON for this might be out of scope or risky if I don't know the backend well.

                // HOWEVER: I can parse the HTML or better yet, just for this specific page, since it's an admin page,
                // maybe rendering the HTML blob is acceptable to ensure "identical view" without rewriting the backend logic.

                // Actually, the best approach for a "skilled software engineer" is to see if I can get the data as JSON.
                // If not, rendering the HTML is a fallback.

                // Let's try to render the HTML for now as it ensures 100% visual fidelity with the template logic
                // which calculates all the stats.
                setData(msg.html);
            }
        };

        socketRef.current.onclose = () => {
            console.log('System Monitor: Disconnected');
            setConnected(false);
            setTimeout(connectSocket, 3000);
        };
    };

    useEffect(() => {
        connectSocket();
        return () => {
            if (socketRef.current) socketRef.current.close();
        };
    }, []);

    // If we receive raw HTML, we render it.
    // This is a pragmatic choice to support the legacy "server-side rendered partial via websocket" pattern
    // without rewriting the complex `SystemMonitor` logic in Python to serialize to JSON today.
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
                    <button onClick={() => window.location.reload()} className="btn-secondary text-xs py-1.5 shadow-lg">
                        <RefreshCw size={16} /> Reload Page
                    </button>
                </div>

                {/*
                    Injecting the styles/scripts from the partial might be tricky.
                    The partial relies on Tailwind classes which are available globally.
                    It shouldn't contain scripts.
                */}
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