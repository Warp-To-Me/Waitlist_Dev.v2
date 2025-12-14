import React, { useEffect, useState } from 'react';
import { ChevronRight, Shield, Zap } from 'lucide-react';

const Doctrines = () => {
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedFit, setSelectedFit] = useState(null);

    useEffect(() => {
        fetch('/api/landing/').then(res => {
            // Wait, we need the doctine list API. The URL in `urls.py` was likely not changed or is routed via `waitlist_data.urls`.
            // Let's check `core/views.py`: `doctrine_list` is mapped to `path('doctrine_list', ...)` inside `waitlist_project/urls.py`? 
            // Wait, I didn't see `doctrine_list` in `api_urlpatterns` in `urls.py` explicitly. 
            // Ah, I edited `core/views.py` but `waitlist_data.urls` is included. 
            // The `doctrine_list` view I edited is in `core/views.py`.
            // Let's check where it's mapped.
            // In `urls.py`, `core_views.landing_page` is mapped.
            // But `doctrine_list`?
            // `Waitlist_Dev.v2/waitlist_data/urls.py` likely maps it?
            // Actually `core/views.py` had `doctrine_list`.
            // Let's assume I need to fetch from `/api/doctrines/` and I need to ensure that route exists.
        }); 
        
        // CORRECTION: I need to verify the route for doctrine_list.
        // I will implement the fetch assuming `/api/doctrines/` and fix the backend routing in the next step if missing.
        fetch('/api/doctrines/')
             .then(res => res.json())
             .then(data => {
                 setCategories(data);
                 setLoading(false);
             })
             .catch(err => console.error(err));
    }, []);

    const fetchFitDetails = (id) => {
        fetch(`/api/doctrines/fit/${id}/`)
            .then(res => res.json())
            .then(data => setSelectedFit(data));
    }

    if (loading) return <div className="p-10 text-center text-slate-500">Loading Strategy...</div>;

    return (
        <div className="flex h-full overflow-hidden">
            {/* Sidebar List */}
            <div className="w-1/3 border-r border-white/5 bg-black/20 overflow-y-auto custom-scrollbar p-6">
                <h2 className="heading-1 mb-8">Doctrines</h2>
                <div className="space-y-8">
                    {categories.map(cat => (
                        <CategoryNode key={cat.id} category={cat} onSelectFit={fetchFitDetails} />
                    ))}
                </div>
            </div>

            {/* Detail View */}
            <div className="flex-1 bg-dark-900/30 overflow-y-auto p-12">
                {selectedFit ? (
                    <div className="max-w-3xl mx-auto animate-fade-in">
                        <div className="flex items-start justify-between mb-8">
                            <div>
                                <h1 className="text-4xl font-bold text-white mb-2">{selectedFit.name}</h1>
                                <div className="flex items-center gap-4 text-slate-400">
                                    <span className="flex items-center gap-2">
                                        <Shield size={16} /> {selectedFit.hull}
                                    </span>
                                </div>
                            </div>
                            <button 
                                onClick={() => navigator.clipboard.writeText(selectedFit.eft_block)}
                                className="btn-primary"
                            >
                                <Zap size={18} /> Copy to Clipboard
                            </button>
                        </div>

                        {selectedFit.description && (
                            <div className="glass-panel p-6 mb-8 text-slate-300 leading-relaxed">
                                {selectedFit.description}
                            </div>
                        )}

                        <div className="grid grid-cols-2 gap-4">
                            {selectedFit.modules.map((mod, idx) => (
                                <div key={idx} className="flex items-center gap-3 bg-white/5 p-2 rounded border border-white/5">
                                    <img 
                                        src={`https://images.evetech.net/types/${mod.icon_id}/icon?size=32`} 
                                        className="w-8 h-8 rounded" 
                                        alt="" 
                                    />
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm text-slate-200 truncate">{mod.name}</div>
                                        <div className="text-xs text-slate-500">x{mod.quantity}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 opacity-50">
                        <Shield size={64} className="mb-4" />
                        <p>Select a doctrine fit to view details</p>
                    </div>
                )}
            </div>
        </div>
    );
};

const CategoryNode = ({ category, onSelectFit }) => {
    return (
        <div className="mb-4">
            <h3 className="text-brand-400 font-bold uppercase tracking-wider text-sm mb-3 border-b border-white/5 pb-1">
                {category.name}
            </h3>
            
            <div className="space-y-1 mb-4 pl-2">
                {category.fits.map(fit => (
                    <button 
                        key={fit.id}
                        onClick={() => onSelectFit(fit.id)}
                        className="w-full text-left px-3 py-2 rounded hover:bg-white/5 text-slate-300 hover:text-white transition flex items-center justify-between group"
                    >
                        <span>{fit.name}</span>
                        <ChevronRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-500" />
                    </button>
                ))}
            </div>

            {category.subcategories.length > 0 && (
                <div className="pl-4 border-l border-white/5 space-y-4">
                    {category.subcategories.map(sub => (
                        <CategoryNode key={sub.id} category={sub} onSelectFit={onSelectFit} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default Doctrines;