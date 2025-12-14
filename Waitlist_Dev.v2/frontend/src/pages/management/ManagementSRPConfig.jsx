import React, { useEffect, useState } from 'react';
import { RefreshCw, Key, LogIn } from 'lucide-react';

const ManagementSRPConfig = () => {
    const [config, setConfig] = useState(null);
    const [userChars, setUserChars] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = () => {
        fetch('/api/management/srp/config/')
            .then(res => res.json())
            .then(data => {
                setConfig(data.config);
                setUserChars(data.user_chars);
            });
    };

    const selectSource = (charId) => {
        if (!confirm("Set this character as the global SRP source? This will effect all wallet data.")) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];

        fetch('/api/management/srp/set_source/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ character_id: charId })
        }).then(res => res.json()).then(data => {
            if (data.success) fetchData();
            else alert("Error: " + data.error);
        });
    };

    const syncWallet = () => {
        setLoading(true);
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch('/api/management/srp/sync/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf }
        }).then(res => res.json()).then(data => {
            alert(data.message);
            setLoading(false);
            fetchData();
        });
    };

    return (
        <div className="flex flex-col gap-6">
            <div className="border-b border-white/5 pb-6">
                <h1 className="heading-1">SRP Configuration</h1>
                <p className="text-slate-400 text-sm mt-1">Designate the character used to pull Corporation Wallet data.</p>
            </div>

            {/* Active Config Card */}
            <div className="glass-panel p-6">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="label-text mb-0">Current Source</h3>
                    {config?.character ? (
                        <span className="badge badge-green">Active</span>
                    ) : (
                        <span className="badge badge-red">Not Configured</span>
                    )}
                </div>

                {config ? (
                    <>
                        <div className="flex items-center gap-4 mb-6">
                            <img
                                src={`https://images.evetech.net/characters/${config.character.character_id}/portrait?size=128`}
                                className="w-16 h-16 rounded-lg border-2 border-brand-500 shadow-[0_0_15px_rgba(245,158,11,0.3)]"
                                alt=""
                            />
                            <div>
                                <h2 className="text-xl font-bold text-white">{config.character.character_name}</h2>
                                <p className="text-slate-400 text-xs">Last Sync: {config.last_sync ? new Date(config.last_sync).toLocaleString() : "Never"}</p>
                                <div className="text-xs text-slate-500 mt-1">Corp ID: {config.character.corporation_id}</div>
                            </div>
                        </div>

                        <div className="flex gap-2">
                            <button onClick={syncWallet} disabled={loading} className="btn-primary text-xs py-2 px-4 shadow-brand-500/20">
                                {loading ? "Syncing..." : "🔄 Force Sync Now"}
                            </button>
                            <a href="/srp/auth/" className="btn-secondary text-xs py-2 px-4 border-amber-500/30 text-amber-400 hover:bg-amber-500/10">
                                <Key size={14} /> Update Token (Re-Auth)
                            </a>
                        </div>
                    </>
                ) : (
                    <>
                        <p className="text-slate-500 italic mb-4">No character selected.</p>
                        <div>
                            <a href="/srp/auth/" className="btn-primary text-xs py-2 px-6 inline-flex gap-2">
                                <LogIn size={14} /> Log In New Character with Wallet Scopes
                            </a>
                        </div>
                    </>
                )}
            </div>

            {/* Selection Form */}
            <div className="glass-panel p-6">
                <h3 className="label-text mb-4">Change Source Character</h3>
                <p className="text-xs text-slate-400 mb-4 bg-blue-900/20 p-3 rounded border border-blue-500/30">
                    ℹ️ The selected character MUST have the <strong>Accountant</strong> or <strong>Junior Accountant</strong> role in-game,
                    and must have logged in via the 'Update Token' button above to grant the <code>esi-wallet.read_corporation_wallets.v1</code> scope.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {userChars.map(char => (
                        <div
                            key={char.character_id}
                            onClick={() => selectSource(char.character_id)}
                            className="cursor-pointer bg-white/5 border border-white/5 hover:border-brand-500 hover:bg-white/10 p-3 rounded-lg flex items-center gap-3 transition group"
                        >
                            <img src={`https://images.evetech.net/characters/${char.character_id}/portrait?size=64`} className="w-10 h-10 rounded border border-slate-600 group-hover:border-white" alt="" />
                            <div>
                                <div className="font-bold text-slate-300 group-hover:text-white">{char.character_name}</div>
                                <div className="text-[10px] text-slate-500">{char.corporation_name}</div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default ManagementSRPConfig;