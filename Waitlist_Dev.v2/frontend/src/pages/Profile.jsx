import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const Profile = () => {
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        // Fetch profile data. In real app, /api/me gives basic info, but /api/profile/ gives full details.
        // We'll rely on /api/profile/ which maps to `profile_view` (now returning JSON).
        fetch('/api/profile/')
            .then(res => {
                if (res.status === 401) {
                    // Not logged in
                    window.location.href = '/auth/login/'; // Redirect to Django auth
                    return null;
                }
                return res.json();
            })
            .then(data => {
                if (data) {
                    setProfile(data);
                    setLoading(false);
                }
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    const handleSwitchChar = (charId) => {
        fetch(`/api/profile/switch/${charId}/`)
            .then(res => {
                if (res.ok) window.location.reload();
            });
    };

    if (loading) return <div className="p-10 text-center animate-pulse">Loading Pilot Data...</div>;

    if (!profile) return null;

    return (
        <div className="container mx-auto px-4 py-8 max-w-6xl">
            <h1 className="heading-1 mb-8">Pilot Profile</h1>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Active Pilot Card */}
                <div className="glass-panel p-6 lg:col-span-1 h-fit">
                    <div className="flex flex-col items-center text-center">
                        <div className="relative mb-4 group">
                             <img
                                src={`https://images.evetech.net/characters/${profile.active_char.character_id}/portrait?size=256`}
                                className="w-32 h-32 rounded-full border-4 border-slate-700 shadow-2xl group-hover:border-brand-500 transition"
                                alt="Active Pilot"
                             />
                             {profile.active_char.is_main && <span className="absolute bottom-0 right-0 badge badge-brand">MAIN</span>}
                        </div>
                        <h2 className="text-2xl font-bold text-white mb-1">{profile.active_char.character_name}</h2>
                        <div className="text-slate-400 text-sm mb-4">
                            {profile.active_char.corporation_name}
                            {profile.active_char.alliance_name && <span className="block text-xs text-slate-500">{profile.active_char.alliance_name}</span>}
                        </div>

                        {/* Stats Grid */}
                        <div className="grid grid-cols-3 gap-2 w-full mb-6 text-center">
                             <div className="bg-white/5 p-2 rounded">
                                <div className="text-[10px] uppercase text-slate-500 font-bold">Wallet</div>
                                <div className="text-xs font-mono text-brand-300 truncate">
                                    {(profile.totals.wallet / 1000000).toFixed(1)}M
                                </div>
                             </div>
                             <div className="bg-white/5 p-2 rounded">
                                <div className="text-[10px] uppercase text-slate-500 font-bold">LP</div>
                                <div className="text-xs font-mono text-green-300 truncate">
                                    {profile.totals.lp.toLocaleString()}
                                </div>
                             </div>
                             <div className="bg-white/5 p-2 rounded">
                                <div className="text-[10px] uppercase text-slate-500 font-bold">SP</div>
                                <div className="text-xs font-mono text-blue-300 truncate">
                                    {(profile.totals.sp / 1000000).toFixed(1)}M
                                </div>
                             </div>
                        </div>
                    </div>
                </div>

                {/* Character List */}
                <div className="glass-panel p-6 lg:col-span-2">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="text-xl font-bold text-white">Linked Characters</h3>
                        <a href="/auth/add_alt/" className="btn-secondary text-xs">
                            + Add Character
                        </a>
                    </div>

                    <div className="space-y-3">
                        {profile.characters.map(char => (
                            <div key={char.character_id} className={`flex items-center justify-between p-4 rounded-lg border transition ${char.character_id === profile.active_char.character_id ? 'bg-brand-900/10 border-brand-500/30' : 'bg-white/5 border-white/5 hover:border-slate-600'}`}>
                                <div className="flex items-center gap-4">
                                    <img src={`https://images.evetech.net/characters/${char.character_id}/portrait?size=64`} className="w-10 h-10 rounded shadow-md" alt="" />
                                    <div>
                                        <div className="font-bold text-white flex items-center gap-2">
                                            {char.character_name}
                                            {char.is_main && <span className="badge badge-brand">Main</span>}
                                        </div>
                                        <div className="text-xs text-slate-500">{char.corporation_name}</div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    {char.character_id !== profile.active_char.character_id && (
                                        <button onClick={() => handleSwitchChar(char.character_id)} className="btn-ghost text-xs">
                                            Switch To
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Profile;