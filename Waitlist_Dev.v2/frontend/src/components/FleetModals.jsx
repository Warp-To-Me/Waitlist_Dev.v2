import React, { useState, useEffect } from 'react';
import { apiCall } from '../utils/api';
import clsx from 'clsx';
import { useSelector } from 'react-redux';
import { selectUserChars } from '../store/slices/fleetSlice';

// --- X-UP MODAL ---

export const XUpModal = ({ isOpen, onClose, fleetToken }) => {
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);
    const availableChars = useSelector(selectUserChars);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSubmitting(true);
        const formData = new FormData(e.target);

        try {
            const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
            
            const res = await apiCall(`/api/fleet/${fleetToken}/xup/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf },
                body: formData 
            });
            
            const data = await res.json();
            if (data.success) {
                onClose();
            } else {
                setError(data.error);
            }
        } catch (err) {
            setError(err.message || "Network Error");
        } finally {
            setSubmitting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dark-950/80 backdrop-blur-sm" onClick={onClose}>
            <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl flex flex-col max-h-[85vh] w-full max-w-4xl" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="glass-header px-6 py-4 flex justify-between items-center shrink-0">
                    <h3 className="font-bold text-white text-lg">Join Waitlist</h3>
                    <button onClick={onClose} className="text-slate-400 hover:text-white">✕</button>
                </div>
                
                <form onSubmit={handleSubmit} id="xup-form" className="flex flex-col md:flex-row flex-grow overflow-hidden">
                    {/* LEFT: Fitting Paste */}
                    <div className="p-6 md:w-1/2 flex flex-col border-b md:border-b-0 md:border-r border-white/5">
                        <label className="label-text mb-2">Paste Fit(s)</label>
                        <div className="flex-grow relative h-48 md:h-auto">
                            <textarea 
                                name="eft_paste" 
                                className="w-full h-full bg-black/30 border border-white/10 rounded-lg p-3 text-[10px] font-mono text-slate-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500/50 outline-none resize-none leading-tight"
                                placeholder={`[Hull, Fit Name]...\n\nPaste multiple fits to submit multiple entries at once.`}
                                autoFocus
                            ></textarea>
                        </div>
                        {error && <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded">{error}</div>}
                    </div>

                    {/* RIGHT: Pilot Selection */}
                    <div className="p-6 md:w-1/2 bg-white/5 flex flex-col overflow-y-auto custom-scrollbar">
                        <h4 className="label-text mb-4">Select Pilot(s)</h4>
                        <div className="space-y-4">
                            {availableChars && availableChars.length > 0 ? availableChars.map(char => (
                                <div key={char.character_id} className="bg-black/20 rounded border border-white/5 p-3 hover:border-white/20 transition group">
                                    <label className="flex items-start gap-3 cursor-pointer mb-2">
                                        <input 
                                            type="checkbox" 
                                            name="character_id" 
                                            value={char.character_id} 
                                            className="mt-1 w-4 h-4 rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-brand-500/50 shrink-0" 
                                        />
                                        <div className="flex-grow min-w-0">
                                            <div className="flex items-center gap-2">
                                                <img src={`https://images.evetech.net/characters/${char.character_id}/portrait?size=32`} className="w-5 h-5 rounded-full border border-white/10" alt="" />
                                                <span className="text-sm font-bold text-slate-200 group-hover:text-white truncate">{char.character_name}</span>
                                                {/* Note: 'is_main' logic isn't explicit in dashboard API response for user_chars, check if needed. 
                                                    The dashboard API response DOES NOT explicitly send is_main in user_chars list, 
                                                    but the legacy template assumed it. 
                                                    We can skip the MAIN badge if not present or rely on frontend if critical. 
                                                    For now, matching API response fields.
                                                */}
                                            </div>
                                            {/* Implants Grid */}
                                            <div className="mt-2 pl-7">
                                                {char.active_implants && char.active_implants.length > 0 ? (
                                                    <div className="grid grid-cols-2 gap-1">
                                                        {char.active_implants.map(imp => (
                                                            <div key={imp.id} className="flex items-center gap-1.5 bg-white/5 px-1.5 py-0.5 rounded border border-white/5 overflow-hidden" title={imp.name}>
                                                                <img src={`https://images.evetech.net/types/${imp.id}/icon?size=32`} className="w-3 h-3 rounded-sm opacity-80 flex-shrink-0" alt="" />
                                                                <span className="text-[9px] text-slate-400 truncate leading-none">{imp.name}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <span className="text-[9px] text-slate-600 italic">No implants detected</span>
                                                )}
                                            </div>
                                        </div>
                                    </label>
                                </div>
                            )) : (
                                <div className="text-slate-500 text-sm italic">Loading pilots...</div>
                            )}
                        </div>
                    </div>
                </form>

                {/* Footer */}
                <div className="p-4 border-t border-white/5 bg-slate-900 flex justify-end shrink-0 gap-3">
                    <button type="button" onClick={onClose} className="btn-ghost text-sm">Cancel</button>
                    <button type="submit" form="xup-form" disabled={submitting} className="btn-primary py-2 px-8 shadow-lg shadow-brand-500/20">
                        {submitting ? "Submitting..." : "Submit Fit(s)"}
                    </button>
                </div>
            </div>
        </div>
    );
};

// --- UPDATE MODAL ---

export const UpdateModal = ({ isOpen, onClose, entryId }) => {
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSubmitting(true);
        const formData = new FormData(e.target);

        try {
            const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
            const res = await apiCall(`/api/fleet/entry/${entryId}/update/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf },
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                onClose();
            } else {
                setError(data.error);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setSubmitting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dark-950/80 backdrop-blur-sm" onClick={onClose}>
            <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl p-6 max-w-lg w-full" onClick={e => e.stopPropagation()}>
                <h2 className="heading-2 mb-1">Update Fit</h2>
                <p className="text-slate-500 text-sm mb-4">Paste your updated EFT fit below. This will refresh your waitlist entry.</p>

                <form onSubmit={handleSubmit}>
                    <textarea 
                        name="eft_text" 
                        rows="8" 
                        className="w-full bg-black/30 border border-white/10 rounded-lg p-3 text-xs font-mono text-slate-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500/50 outline-none mb-4"
                        placeholder="[Megathron, DPS]..."
                        autoFocus
                    ></textarea>

                    {error && <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded">{error}</div>}

                    <div className="flex justify-end gap-3">
                        <button type="button" onClick={onClose} className="btn-ghost text-sm">Cancel</button>
                        <button type="submit" disabled={submitting} className="btn-primary px-6 py-2">
                            {submitting ? "Updating..." : "Update Fit"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};
