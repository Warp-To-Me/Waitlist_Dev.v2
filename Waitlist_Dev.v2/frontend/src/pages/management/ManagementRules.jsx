import React, { useEffect, useState, useRef } from 'react';
import { Save, Upload, Download, Search, X, Check, Copy, Trash } from 'lucide-react';
import clsx from 'clsx';
import { apiCall } from '../../utils/api';

const ManagementRules = () => {
    const [view, setView] = useState('search'); // 'search' or 'saved'
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [savedQuery, setSavedQuery] = useState('');
    const [savedRules, setSavedRules] = useState([]);
    const [pagination, setPagination] = useState({ page: 1, total_pages: 1, has_next: false, has_previous: false });
    
    const [currentGroup, setCurrentGroup] = useState(null); // { id, name }
    const [rules, setRules] = useState([]); // List of rules for current group
    const [loadingRules, setLoadingRules] = useState(false);

    const [exportModalOpen, setExportModalOpen] = useState(false);
    const [importModalOpen, setImportModalOpen] = useState(false);
    const [exportString, setExportString] = useState('');
    const [importString, setImportString] = useState('');

    const searchTimeout = useRef(null);

    // --- Search Groups ---
    useEffect(() => {
        if (searchQuery.length === 0) {
            setSearchResults([]);
            return;
        }
        if (searchTimeout.current) clearTimeout(searchTimeout.current);
        searchTimeout.current = setTimeout(() => {
            apiCall(`/api/management/rules/search_groups/?q=${encodeURIComponent(searchQuery)}`)
                .then(res => res.json())
                .then(data => setSearchResults(data.results || []));
        }, 300);
    }, [searchQuery]);

    // --- Load Saved Rules ---
    useEffect(() => {
        if (view === 'saved') {
            fetchSavedRules(1);
        }
    }, [view, savedQuery]);

    const fetchSavedRules = (page) => {
        apiCall(`/api/management/rules/list/?page=${page}&q=${encodeURIComponent(savedQuery)}`)
            .then(res => res.json())
            .then(data => {
                setSavedRules(data.results || []);
                setPagination({
                    page: data.current_page,
                    total_pages: data.total_pages,
                    has_next: data.has_next,
                    has_previous: data.has_previous
                });
            });
    };

    // --- Load Rules for Group ---
    const loadGroup = (id, name) => {
        setCurrentGroup({ id, name });
        setLoadingRules(true);
        // Hide dropdowns/switch view if needed, though typically we just show the editor
        setSearchResults([]); // Clear search dropdown
        setSearchQuery(''); // Clear search input
        
        apiCall(`/api/management/rules/discovery/${id}/`)
            .then(res => res.json())
            .then(data => {
                setRules(data.rules || []);
                setLoadingRules(false);
            });
    };

    const handleRuleChange = (attrId, field, value) => {
        setRules(prev => prev.map(r => r.attr_id === attrId ? { ...r, [field]: value } : r));
    };

    const toggleRuleActive = (attrId) => {
        setRules(prev => prev.map(r => r.attr_id === attrId ? { ...r, is_active: !r.is_active } : r));
    };

    const saveRules = () => {
        if (!currentGroup) return;
        const activeRules = rules.filter(r => r.is_active).map(r => ({
            attr_id: r.attr_id,
            logic: r.logic,
            tolerance: parseFloat(r.tolerance) || 0
        }));

        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/management/rules/save/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ group_id: currentGroup.id, rules: activeRules })
        }).then(res => res.json()).then(data => {
            if (data.success) alert("Saved!"); else alert("Error: " + data.error);
        });
    };

    const deleteGroupRules = (id, name) => {
        if (!confirm(`Delete all rules for "${name}"?`)) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/management/rules/delete/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ group_id: id })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                fetchSavedRules(pagination.page);
                if (currentGroup?.id === id) {
                    setCurrentGroup(null);
                    setRules([]);
                }
            } else alert("Error: " + data.error);
        });
    };

    const exportRules = () => {
        apiCall('/api/management/rules/export/')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    setExportString(data.export_string);
                    setExportModalOpen(true);
                } else alert(data.error);
            });
    };

    const importRules = () => {
        if (!importString) return alert("Paste string first");
        if (!confirm("Overwrite all rules?")) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/management/rules/import/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ import_string: importString })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                alert(data.message);
                setImportModalOpen(false);
                if (view === 'saved') fetchSavedRules(1);
            } else alert(data.error);
        });
    };

    return (
        <div className="flex flex-col h-full gap-6">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-white/5 pb-6 shrink-0">
                <div>
                    <h1 className="heading-1">Doctrine Rule Helper</h1>
                    <p className="text-slate-400 text-sm mt-1">Configure logic for comparing non-doctrine modules.</p>
                </div>
                <div className="flex gap-3">
                    {currentGroup && (
                        <button onClick={saveRules} className="btn-success shadow-lg shadow-green-500/20 flex items-center gap-2">
                            <Save size={14} /> Save Selected Rules
                        </button>
                    )}
                    <div className="h-8 w-px bg-white/10 mx-2"></div>
                    <button onClick={exportRules} className="btn-secondary text-xs border-brand-500/30 text-brand-400 hover:bg-brand-500/10 flex items-center gap-2">
                        <Upload size={14} /> Export Rules
                    </button>
                    <button onClick={() => setImportModalOpen(true)} className="btn-secondary text-xs hover:text-white flex items-center gap-2">
                        <Download size={14} /> Import
                    </button>
                </div>
            </div>

            {/* Control Bar */}
            <div className="glass-panel p-4 shrink-0 flex flex-col md:flex-row gap-4 items-center relative z-20">
                <div className="flex bg-black/40 p-1 rounded-lg border border-white/10">
                    <button 
                        onClick={() => setView('search')} 
                        className={clsx("px-4 py-1.5 rounded-md text-xs font-bold transition", view === 'search' ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white")}
                    >
                        Search Groups
                    </button>
                    <button 
                        onClick={() => setView('saved')} 
                        className={clsx("px-4 py-1.5 rounded-md text-xs font-bold transition", view === 'saved' ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white")}
                    >
                        Saved Rules
                    </button>
                </div>

                {view === 'search' ? (
                    <div className="relative flex-grow w-full group">
                        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none group-focus-within:text-brand-500 transition">
                            <Search className="w-5 h-5 text-slate-500" />
                        </div>
                        <input 
                            type="text" 
                            className="input-field pl-10" 
                            placeholder="Search by Item Group (e.g. 'Shield Hardener')..." 
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                        {searchResults.length > 0 && (
                            <div className="absolute top-full left-0 w-full mt-2 bg-slate-900 border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
                                {searchResults.map(grp => (
                                    <div 
                                        key={grp.id} 
                                        className="p-3 hover:bg-brand-900/20 hover:text-brand-400 cursor-pointer border-b border-white/5 last:border-0 transition flex justify-between"
                                        onClick={() => loadGroup(grp.id, grp.name)}
                                    >
                                        <span>{grp.name}</span> <span className="text-slate-600 font-mono text-xs opacity-50">{grp.id}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="w-full overflow-hidden flex flex-col gap-2">
                        <div className="relative w-full">
                            <input 
                                type="text" 
                                className="input-field pl-9 py-1.5 text-xs bg-black/20 border-white/10 focus:border-brand-500"
                                placeholder="Filter saved rules..."
                                value={savedQuery}
                                onChange={(e) => setSavedQuery(e.target.value)}
                            />
                            <Search className="absolute left-3 top-2 w-4 h-4 text-slate-500" />
                        </div>
                        <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto custom-scrollbar p-1">
                            {savedRules.map(item => (
                                <div key={item.id} className="px-3 py-2 bg-slate-800 border border-slate-700 rounded hover:border-brand-500 hover:text-white text-slate-300 text-xs transition flex justify-between items-center gap-2 group min-w-[200px] flex-grow md:flex-grow-0">
                                    <span className="flex-grow cursor-pointer flex justify-between items-center gap-2" onClick={() => loadGroup(item.id, item.name)}>
                                        <span className="font-bold truncate">{item.name}</span>
                                        <span className="bg-slate-900 text-slate-500 px-1.5 py-0.5 rounded text-[9px] group-hover:text-brand-400 transition font-mono">{item.count}</span>
                                    </span>
                                    <button onClick={(e) => { e.stopPropagation(); deleteGroupRules(item.id, item.name); }} className="text-slate-600 hover:text-red-400 px-1 transition">
                                        <X size={14} />
                                    </button>
                                </div>
                            ))}
                        </div>
                        {pagination.total_pages > 1 && (
                            <div className="flex justify-between items-center bg-black/20 p-1.5 rounded border border-white/5 text-[10px]">
                                <button disabled={!pagination.has_previous} onClick={() => fetchSavedRules(pagination.page - 1)} className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 disabled:opacity-50">Previous</button>
                                <span className="text-slate-500 font-mono">Page {pagination.page} / {pagination.total_pages}</span>
                                <button disabled={!pagination.has_next} onClick={() => fetchSavedRules(pagination.page + 1)} className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 disabled:opacity-50">Next</button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Main Editor */}
            {currentGroup && (
                <div className="flex-col flex-grow min-h-0 animate-fade-in relative z-0 flex">
                    <div className="flex items-center gap-4 mb-4">
                        <h2 className="text-2xl font-bold text-white tracking-tight">{currentGroup.name}</h2>
                        <span className="badge badge-brand">ID: {currentGroup.id}</span>
                    </div>

                    <div className="glass-panel overflow-hidden flex flex-col flex-grow">
                        <div className="grid grid-cols-12 gap-4 p-4 bg-white/5 border-b border-white/5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                            <div className="col-span-1 text-center">Use?</div>
                            <div className="col-span-3">Attribute Name</div>
                            <div className="col-span-3">Logic</div>
                            <div className="col-span-1 text-center">Tolerance %</div>
                            <div className="col-span-4">Description</div>
                        </div>

                        <div className="overflow-y-auto custom-scrollbar flex-grow p-2 space-y-1">
                            {loadingRules ? (
                                <div className="p-12 text-center text-slate-500 animate-pulse">Scanning database attributes...</div>
                            ) : rules.length > 0 ? (
                                rules.map(rule => (
                                    <div key={rule.attr_id} className={clsx("grid grid-cols-12 gap-4 p-3 rounded items-center transition group", rule.is_active ? "bg-white/5 border-l-2 border-brand-500" : "opacity-60 hover:opacity-100 hover:bg-white/5 border-l-2 border-transparent")}>
                                        <div className="col-span-1 flex justify-center">
                                            <input type="checkbox" checked={rule.is_active} onChange={() => toggleRuleActive(rule.attr_id)} className="w-5 h-5 rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-offset-0 focus:ring-0 cursor-pointer" />
                                        </div>
                                        <div className="col-span-3 font-bold text-sm text-slate-200 truncate" title={rule.name}>{rule.name}</div>
                                        <div className="col-span-3">
                                            <select 
                                                value={rule.logic} 
                                                onChange={(e) => handleRuleChange(rule.attr_id, 'logic', e.target.value)}
                                                className="w-full bg-black/40 border border-slate-700 rounded px-2 py-1 text-xs text-white outline-none focus:border-brand-500"
                                            >
                                                <option value="higher">Higher is Better</option>
                                                <option value="lower">Lower is Better</option>
                                                <option value="match">Must Match</option>
                                            </select>
                                        </div>
                                        <div className="col-span-1">
                                            <input 
                                                type="number" step="0.1" min="0" 
                                                value={rule.tolerance} 
                                                onChange={(e) => handleRuleChange(rule.attr_id, 'tolerance', e.target.value)}
                                                className="w-full bg-black/40 border border-slate-700 rounded px-2 py-1 text-xs text-center text-white outline-none focus:border-brand-500"
                                                placeholder="0%"
                                            />
                                        </div>
                                        <div className="col-span-4 text-xs text-slate-500 truncate" title={rule.description}>{rule.description || 'No description available.'}</div>
                                    </div>
                                ))
                            ) : (
                                <div className="p-8 text-center text-slate-500">No relevant attributes found for this group.</div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Export Modal */}
            {exportModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark-950/80 backdrop-blur-sm px-4">
                    <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden animate-fade-in">
                        <div className="glass-header px-6 py-4 border-b border-white/5 flex justify-between items-center">
                            <h3 className="font-bold text-white text-lg">Export Rules</h3>
                            <button onClick={() => setExportModalOpen(false)} className="text-slate-400 hover:text-white"><X size={16} /></button>
                        </div>
                        <div className="p-6">
                            <p className="text-slate-400 text-sm mb-4">Copy the string below to import into another instance.</p>
                            <textarea readOnly value={exportString} className="w-full bg-black/30 border border-slate-700 rounded p-3 text-xs font-mono text-brand-400 h-32 focus:ring-1 focus:ring-brand-500 outline-none resize-none" />
                            <div className="flex justify-end gap-2 mt-4">
                                <button onClick={() => setExportModalOpen(false)} className="btn-ghost text-xs">Close</button>
                                <button onClick={() => navigator.clipboard.writeText(exportString)} className="btn-primary text-xs px-6">Copy to Clipboard</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Import Modal */}
            {importModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark-950/80 backdrop-blur-sm px-4">
                    <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden animate-fade-in">
                        <div className="glass-header px-6 py-4 border-b border-white/5 flex justify-between items-center">
                            <h3 className="font-bold text-white text-lg">Import Rules</h3>
                            <button onClick={() => setImportModalOpen(false)} className="text-slate-400 hover:text-white"><X size={16} /></button>
                        </div>
                        <div className="p-6">
                            <div className="bg-amber-900/20 border border-amber-500/30 p-3 rounded text-amber-200 text-xs mb-4 flex items-start gap-2">
                                <span className="text-lg">⚠️</span>
                                <p><strong>Warning:</strong> Importing rules will <u>overwrite</u> all currently configured analysis rules.</p>
                            </div>
                            <textarea 
                                value={importString} 
                                onChange={(e) => setImportString(e.target.value)} 
                                className="w-full bg-black/30 border border-slate-700 rounded p-3 text-xs font-mono text-white h-32 focus:ring-1 focus:ring-brand-500 outline-none resize-none" 
                                placeholder="Paste export string here..." 
                            />
                            <div className="flex justify-end gap-2 mt-4">
                                <button onClick={() => setImportModalOpen(false)} className="btn-ghost text-xs">Cancel</button>
                                <button onClick={importRules} className="btn-primary text-xs px-6">Import & Overwrite</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManagementRules;