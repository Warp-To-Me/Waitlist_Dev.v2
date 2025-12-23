import React, { useEffect, useState } from 'react';
import { Search, ChevronDown, ChevronRight, Copy, X } from 'lucide-react';

const Doctrines = () => {
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedFit, setSelectedFit] = useState(null);
    const [modalLoading, setModalLoading] = useState(false);

    useEffect(() => {
        // Assuming /api/doctrines/ is the correct endpoint for the public list
        fetch('/api/doctrines/')
            .then(res => res.json())
            .then(data => {
                setCategories(data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    const fetchFitDetails = (id) => {
        setModalLoading(true);
        setSelectedFit(null); // Clear previous or show loading state
        fetch(`/api/doctrines/fit/${id}/`) // Corrected endpoint matching urls.py
            .then(res => res.json())
            .then(data => {
                setSelectedFit(data);
                setModalLoading(false);
            })
            .catch(() => setModalLoading(false));
    };

    const closeModal = () => setSelectedFit(null);

    const copyToClipboard = () => {
        if (!selectedFit) return;
        navigator.clipboard.writeText(selectedFit.eft_format);
        alert("Copied to clipboard!");
    };

    if (loading) return <div className="p-10 text-center animate-pulse text-slate-500">Loading fittings...</div>;

    return (
        <div className="absolute inset-0 overflow-y-auto custom-scrollbar" id="doctrine-scroll-wrapper">
            <div className="container mx-auto p-4 md:p-8 pb-32">
                {/* Header */}
                <div className="flex flex-col md:flex-row justify-between items-end gap-6 mb-8 border-b border-white/5 pb-6">
                    <div>
                        <h1 className="heading-1">
                            <span className="text-brand-500">Doctrine</span> Fittings
                        </h1>
                        <p className="text-slate-400 text-sm mt-2 font-medium">
                            Approved fleet compositions. Click on a category to expand it.
                        </p>
                    </div>

                    {/* Search Bar */}
                    <div className="relative w-full md:w-96">
                        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                            <Search className="w-5 h-5 text-slate-500" />
                        </div>
                        <input 
                            type="text"
                            className="input-field pl-10"
                            placeholder="Search ship, fit name, or role..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                {/* Content Area */}
                <div id="doctrine-container" className="animate-fade-in space-y-4">
                    {categories.map(cat => (
                        <CategoryItem 
                            key={cat.id} 
                            category={cat} 
                            searchQuery={searchQuery} 
                            onSelectFit={fetchFitDetails} 
                        />
                    ))}
                </div>
            </div>

            {/* Fit Detail Modal */}
            {(selectedFit || modalLoading) && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dark-950/80 backdrop-blur-sm" onClick={closeModal}>
                    <div className="relative transform rounded-xl bg-slate-900 border border-white/10 shadow-2xl w-full max-w-2xl flex flex-col max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
                        
                        {/* Header */}
                        <div className="glass-header px-4 py-3 flex justify-between items-center shrink-0 bg-slate-900/95 z-20">
                            <div className="flex items-center gap-3">
                                {selectedFit && (
                                    <>
                                        <img src={`https://images.evetech.net/types/${selectedFit.hull_id}/icon?size=64`} className="w-10 h-10 rounded border border-white/10 bg-dark-900 shadow-lg" alt="" />
                                        <div>
                                            <h3 className="text-lg font-bold text-white tracking-tight leading-none">{selectedFit.hull}</h3>
                                            <p className="text-xs text-brand-500 font-mono mt-1">{selectedFit.name}</p>
                                        </div>
                                    </>
                                )}
                                {modalLoading && <div className="text-slate-400">Loading...</div>}
                            </div>
                            <button onClick={closeModal} className="text-slate-400 hover:text-white transition p-1 hover:bg-white/5 rounded-full">
                                <X size={20} />
                            </button>
                        </div>

                        {/* Content */}
                        {selectedFit && (
                            <div className="flex flex-col flex-grow overflow-hidden bg-dark-950 relative">
                                {/* Fitting Notes */}
                                <div className="px-4 py-3 bg-slate-900/50 border-b border-white/5 shrink-0">
                                    <h4 className="label-text mb-1 text-[10px]">Fitting Notes</h4>
                                    <p className="text-xs text-slate-400 leading-relaxed whitespace-pre-wrap font-sans max-h-24 overflow-y-auto custom-scrollbar">
                                        {selectedFit.description || "No fitting notes available."}
                                    </p>
                                </div>

                                {/* Slots */}
                                <div className="overflow-y-auto custom-scrollbar flex-grow bg-dark-950" id="modal-slots">
                                    {selectedFit.slots && selectedFit.slots.length > 0 ? (
                                        selectedFit.slots.map((group, idx) => {
                                            if (group.key === 'subsystem' && (!group.total || group.total === 0)) return null;
                                            return (
                                                <div key={idx}>
                                                    <div className="bg-slate-900/90 backdrop-blur-sm px-4 py-1.5 border-b border-white/5 flex justify-between items-center sticky top-0 z-10">
                                                        <h5 className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">{group.name}</h5>
                                                        {group.is_hardpoint && <span className="text-[9px] text-slate-600 font-mono tracking-tight">({group.used}/{group.total})</span>}
                                                    </div>
                                                    <div className="px-4 py-1 space-y-px">
                                                        {group.modules.map((mod, mIdx) => (
                                                            <div key={mIdx} className={`flex items-center gap-2 px-2 py-0.5 rounded border border-transparent hover:border-white/10 ${mIdx % 2 === 0 ? 'bg-white/5' : 'bg-transparent'} transition-all duration-300`}>
                                                                <img src={`https://images.evetech.net/types/${mod.id}/icon?size=32`} className="w-4 h-4 rounded shadow-inner flex-shrink-0" alt="" />
                                                                <div className="flex-grow min-w-0 text-[11px]">
                                                                    <div className="flex justify-between items-center">
                                                                        <span className="font-medium text-slate-300 truncate leading-tight">{mod.name}</span>
                                                                        {mod.quantity > 1 && <span className="text-[9px] text-brand-400 font-mono leading-none bg-brand-900/20 px-1 rounded border border-brand-500/20">x{mod.quantity}</span>}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        ))}
                                                        {group.is_hardpoint && Array.from({ length: group.empties_count }).map((_, eIdx) => (
                                                            <div key={`empty-${eIdx}`} className="flex items-center gap-2 px-2 py-0.5 opacity-30 select-none">
                                                                <div className="w-4 h-4 rounded bg-white/10 ml-0.5"></div>
                                                                <span className="text-[9px] text-slate-500 font-mono italic">[Empty Slot]</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            );
                                        })
                                    ) : (
                                        <div className="text-center text-slate-500 italic mt-10 p-4">No module data available.</div>
                                    )}
                                </div>

                                {/* Footer */}
                                <div className="p-3 border-t border-white/5 bg-slate-900 shrink-0 z-20 shadow-[0_-10px_20px_rgba(0,0,0,0.3)]">
                                    <button onClick={copyToClipboard} className="btn-primary w-full text-xs justify-center py-2 shadow-lg shadow-brand-500/10 font-bold uppercase tracking-wider flex items-center gap-2">
                                        <Copy size={14} /> Copy EFT to Clipboard
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

// Recursive Category Component with Search Logic
const CategoryItem = ({ category, searchQuery, onSelectFit }) => {
    const [expanded, setExpanded] = useState(true); // Default open for top level
    
    // Check if this category or children match search
    const matchesSearch = (cat) => {
        if (!searchQuery) return true;
        const q = searchQuery.toLowerCase();
        if (cat.name.toLowerCase().includes(q)) return true;
        if (cat.fits.some(f => f.name.toLowerCase().includes(q) || f.hull.toLowerCase().includes(q))) return true;
        if (cat.subcategories.some(sub => matchesSearch(sub))) return true;
        return false;
    };

    if (!matchesSearch(category)) return null;

    return (
        <div className="glass-panel overflow-hidden border border-white/5 bg-slate-900/40">
            <div 
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/5 transition border-b border-white/5"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center gap-3">
                    {expanded ? <ChevronDown size={16} className="text-brand-500" /> : <ChevronRight size={16} className="text-slate-500" />}
                    <h2 className="text-lg font-bold text-slate-200 tracking-tight">{category.name}</h2>
                </div>
                <span className="badge badge-slate">{category.fits.length} Fits</span>
            </div>

            {expanded && (
                <div className="bg-black/20 p-2 space-y-2">
                    {/* Render Fits */}
                    {category.fits.map(fit => {
                        const q = searchQuery.toLowerCase();
                        if (searchQuery && !fit.name.toLowerCase().includes(q) && !fit.hull.toLowerCase().includes(q)) return null;
                        
                        return (
                            <div 
                                key={fit.id} 
                                onClick={() => onSelectFit(fit.id)}
                                className="group relative overflow-hidden bg-white/5 hover:bg-brand-900/20 border border-white/5 hover:border-brand-500/30 rounded-lg p-3 cursor-pointer transition-all duration-300"
                            >
                                <div className="flex justify-between items-center relative z-10">
                                    <div className="flex items-center gap-4">
                                        <img src={`https://images.evetech.net/types/${fit.hull_id}/icon?size=64`} className="w-10 h-10 rounded border border-white/10 bg-black/50 shadow-inner" alt="" />
                                        <div>
                                            <div className="font-bold text-slate-200 group-hover:text-white transition">{fit.name}</div>
                                            <div className="text-xs text-slate-500 font-mono mt-0.5">{fit.hull}</div>
                                        </div>
                                    </div>
                                    <div className="flex flex-wrap gap-1 max-w-[50%] justify-end">
                                        {fit.tags && fit.tags.map(tag => (
                                            <span key={tag} className="badge badge-slate text-[9px]">{tag}</span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {/* Render Subcategories */}
                    {category.subcategories.map(sub => (
                        <CategoryItem 
                            key={sub.id} 
                            category={sub} 
                            searchQuery={searchQuery} 
                            onSelectFit={onSelectFit} 
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export default Doctrines;