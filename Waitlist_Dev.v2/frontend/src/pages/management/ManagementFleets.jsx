import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Plus, Settings, Scroll, ExternalLink, Trash, Power } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
    fetchFleetList, closeFleet, deleteFleet,
    selectFleetList, selectCanViewAdmin
} from '../../store/slices/fleetSlice';

const ManagementFleets = () => {
    const dispatch = useDispatch();
    const fleets = useSelector(selectFleetList);
    const canViewAdmin = useSelector(selectCanViewAdmin);

    useEffect(() => {
        dispatch(fetchFleetList());
    }, [dispatch]);

    const handleAction = (action, fleetId) => {
        const msg = action === 'close' 
            ? 'Are you sure you want to close this fleet?' 
            : 'DELETE this fleet record? This cannot be undone.';
        
        if (!confirm(msg)) return;

        if (action === 'close') {
            dispatch(closeFleet(fleetId))
                .unwrap()
                .catch(err => alert(err));
        } else if (action === 'delete') {
            dispatch(deleteFleet(fleetId))
                .unwrap()
                .catch(err => alert(err));
        }
    };

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-white/5 pb-6">
                <h1 className="heading-1">Active & Recent Fleets</h1>
                <Link to="/management/fleets/setup" className="btn-primary text-sm shadow-lg shadow-brand-500/20 flex items-center gap-2">
                    <Plus size={16} /> Create Fleet
                </Link>
            </div>

            {/* Fleet List */}
            <div className="glass-panel p-6">
                {fleets.length > 0 ? (
                    <ul className="space-y-4">
                        {fleets.map(fleet => (
                            <li key={fleet.id} className="p-4 bg-white/5 rounded-xl border border-white/5 flex flex-col md:flex-row justify-between md:items-center gap-4 group hover:bg-white/10 transition duration-300">
                                <div className="flex items-center gap-4">
                                    <div className="bg-dark-900 p-3 rounded-lg border border-white/10 text-2xl group-hover:scale-110 transition">
                                        🛸
                                    </div>
                                    <div>
                                        <h3 className="font-bold text-lg text-white flex items-center gap-3">
                                            {fleet.name}
                                            {fleet.is_active ? (
                                                <span className="badge badge-green flex items-center gap-1 normal-case px-2">
                                                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span>
                                                    Active
                                                </span>
                                            ) : (
                                                <span className="badge badge-slate text-xs">CLOSED</span>
                                            )}
                                        </h3>
                                        <div className="text-sm text-slate-400 flex gap-4 mt-1 font-mono text-xs items-center">
                                            <span>FC: <strong className="text-slate-200">{fleet.commander_name}</strong></span>
                                            <span className="opacity-50">|</span>
                                            <span>{new Date(fleet.created_at).toLocaleString()}</span>
                                            {fleet.esi_fleet_id && (
                                                <>
                                                    <span className="opacity-50">|</span>
                                                    <span className="bg-black/30 px-1.5 py-0.5 rounded text-slate-500 border border-white/5">ID: {fleet.esi_fleet_id}</span>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-3">
                                    {fleet.is_active && (
                                        <Link 
                                            to={`/management/fleets/${fleet.join_token}/settings`}
                                            className="btn-secondary py-1.5 px-3 text-xs inline-flex items-center gap-2 border-brand-500/30 text-brand-400 hover:bg-brand-500/10"
                                        >
                                            <Settings size={14} /> Manage
                                        </Link>
                                    )}

                                    <Link 
                                        to={`/management/fleets/${fleet.join_token}/history`}
                                        className="btn-secondary py-1.5 px-3 text-xs inline-flex items-center gap-2 border-slate-600 hover:border-white/50 text-slate-300 hover:text-white"
                                        title="View Audit Log"
                                    >
                                        <Scroll size={14} /> History
                                    </Link>

                                    {fleet.is_active ? (
                                        <>
                                            <Link 
                                                to={`/fleet/${fleet.join_token}`}
                                                className="btn-success py-1.5 px-3 text-xs inline-flex items-center gap-2"
                                            >
                                                <ExternalLink size={14} /> Open Board
                                            </Link>
                                            <button 
                                                onClick={() => handleAction('close', fleet.id)}
                                                className="btn-secondary py-1.5 px-3 text-xs text-brand-400 border-brand-500/30 hover:bg-brand-500/10 hover:border-brand-500/50 flex items-center gap-2"
                                            >
                                                <Power size={14} /> Close Fleet
                                            </button>
                                        </>
                                    ) : (
                                        canViewAdmin && (
                                            <button 
                                                onClick={() => handleAction('delete', fleet.id)}
                                                className="text-red-500 hover:text-red-400 text-xs underline px-2 transition font-bold flex items-center gap-1"
                                            >
                                                <Trash size={12} /> Delete
                                            </button>
                                        )
                                    )}
                                </div>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <div className="text-center py-16 text-slate-500 border-2 border-dashed border-white/10 rounded-xl bg-white/5">
                        <div className="text-4xl mb-4 grayscale opacity-30">📡</div>
                        <p className="mb-2 font-bold text-slate-400">No fleets recorded.</p>
                        <p className="text-sm">Create a fleet to start a waitlist session.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ManagementFleets;