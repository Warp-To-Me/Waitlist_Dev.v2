import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Shield, Info, LogIn, CheckCircle } from 'lucide-react';

const LoginPage = () => {
    const [baseScopes, setBaseScopes] = useState([]);
    const [optionalScopes, setOptionalScopes] = useState([]);
    const [selectedScopes, setSelectedScopes] = useState(new Set());
    const [loading, setLoading] = useState(true);
    const [redirecting, setRedirecting] = useState(false);
    
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const mode = searchParams.get('mode');

    // Helper to get cookie for CSRF
    const getCookie = (name) => {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    useEffect(() => {
        fetch('/auth/login-options/')
            .then(res => res.json())
            .then(data => {
                setBaseScopes(data.base_scopes || []);
                setOptionalScopes(data.optional_scopes || []);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load scopes", err);
                setLoading(false);
            });
    }, []);

    const handleLogin = (useCustom) => {
        setRedirecting(true);
        
        let scopesToSend = [];
        if (useCustom) {
            scopesToSend = Array.from(selectedScopes);
        }

        fetch('/auth/login-options/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                scopes: scopesToSend,
                mode: mode // Pass mode to backend
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.redirect_url) {
                window.location.href = data.redirect_url;
            } else {
                setRedirecting(false);
                alert("Failed to get login URL");
            }
        })
        .catch(err => {
            console.error(err);
            setRedirecting(false);
        });
    };

    const toggleScope = (scope) => {
        const next = new Set(selectedScopes);
        if (next.has(scope)) {
            next.delete(scope);
        } else {
            next.add(scope);
        }
        setSelectedScopes(next);
    };

    if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500 animate-pulse">Loading login options...</div>;

    return (
        <div className="min-h-screen flex items-center justify-center p-4">
            <div className="glass-panel w-full max-w-2xl p-0 overflow-hidden relative flex flex-col max-h-[85vh]">
                {/* Header */}
                <div className="p-8 bg-gradient-to-br from-brand-900/50 to-transparent border-b border-white/5 shrink-0">
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        <Shield className="text-brand-500" size={32} />
                        Login Configuration
                    </h1>
                    <p className="text-slate-400 mt-2">
                        Customize the permissions you grant to this application. 
                    </p>
                </div>

                <div className="p-8 space-y-8 overflow-y-auto custom-scrollbar flex-1">
                    {/* Base Scopes */}
                    <div>
                        <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-brand-500"></span>
                            Required Permissions
                        </h3>
                        <div className="space-y-3">
                            {baseScopes.map(s => (
                                <div key={s.scope} className="flex items-start gap-3 p-1.5 rounded-lg bg-white/5 border border-white/5 opacity-75 cursor-not-allowed">
                                    <div className="mt-0.5 text-brand-500">
                                        <CheckCircle size={18} fill="currentColor" className="text-black" />
                                    </div>
                                    <div>
                                        <div className="font-bold text-slate-300 text-sm">{s.label}</div>
                                        <div className="text-xs text-slate-500">{s.description}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Optional Scopes */}
                    <div>
                        <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                            Optional Permissions
                        </h3>
                        <div className="grid grid-cols-1 gap-3">
                            {optionalScopes.map(s => (
                                <label key={s.scope} className="flex items-start gap-3 p-1.5 rounded-lg bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/20 transition cursor-pointer group">
                                    <div className="relative flex items-center mt-0.5">
                                        <input 
                                            type="checkbox" 
                                            className="peer appearance-none w-5 h-5 rounded border border-slate-600 bg-black checked:bg-blue-500 checked:border-blue-500 transition"
                                            checked={selectedScopes.has(s.scope)}
                                            onChange={() => toggleScope(s.scope)}
                                        />
                                        <CheckCircle size={14} className="absolute inset-0 m-auto text-white pointer-events-none opacity-0 peer-checked:opacity-100" />
                                    </div>
                                    <div>
                                        <div className="font-bold text-slate-300 group-hover:text-white text-sm transition">{s.label}</div>
                                        <div className="text-xs text-slate-500">{s.description}</div>
                                    </div>
                                </label>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Actions */}
                <div className="p-6 bg-black/20 border-t border-white/5 flex flex-col sm:flex-row gap-4 justify-between items-center shrink-0">
                    <button 
                        onClick={() => handleLogin(false)}
                        disabled={redirecting}
                        className="text-slate-400 hover:text-white text-sm font-bold px-4 py-2 rounded hover:bg-white/5 transition"
                    >
                        Login with Base Only
                    </button>

                    <button 
                        onClick={() => handleLogin(true)}
                        disabled={redirecting}
                        className="btn-primary px-8 py-3 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {redirecting ? (
                            <>Connecting to EVE SSO...</>
                        ) : (
                            <>
                                <LogIn size={18} />
                                Login with Selected
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;
