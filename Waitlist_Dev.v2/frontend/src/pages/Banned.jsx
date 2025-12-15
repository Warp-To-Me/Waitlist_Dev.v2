import React from 'react';
import { Ban, User } from 'lucide-react';

const Banned = ({ reason, expires, createdAt }) => {
    // If props aren't passed (e.g. direct nav), we might want to fetch them or show generic
    // For now, we'll assume the context might provide them or we just show a generic message if missing.
    
    return (
        <div className="min-h-screen flex items-center justify-center -mt-20">
            <div className="max-w-md w-full bg-slate-800 border border-slate-700 rounded-xl shadow-2xl p-8 text-center relative overflow-hidden">

                {/* Red Glow Background */}
                <div className="absolute top-0 left-0 w-full h-2 bg-red-600"></div>
                <div className="absolute -top-10 -left-10 w-32 h-32 bg-red-600/20 rounded-full blur-3xl pointer-events-none"></div>
                <div className="absolute -bottom-10 -right-10 w-32 h-32 bg-red-600/20 rounded-full blur-3xl pointer-events-none"></div>

                <div className="mb-6">
                    <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-red-900/30 text-red-500 mb-4 ring-1 ring-red-500/50">
                        <Ban size={40} />
                    </div>
                    <h1 className="text-3xl font-bold text-white mb-2">Account Banned</h1>
                    <p className="text-slate-400">Your access to the Waitlist Dashboard has been restricted.</p>
                </div>

                <div className="bg-slate-900/50 rounded-lg p-5 border border-slate-700 text-left space-y-3 mb-6">
                    <div>
                        <span className="text-xs text-slate-500 uppercase tracking-wide font-bold">Reason</span>
                        <p className="text-slate-200 mt-1">{reason || "Violation of Fleet Rules"}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <span className="text-xs text-slate-500 uppercase tracking-wide font-bold">Banned On</span>
                            <p className="text-slate-300 mt-1 text-sm">{createdAt ? new Date(createdAt).toLocaleDateString() : "Unknown"}</p>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase tracking-wide font-bold">Expires</span>
                            {expires ? (
                                <p className="text-yellow-400 mt-1 text-sm font-medium">{new Date(expires).toLocaleString()}</p>
                            ) : (
                                <p className="text-red-500 mt-1 text-sm font-bold">PERMANENT</p>
                            )}
                        </div>
                    </div>
                </div>

                <div className="text-sm text-slate-500">
                    If you believe this is an error, please contact a Fleet Commander or Administrator on Discord.
                </div>

                <div className="mt-6 pt-6 border-t border-slate-700">
                    <a href="/profile" className="flex items-center justify-center gap-2 w-full py-2 px-4 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors mb-3">
                        <User size={16} /> View My Profile
                    </a>
                </div>
            </div>
        </div>
    );
};

export default Banned;