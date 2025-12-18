import React from 'react';
import { ShieldAlert, Lock, ArrowLeft } from 'lucide-react';
import { useSelector } from 'react-redux';
import { selectUser } from '../store/slices/authSlice';

const AccessDenied = () => {
    const user = useSelector(selectUser);

    return (
        <div className="absolute inset-0 flex items-center justify-center bg-dark-950 overflow-hidden">
            {/* Background Effects */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-500/10 rounded-full blur-[100px]"></div>
                <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-[100px]"></div>
            </div>

            <div className="relative z-10 max-w-md w-full p-6">
                <div className="glass-panel p-8 text-center border-red-500/20 shadow-2xl shadow-red-900/20 animate-fade-in">

                    <div className="mb-6 relative inline-block">
                        <div className="absolute inset-0 bg-red-500/20 blur-xl rounded-full"></div>
                        <div className="relative bg-dark-900 p-4 rounded-full border border-red-500/30 text-4xl text-red-500">
                            <ShieldAlert size={48} />
                        </div>
                    </div>

                    <h1 className="text-2xl font-bold text-white mb-2">Access Restricted</h1>
                    <p className="text-slate-400 mb-8 leading-relaxed">
                        You do not have the required security clearance to view this resource.
                        <br />
                        <span className="text-xs mt-2 block opacity-70">
                             Please authenticate your pilot credentials or contact fleet command if you believe this is an error.
                        </span>
                    </p>

                    <div className="flex flex-col gap-3">
                        {!user && (
                            <a href="/auth/login" className="btn-primary w-full py-3 justify-center text-base shadow-brand-500/20 group">
                                <span className="group-hover:scale-110 transition mr-2">🚀</span>
                                Log In via EVE Online
                            </a>
                        )}
                        <a href="/" className="btn-secondary w-full justify-center flex items-center gap-2">
                            <ArrowLeft size={16} /> Return to Dashboard
                        </a>
                    </div>

                </div>

                <div className="mt-8 text-center">
                    <p className="text-xs text-slate-600 font-mono">SECURITY PROTOCOL 403-UNAUTHORIZED</p>
                </div>
            </div>
        </div>
    );
};

export default AccessDenied;