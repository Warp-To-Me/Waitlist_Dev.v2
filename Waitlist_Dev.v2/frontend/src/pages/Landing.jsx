import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LogIn } from 'lucide-react';

const Landing = () => {
    const [fleets, setFleets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        fetch('/api/landing/')
            .then(res => res.json())
            .then(data => {
                if (data.should_redirect && data.redirect_token) {
                    navigate(`/fleet/${data.redirect_token}`);
                }
                setFleets(data.active_fleets || []); // Template uses active_fleets
                setIsAuthenticated(data.is_authenticated); // Assuming API returns this
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, [navigate]);

    if (loading) return <div className="p-10 text-center animate-pulse text-slate-500">Loading...</div>;

    return (
        <div className="absolute inset-0 overflow-y-auto custom-scrollbar">
            <div className="container mx-auto p-8 flex flex-col items-center justify-center text-center min-h-[80vh]">
                <div className="mb-12 relative">
                    <div className="absolute -inset-10 bg-brand-500/20 blur-[100px] rounded-full pointer-events-none"></div>
                </div>

                {isAuthenticated ? (
                    <div className="w-full max-w-4xl space-y-6 relative z-10">
                        <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-6">
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                <span className="text-brand-500">📡</span> Fleets
                            </h2>
                            <span className="badge badge-brand">{fleets.length} Detected</span>
                        </div>

                        {fleets.length > 0 ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left">
                                {fleets.map(fleet => (
                                    <Link
                                        key={fleet.id}
                                        to={`/fleet/${fleet.join_token}`}
                                        className="glass-panel p-6 group hover:border-brand-500/50 transition duration-300 relative overflow-hidden"
                                    >
                                        <div className="absolute inset-0 bg-brand-500/0 group-hover:bg-brand-500/5 transition duration-500"></div>

                                        <div className="flex justify-between items-start mb-4 relative z-10">
                                            <div>
                                                <h3 className="text-xl font-bold text-white group-hover:text-brand-400 transition">{fleet.name}</h3>
                                                <p className="text-sm text-slate-400 mt-1">FC: <span className="text-slate-200 font-semibold">{fleet.fc_name}</span></p>
                                            </div>
                                            <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse shadow-[0_0_10px_rgba(34,197,94,0.6)]"></div>
                                        </div>

                                        <div className="flex justify-between items-center relative z-10 mt-6">
                                            <span className="badge badge-slate flex items-center gap-1">
                                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                                {new Date(fleet.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                            </span>
                                            <span className="text-brand-400 text-sm font-bold flex items-center gap-1 opacity-0 group-hover:opacity-100 transition transform translate-x-2 group-hover:translate-x-0">
                                                Join Fleet <span className="text-lg">→</span>
                                            </span>
                                        </div>
                                    </Link>
                                ))}
                            </div>
                        ) : (
                            <div className="glass-panel p-12 flex flex-col items-center justify-center text-slate-500 border-dashed border-2 border-slate-800 bg-transparent">
                                <div className="text-5xl mb-4 grayscale opacity-30">🛸</div>
                                <h3 className="text-xl font-bold text-slate-400">No Fleets Active</h3>
                                <p className="mt-2 text-sm">Stand by for pings on Discord.</p>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="max-w-xl mx-auto space-y-8 relative z-10">
                        <div className="glass-panel p-8 border-brand-500/20">
                            <p className="text-slate-300 mb-8 leading-relaxed">
                                Authentication is required to access fleet services. <br/>Please log in using your primary EVE Online character.
                            </p>
                            <div className="flex justify-center">
                                <a href="/sso/login" data-no-spa className="btn-primary py-4 px-12 text-lg rounded-xl flex items-center gap-2">
                                    <LogIn size={24} />
                                    Log In with SSO
                                </a>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Landing;