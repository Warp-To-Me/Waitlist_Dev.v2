import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Play, Square, RefreshCw, ChevronRight, X, Maximize2, AlertTriangle } from 'lucide-react';
import useWebSocket from 'react-use-websocket';
import { useDispatch, useSelector } from 'react-redux';
import { 
    fetchScripts, runScript, stopScript, 
    selectAvailableScripts, selectActiveScripts, selectScriptStatus 
} from '../../store/slices/scriptSlice';

// --- CONSOLE COMPONENT ---
// Keeps its own WebSocket state as it's a transient, high-frequency stream component
const ScriptConsole = ({ scriptId, scriptName, onClose }) => {
    const [logs, setLogs] = useState([]);
    const [status, setStatus] = useState('connecting');
    const scrollRef = useRef(null);
    const dispatch = useDispatch();
    
    // Construct WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host; 
    const wsUrl = `${protocol}//${host}/ws/management/scripts/${scriptId}/`;
    
    const { lastMessage } = useWebSocket(wsUrl, {
        shouldReconnect: () => true,
        reconnectAttempts: 10,
        reconnectInterval: 3000,
        onOpen: () => setStatus('connected'),
        onClose: () => setStatus('disconnected'),
    });

    useEffect(() => {
        if (lastMessage !== null) {
            try {
                const data = JSON.parse(lastMessage.data);
                if (data.type === 'log') {
                    setLogs(prev => [...prev, data.message]);
                } else if (data.type === 'status') {
                    setStatus(data.status);
                }
            } catch (e) {
                console.error("WS Parse Error", e);
            }
        }
    }, [lastMessage]);

    // Auto-scroll
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    const handleStop = async () => {
        if (!confirm('Are you sure you want to kill this process?')) return;
        await dispatch(stopScript(scriptId)).unwrap();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="bg-slate-900 border border-slate-700 w-full max-w-5xl h-[80vh] rounded-xl flex flex-col shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 bg-slate-800 border-b border-slate-700">
                    <div className="flex items-center gap-3">
                        <Terminal size={18} className="text-brand-400" />
                        <div>
                            <h3 className="text-white font-mono font-bold text-sm">{scriptName || 'Unknown Script'}</h3>
                            <div className="flex items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${status === 'connected' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                <span className="text-xs text-slate-400 uppercase tracking-wider">{status}</span>
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {status !== 'completed' && status !== 'failed' && (
                             <button 
                                onClick={handleStop}
                                className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 rounded text-xs font-bold transition"
                            >
                                <Square size={14} /> STOP
                            </button>
                        )}
                        <button onClick={onClose} className="p-1 hover:bg-white/10 rounded text-slate-400 hover:text-white transition">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Terminal Window */}
                <div 
                    ref={scrollRef}
                    className="flex-grow bg-black p-4 overflow-y-auto font-mono text-xs md:text-sm text-green-400 leading-relaxed custom-scrollbar"
                >
                    {logs.length === 0 && <span className="text-slate-600 italic">Connecting to console stream...</span>}
                    {logs.map((line, i) => (
                        <div key={i} className="whitespace-pre-wrap break-all">{line}</div>
                    ))}
                </div>
            </div>
        </div>
    );
};


const ManagementScripts = () => {
    const dispatch = useDispatch();
    const scripts = useSelector(selectAvailableScripts) || [];
    const activeScripts = useSelector(selectActiveScripts) || [];
    const status = useSelector(selectScriptStatus);
    const error = useSelector(state => state.scripts.error);
    
    // Modal State
    const [selectedScript, setSelectedScript] = useState(null);
    const [argsInput, setArgsInput] = useState('');
    const [consoleOpen, setConsoleOpen] = useState(false);
    const [activeConsoleId, setActiveConsoleId] = useState(null);
    const [activeConsoleName, setActiveConsoleName] = useState(null);

    useEffect(() => {
        dispatch(fetchScripts());
        const interval = setInterval(() => {
             dispatch(fetchScripts());
        }, 10000);
        return () => clearInterval(interval);
    }, [dispatch]);

    const openRunModal = (script) => {
        setSelectedScript(script);
        setArgsInput('');
    };

    const handleRun = async () => {
        if (!selectedScript) return;
        try {
            const resultAction = await dispatch(runScript({
                name: selectedScript.name,
                args: argsInput
            })).unwrap();
            
            // Open Console Immediately
            setActiveConsoleId(resultAction.script_id);
            setActiveConsoleName(selectedScript.name);
            setConsoleOpen(true);
            
            // Close Run Modal & Refresh
            setSelectedScript(null);
            dispatch(fetchScripts());

        } catch (e) {
            alert("Failed to start: " + e);
        }
    };

    const joinConsole = (s) => {
        setActiveConsoleId(s.id);
        setActiveConsoleName(s.name);
        setConsoleOpen(true);
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">System Scripts</h1>
                    <p className="text-slate-400">Run backend management commands directly from the dashboard.</p>
                </div>
                <button onClick={() => dispatch(fetchScripts())} className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition">
                    <RefreshCw size={20} className={status === 'loading' ? 'animate-spin' : ''} />
                </button>
            </div>

            {/* Error Message */}
            {status === 'failed' && (
                <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-center gap-3">
                    <AlertTriangle size={20} />
                    <span>Error loading scripts: {error || 'Unknown error'}</span>
                </div>
            )}

            {/* Active Scripts Banner */}
            {activeScripts && activeScripts.length > 0 && (
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Currently Running</h3>
                    <div className="space-y-2">
                        {activeScripts.map(s => (
                            <div key={s.id} className="flex items-center justify-between bg-slate-900/50 p-3 rounded-lg border border-slate-700/50">
                                <div className="flex items-center gap-3">
                                    <div className={`w-2 h-2 rounded-full ${s.status === 'running' ? 'bg-green-500 animate-pulse' : 'bg-slate-500'}`} />
                                    <div>
                                        <span className="text-white font-mono font-bold">{s.name}</span>
                                        <span className="text-slate-500 text-xs ml-2 font-mono">{s.args}</span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-slate-400 mr-2">{s.status}</span>
                                    <button 
                                        onClick={() => joinConsole(s)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-500/10 text-brand-400 hover:bg-brand-500/20 border border-brand-500/20 rounded text-xs font-bold transition"
                                    >
                                        <Terminal size={14} /> Console
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Script Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {status === 'loading' && (!scripts || scripts.length === 0) ? (
                    <div className="text-slate-500 col-span-full py-10 text-center">Loading scripts...</div>
                ) : (scripts || []).length === 0 && status === 'succeeded' ? (
                    <div className="text-slate-500 col-span-full py-10 text-center flex flex-col items-center gap-2">
                        <Terminal size={32} className="opacity-20" />
                        <span>No management scripts found in core/waitlist_data.</span>
                    </div>
                ) : (scripts || []).map(script => (
                    <div key={script.name} className="group bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/20 rounded-xl p-5 transition flex flex-col h-full">
                        <div className="flex items-start justify-between mb-3">
                            <div className="p-2 bg-slate-900 rounded-lg text-brand-400 border border-white/5">
                                <Terminal size={20} />
                            </div>
                            <span className="text-[10px] font-bold bg-slate-800 text-slate-400 px-2 py-1 rounded border border-white/5">
                                {script.app}
                            </span>
                        </div>
                        <h3 className="text-white font-bold text-lg mb-1">{script.name}</h3>
                        <p className="text-slate-400 text-sm mb-4 flex-grow line-clamp-3">{script.help}</p>
                        
                        <button 
                            onClick={() => openRunModal(script)}
                            className="w-full py-2 bg-brand-600 hover:bg-brand-500 text-white font-bold rounded-lg transition flex items-center justify-center gap-2 group-hover:shadow-lg group-hover:shadow-brand-500/20"
                        >
                            <Play size={16} /> Run Script
                        </button>
                    </div>
                ))}
            </div>

            {/* Run Modal */}
            {selectedScript && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                    <div className="bg-slate-900 border border-slate-700 w-full max-w-lg rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
                        <div className="p-6">
                            <h2 className="text-xl font-bold text-white mb-2">Run <span className="font-mono text-brand-400">{selectedScript.name}</span></h2>
                            <p className="text-slate-400 text-sm mb-6">Configure arguments for this command.</p>
                            
                            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Arguments (Optional)</label>
                            <input 
                                type="text" 
                                value={argsInput}
                                onChange={(e) => setArgsInput(e.target.value)}
                                placeholder="e.g. --days 30 --force"
                                className="w-full bg-black/50 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition font-mono text-sm mb-6"
                            />
                            
                            <div className="flex items-center gap-3">
                                <button 
                                    onClick={() => setSelectedScript(null)}
                                    className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-lg transition"
                                >
                                    Cancel
                                </button>
                                <button 
                                    onClick={handleRun}
                                    className="flex-1 py-2.5 bg-brand-600 hover:bg-brand-500 text-white font-bold rounded-lg transition flex items-center justify-center gap-2"
                                >
                                    <Play size={16} /> Execute
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Console Modal */}
            {consoleOpen && activeConsoleId && (
                <ScriptConsole 
                    scriptId={activeConsoleId} 
                    scriptName={activeConsoleName} 
                    onClose={() => { setConsoleOpen(false); setActiveConsoleId(null); }} 
                />
            )}
        </div>
    );
};

export default ManagementScripts;
