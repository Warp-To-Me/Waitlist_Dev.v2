import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

const Landing = () => {
    const [fleets, setFleets] = useState([]);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        fetch('/api/landing/')
            .then(res => res.json())
            .then(data => {
                // Handle auto-redirect
                if (data.should_redirect && data.redirect_token) {
                    navigate(`/fleet/${data.redirect_token}`);
                }
                setFleets(data.fleets || []);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, [navigate]);

    if (loading) return <div className="p-10 text-center animate-pulse">Loading Operations...</div>;

    return (
        <div className="container mx-auto px-4 py-12 max-w-5xl">
            <div className="text-center mb-16 space-y-4">
                <h1 className="heading-1">
                    Fleet Operations
                </h1>
                <p className="text-slate-400 text-lg max-w-2xl mx-auto">
                    Active fleets are listed below. Click to join the waitlist or view fleet status.
                </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {fleets.length === 0 ? (
                    <div className="col-span-full text-center py-12 bg-white/5 rounded-2xl border border-white/10 border-dashed">
                        <div className="text-slate-500 font-mono mb-2 text-4xl">⚠</div>
                        <h3 className="text-xl font-bold text-slate-300">No Active Fleets</h3>
                        <p className="text-slate-500 text-sm mt-1">Check back later or wait for a ping.</p>
                    </div>
                ) : (
                    fleets.map(fleet => (
                        <Link 
                            key={fleet.id} 
                            to={`/fleet/${fleet.join_token}`}
                            className="glass-panel p-6 hover:bg-white/5 transition group relative overflow-hidden"
                        >
                            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition transform group-hover:scale-110">
                                <svg className="w-24 h-24 text-brand-500" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 19h20L12 2zm0 3l7.5 13h-15L12 5z"/></svg>
                            </div>

                            <div className="relative z-10">
                                <div className="flex justify-between items-start mb-4">
                                    <span className={`badge ${fleet.status === 'forming' ? 'badge-brand' : 'badge-green'}`}>
                                        {fleet.status.toUpperCase()}
                                    </span>
                                    <span className="text-xs font-mono text-slate-500">
                                        {new Date(fleet.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                    </span>
                                </div>

                                <h3 className="text-xl font-bold text-white mb-1 group-hover:text-brand-400 transition">
                                    {fleet.type}
                                </h3>
                                <div className="flex items-center gap-2 text-sm text-slate-400 mb-4">
                                    <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                                    <span>FC: <strong className="text-slate-300">{fleet.fc_name}</strong></span>
                                </div>

                                <div className="text-sm text-slate-400 line-clamp-2 min-h-[2.5em]">
                                    {fleet.description || "No description provided."}
                                </div>
                            </div>
                        </Link>
                    ))
                )}
            </div>
        </div>
    );
};

export default Landing;