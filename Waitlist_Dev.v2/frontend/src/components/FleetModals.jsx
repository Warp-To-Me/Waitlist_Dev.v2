import React, { useState, useEffect } from 'react';
import { apiCall } from '../utils/api';
import clsx from 'clsx';
import { useSelector } from 'react-redux';
import { selectUser } from '../store/slices/authSlice';

// --- X-UP MODAL ---

export const XUpModal = ({ isOpen, onClose, fleetToken }) => {
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);
    const [availableChars, setAvailableChars] = useState([]);
    const { user } = useSelector(selectUser) || {};

    // Fetch available characters for the user when modal opens
    useEffect(() => {
        if (isOpen && user) {
            // In a real app we might fetch from API or use Redux profile data
            // Assuming we can get them from profile or a specific endpoint
            // For now, let's assume we fetch them
            apiCall('/api/profile/')
                .then(r => r.json())
                .then(data => {
                    // Combine main + alts
                    const chars = [data.main_character, ...(data.alts || [])].filter(Boolean);
                    setAvailableChars(chars);
                })
                .catch(console.error);
        }
    }, [isOpen, user]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSubmitting(true);
        const formData = new FormData(e.target);

        try {
            const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
            // The legacy form sends 'character_id' as a list if multiple selected
            // We need to handle that.

            const res = await apiCall(`/fleet/${fleetToken}/join/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf },
                body: formData // Send as FormData to handle multiple checkboxes
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
            <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
                <h2 className="heading-2 mb-4 flex items-center gap-2">
                    <span>🚀</span> Join Waitlist
                </h2>

                <form onSubmit={handleSubmit} id="xup-form">
                    <div className="mb-4">
                        <label className="label-text mb-2">Select Pilot(s)</label>
                        <div className="space-y-2 max-h-60 overflow-y-auto custom-scrollbar p-1">
                            {availableChars.length > 0 ? availableChars.map(char => (
                                <label key={char.character_id} className="flex items-center gap-3 p-2 bg-white/5 hover:bg-white/10 rounded border border-white/5 cursor-pointer transition group">
                                    <input type="checkbox" name="character_id" value={char.character_id} className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-brand-500/50" />
                                    <img src={`https://images.evetech.net/characters/${char.character_id}/portrait?size=64`} className="w-8 h-8 rounded border border-white/10" alt="" />
                                    <div>
                                        <div className="font-bold text-sm text-slate-200 group-hover:text-white">{char.character_name}</div>
                                        <div className="text-[10px] text-slate-500">{char.corporation_name}</div>
                                    </div>
                                </label>
                            )) : (
                                <div className="text-slate-500 text-sm italic">Loading pilots...</div>
                            )}
                        </div>
                    </div>

                    {error && <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded">{error}</div>}

                    <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
                        <button type="button" onClick={onClose} className="btn-ghost text-sm">Cancel</button>
                        <button type="submit" disabled={submitting} className="btn-primary px-6 py-2 shadow-lg shadow-brand-500/20">
                            {submitting ? "Submitting..." : "Submit Fit(s)"}
                        </button>
                    </div>
                </form>
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
            const res = await apiCall(`/fleet/entry/${entryId}/update/`, {
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
