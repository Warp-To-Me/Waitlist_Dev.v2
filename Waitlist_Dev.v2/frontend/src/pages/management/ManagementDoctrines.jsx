import React, { useEffect, useState } from 'react';
import { Upload, Download, Edit, Trash, X } from 'lucide-react';
import { apiCall } from '../../utils/api';

const ManagementDoctrines = () => {
    const [categories, setCategories] = useState([]);
    const [tags, setTags] = useState([]);
    const [fits, setFits] = useState([]);
    const [formAction, setFormAction] = useState('create');
    const [formData, setFormData] = useState({ fit_id: '', category_id: '', eft_paste: '', description: '', tags: [] });
    const [exportModalOpen, setExportModalOpen] = useState(false);
    const [importModalOpen, setImportModalOpen] = useState(false);
    const [exportString, setExportString] = useState('');
    const [importString, setImportString] = useState('');

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = () => {
        apiCall('/api/management/doctrines/data/')
            .then(res => res.json())
            .then(data => {
                setCategories(data.categories || []);
                setTags(data.tags || []);
                setFits(data.fits || []);
                if (data.categories.length > 0 && !formData.category_id) {
                    setFormData(prev => ({ ...prev, category_id: data.categories[0].id }));
                }
            });
    };

    const handleTagChange = (tagId) => {
        const newTags = formData.tags.includes(tagId) 
            ? formData.tags.filter(t => t !== tagId) 
            : [...formData.tags, tagId];
        setFormData({ ...formData, tags: newTags });
    };

    const editFit = (fit) => {
        setFormAction('update');
        setFormData({
            fit_id: fit.id,
            category_id: fit.category_id,
            eft_paste: fit.eft_format,
            description: fit.description,
            tags: fit.tag_ids
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const resetForm = () => {
        setFormAction('create');
        setFormData({ fit_id: '', category_id: categories[0]?.id || '', eft_paste: '', description: '', tags: [] });
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/management/doctrines/save/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action: formAction, ...formData })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                resetForm();
                fetchData();
            } else {
                alert(data.error);
            }
        });
    };

    const deleteFit = (id) => {
        if (!confirm('Are you sure?')) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/management/doctrines/save/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action: 'delete', fit_id: id })
        }).then(res => res.json()).then(data => {
            if (data.success) fetchData(); else alert(data.error);
        });
    };

    const exportDoctrines = () => {
        apiCall('/api/management/doctrines/export/')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    setExportString(data.export_string);
                    setExportModalOpen(true);
                } else alert(data.error);
            });
    };

    const importDoctrines = () => {
        if (!importString.trim()) return alert("Paste string first");
        if (!confirm("Overwrite all data?")) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        apiCall('/api/management/doctrines/import/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ import_string: importString })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                alert(data.message);
                setImportModalOpen(false);
                fetchData();
            } else alert(data.error);
        });
    };

    // Helper to render nested options
    const renderCategoryOptions = (cats, level = 0) => {
        return cats.map(cat => (
            <React.Fragment key={cat.id}>
                <option value={cat.id} className={level === 0 ? "font-bold bg-slate-900" : "bg-slate-800"}>
                    {'-'.repeat(level * 2)} {cat.name}
                </option>
                {cat.subcategories && renderCategoryOptions(cat.subcategories, level + 1)}
            </React.Fragment>
        ));
    };

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-white/5 pb-6">
                <h1 className="heading-1">Doctrine Management</h1>
                <div className="flex gap-2">
                    <button onClick={exportDoctrines} className="btn-secondary text-xs border-brand-500/30 text-brand-400 hover:bg-brand-500/10 flex items-center gap-2">
                        <Upload size={14} /> Export Doctrines
                    </button>
                    <button onClick={() => setImportModalOpen(true)} className="btn-secondary text-xs hover:text-white flex items-center gap-2">
                        <Download size={14} /> Import
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                {/* Form */}
                <div className="glass-panel p-6 h-fit sticky top-6">
                    <div className="flex justify-between items-center mb-6">
                        <h2 className={`text-lg font-bold tracking-wide ${formAction === 'update' ? 'text-blue-500' : 'text-brand-500'}`}>
                            {formAction === 'update' ? 'Edit Fit' : 'Import Fit'}
                        </h2>
                        {formAction === 'update' && (
                            <button onClick={resetForm} className="text-xs text-red-400 hover:text-white underline decoration-red-500/30 hover:decoration-white transition">Cancel Edit</button>
                        )}
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="label-text">Category</label>
                            <select 
                                value={formData.category_id} 
                                onChange={(e) => setFormData({...formData, category_id: e.target.value})} 
                                className="select-field"
                            >
                                {renderCategoryOptions(categories)}
                            </select>
                        </div>

                        <div>
                            <label className="label-text">EFT Block</label>
                            <textarea 
                                value={formData.eft_paste} 
                                onChange={(e) => setFormData({...formData, eft_paste: e.target.value})}
                                rows="8" 
                                className="input-field font-mono text-xs" 
                                placeholder="[Hull Name, Fit Name]..." 
                            />
                            <p className="text-[10px] text-slate-500 mt-1 pl-1">Accepts EFT/Pyfa formats.</p>
                        </div>

                        <div>
                            <label className="label-text">Tags / Labels</label>
                            <div className="flex flex-wrap gap-2 p-3 rounded-lg border border-white/5 bg-black/20">
                                {tags.map(tag => (
                                    <label key={tag.id} className="cursor-pointer">
                                        <input 
                                            type="checkbox" 
                                            className="peer sr-only" 
                                            checked={formData.tags.includes(tag.id)} 
                                            onChange={() => handleTagChange(tag.id)} 
                                        />
                                        <span className="px-2 py-1 rounded text-[10px] font-bold border border-slate-700 bg-slate-800 text-slate-400 peer-checked:border-brand-500 peer-checked:text-brand-400 peer-checked:bg-brand-900/20 transition select-none block hover:border-slate-500">
                                            {tag.name}
                                        </span>
                                    </label>
                                ))}
                            </div>
                        </div>

                        <div>
                            <label className="label-text">Internal Notes</label>
                            <input 
                                type="text" 
                                value={formData.description} 
                                onChange={(e) => setFormData({...formData, description: e.target.value})}
                                className="input-field" 
                            />
                        </div>

                        <button type="submit" className={`w-full shadow-lg transition btn ${formAction === 'update' ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20' : 'btn-primary shadow-brand-500/20'}`}>
                            {formAction === 'update' ? 'Update Fit' : 'Parse & Save'}
                        </button>
                    </form>
                </div>

                {/* List */}
                <div className="lg:col-span-2 glass-panel overflow-hidden">
                    <div className="p-4 bg-white/5 border-b border-white/5">
                        <h3 className="font-bold text-slate-200">Existing Fits</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left text-slate-400">
                            <thead className="text-xs uppercase bg-white/5 text-slate-300 font-bold">
                                <tr>
                                    <th className="px-6 py-3">Hull</th>
                                    <th className="px-6 py-3">Fit Name</th>
                                    <th className="px-6 py-3">Category</th>
                                    <th className="px-6 py-3">Tags</th>
                                    <th className="px-6 py-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {fits.map(fit => (
                                    <tr key={fit.id} className="hover:bg-white/5 transition group">
                                        <td className="px-6 py-4 font-bold text-white">{fit.ship_name}</td>
                                        <td className="px-6 py-4">{fit.name}</td>
                                        <td className="px-6 py-4 opacity-50 text-xs">{fit.category_path}</td>
                                        <td className="px-6 py-4">
                                            <div className="flex flex-wrap gap-1">
                                                {fit.tags.map(t => <span key={t} className="badge badge-slate text-[10px]">{t}</span>)}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right flex justify-end items-center gap-2">
                                            <button onClick={() => editFit(fit)} className="btn-secondary py-1 px-2 text-[10px] border-blue-500/30 text-blue-400 hover:bg-blue-500/10">
                                                <Edit size={12} /> EDIT
                                            </button>
                                            <button onClick={() => deleteFit(fit.id)} className="btn-danger py-1 px-2 text-[10px]">
                                                <Trash size={12} /> DEL
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                {fits.length === 0 && (
                                    <tr><td colSpan="5" className="p-8 text-center italic text-slate-500">No fits found.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Export Modal */}
            {exportModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark-950/80 backdrop-blur-sm px-4">
                    <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden animate-fade-in">
                        <div className="glass-header px-6 py-4 border-b border-white/5 flex justify-between items-center">
                            <h3 className="font-bold text-white text-lg">Export Doctrines</h3>
                            <button onClick={() => setExportModalOpen(false)} className="text-slate-400 hover:text-white"><X size={16} /></button>
                        </div>
                        <div className="p-6">
                            <p className="text-slate-400 text-sm mb-4">Copy this string to import into another instance.</p>
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
                            <h3 className="font-bold text-white text-lg">Import Doctrines</h3>
                            <button onClick={() => setImportModalOpen(false)} className="text-slate-400 hover:text-white"><X size={16} /></button>
                        </div>
                        <div className="p-6">
                            <div className="bg-amber-900/20 border border-amber-500/30 p-3 rounded text-amber-200 text-xs mb-4 flex items-start gap-2">
                                <span className="text-lg">⚠️</span>
                                <p><strong>Warning:</strong> Importing will <u className="font-bold text-white">WIPE</u> all existing data.</p>
                            </div>
                            <textarea 
                                value={importString} 
                                onChange={(e) => setImportString(e.target.value)} 
                                className="w-full bg-black/30 border border-slate-700 rounded p-3 text-xs font-mono text-white h-32 focus:ring-1 focus:ring-brand-500 outline-none resize-none" 
                                placeholder="Paste export string here..." 
                            />
                            <div className="flex justify-end gap-2 mt-4">
                                <button onClick={() => setImportModalOpen(false)} className="btn-ghost text-xs">Cancel</button>
                                <button onClick={importDoctrines} className="btn-primary text-xs px-6">Import & Overwrite</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManagementDoctrines;