import React, { useEffect, useState, useRef } from 'react';
import { RefreshCw, ArrowLeft, ArrowRight, TrendingUp, TrendingDown, DollarSign } from 'lucide-react';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend, ArcElement } from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';
import clsx from 'clsx';

// Register ChartJS components
ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend, ArcElement);

const ManagementSRP = () => {
    // --- STATE ---
    const [status, setStatus] = useState(null);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [syncTimerStr, setSyncTimerStr] = useState("Checking...");

    // Filters
    const [dateRange, setDateRange] = useState({ start: '', end: '' });
    const [divisions, setDivisions] = useState(['1','2','3','4','5','6','7']);
    const [divisionMap, setDivisionMap] = useState({}); // { 1: "Master Wallet", ... }

    // Pagination State
    const [page, setPage] = useState(1);
    const [limit, setLimit] = useState(25);

    // Column Filters
    const [filters, setFilters] = useState({
        f_div: '',
        f_amount: '',
        f_from: '',
        f_to: '',
        f_type: '',
        f_category: '',
        f_reason: ''
    });

    // Timers
    const statusPollRef = useRef(null);
    const syncTimerRef = useRef(null);

    // --- INITIALIZATION ---
    useEffect(() => {
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
        const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];
        setDateRange({ start, end });

        fetchStatus();
        fetchDivisions();

        return () => {
            if (statusPollRef.current) clearTimeout(statusPollRef.current);
            if (syncTimerRef.current) clearInterval(syncTimerRef.current);
        };
    }, []);

    // Fetch Data on Filter Change (Removed dateRange.start check to allow "All" selection)
    useEffect(() => {
        fetchData();
    }, [dateRange, divisions, page, limit, filters]);

    // --- API CALLS ---
    const fetchDivisions = () => {
        fetch('/api/mgmt/srp/divisions/')
            .then(res => res.json())
            .then(data => {
                // Ensure mapping has string keys if needed, but API returns {1: "Name"}
                // We'll trust the API returns a dict.
                if (data && !data.error) setDivisionMap(data);
            })
            .catch(err => console.error("Failed to fetch divisions", err));
    };

    const fetchStatus = () => {
        fetch('/api/srp/status/')
            .then(res => res.json())
            .then(data => {
                setStatus(data);
                if (data.next_sync) startSyncTimer(data.next_sync);

                let delay = 30000;
                if (data.next_sync) {
                    const diff = new Date(data.next_sync) - new Date();
                    if (diff > 300000) delay = 300000;
                    else if (diff > 15000) delay = diff;
                    else delay = 15000;
                }
                statusPollRef.current = setTimeout(fetchStatus, delay > 1000 ? delay : 5000);
            })
            .catch(() => {
                statusPollRef.current = setTimeout(fetchStatus, 60000);
            });
    };

    const fetchData = () => {
        setLoading(true);
        const params = new URLSearchParams({
            start_date: dateRange.start,
            end_date: dateRange.end,
            page: page,
            limit: limit,
            ...filters
        });
        divisions.forEach(d => params.append('divisions[]', d));

        fetch(`/api/srp/data/?${params.toString()}`)
            .then(res => res.json())
            .then(data => {
                setSummary(data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to fetch SRP data", err);
                setLoading(false);
            });
    };

    const updateCategory = (entryId, newCategory) => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch('/api/mgmt/srp/update_category/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify({ entry_id: entryId, category: newCategory })
        })
        .then(res => res.json())
        .then(data => {
            if (!data.success) alert("Failed to update category");
            else fetchData();
        });
    };

    // --- HELPERS ---
    const startSyncTimer = (targetIso) => {
        if (syncTimerRef.current) clearInterval(syncTimerRef.current);
        const target = new Date(targetIso).getTime();

        const update = () => {
            const now = new Date().getTime();
            const diff = target - now;
            if (diff <= 0) {
                setSyncTimerStr("Sync Ready");
                return;
            }
            const h = Math.floor(diff / (1000 * 60 * 60));
            const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const s = Math.floor((diff % (1000 * 60)) / 1000);
            setSyncTimerStr(`${h > 0 ? h + 'h ' : ''}${m}m ${s}s`);
        };
        update();
        syncTimerRef.current = setInterval(update, 1000);
    };

    const debouncedSetFilter = (key, value) => {
        setFilters(prev => ({ ...prev, [key]: value }));
        setPage(1);
    };

    if (!status && !summary && loading) return <div className="p-10 text-center text-slate-500"><RefreshCw className="animate-spin inline mr-2"/> Loading Dashboard...</div>;

    return (
        <div className="flex flex-col gap-6 pb-12">
            {/* HEADER / FILTERS */}
            <div className="glass-panel p-4 flex flex-col md:flex-row justify-between items-center gap-4 bg-slate-900/90 sticky top-0 z-20 backdrop-blur-md">
                <div className="flex items-center gap-6">
                    <div>
                        <h1 className="text-lg font-bold text-white tracking-tight">Corporation Wallet Monitor</h1>
                        <p className="text-xs text-slate-400">
                            Last Sync: <span className="text-slate-300">{status?.last_sync ? new Date(status.last_sync).toLocaleString() : 'Never'}</span>
                        </p>
                    </div>

                    {status?.next_sync && (
                        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black/20 border border-white/5">
                            <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Next Sync</span>
                            <span className="text-xs font-mono text-slate-400 font-bold w-20">{syncTimerStr}</span>
                        </div>
                    )}
                </div>

                <div className="flex gap-4 items-center flex-wrap">
                    <div className="flex items-center gap-2 bg-black/30 p-1.5 rounded border border-white/10">
                        <input
                            type="date"
                            value={dateRange.start}
                            onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                            className="bg-transparent text-xs text-white outline-none w-24"
                        />
                        <span className="text-slate-500">-</span>
                        <input
                            type="date"
                            value={dateRange.end}
                            onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                            className="bg-transparent text-xs text-white outline-none w-24"
                        />
                        <button
                            onClick={() => setDateRange({ start: '', end: '' })}
                            className="text-[10px] font-bold text-slate-500 hover:text-brand-400 ml-2 pl-2 border-l border-white/10 uppercase transition"
                        >
                            All
                        </button>
                    </div>

                    <div className="flex gap-2 text-xs">
                        {['1','2','3','4','5','6','7'].map(div => (
                            <label key={div} className="flex items-center gap-1 cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    checked={divisions.includes(div)}
                                    onChange={(e) => {
                                        if (e.target.checked) setDivisions(p => [...p, div]);
                                        else setDivisions(p => p.filter(d => d !== div));
                                    }}
                                    className="rounded bg-slate-800 border-slate-600 text-brand-500 focus:ring-0 w-3 h-3"
                                />
                                <span className="text-slate-300" title={divisionMap[div] || `Division ${div}`}>
                                    {divisionMap[div] ? divisionMap[div].substring(0, 10) : `Div ${div}`}
                                </span>
                            </label>
                        ))}
                    </div>

                    <button onClick={() => fetchData()} className="btn-ghost p-1.5 text-slate-400 hover:text-white" title="Refresh">
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            {/* DIVISION BALANCES */}
            {summary?.division_balances && Object.keys(summary.division_balances).length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                    {Object.entries(summary.division_balances).map(([div, bal]) => (
                        <div key={div} className="glass-panel p-3 flex flex-col justify-center items-center border border-white/5 bg-slate-900/50">
                            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1 truncate w-full text-center" title={divisionMap[div] || `Division ${div}`}>
                                {divisionMap[div] || `Division ${div}`}
                            </span>
                            <span className="text-xs font-mono font-bold text-white whitespace-nowrap">{parseFloat(bal).toLocaleString()} ISK</span>
                        </div>
                    ))}
                </div>
            )}

            {/* SUMMARY CARDS */}
            {summary && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <SummaryCard label="Total Income" value={summary.summary.income} color="text-green-400" />
                    <SummaryCard label="Total Outcome" value={summary.summary.outcome} color="text-red-400" />
                    <SummaryCard label="Net Change" value={summary.summary.net} color={summary.summary.net >= 0 ? 'text-white' : 'text-red-300'} />
                </div>
            )}

            {/* CHARTS */}
            {summary && <SRPCharts data={summary} />}

            {/* TRANSACTIONS TABLE */}
            <div className="glass-panel flex flex-col overflow-hidden min-h-[500px]">
                {/* Pagination Controls Top */}
                <div className="p-3 border-b border-white/5 bg-slate-900/50 flex justify-between items-center">
                    <h3 className="label-text mb-0 w-1/3">Transactions</h3>
                    <div className="w-1/3 flex justify-center">
                        <SmartPagination
                            current={page}
                            total={summary?.pagination?.total_pages || 1}
                            onChange={setPage}
                        />
                    </div>
                    <div className="w-1/3 flex justify-end">
                        <select
                            value={limit}
                            onChange={(e) => {
                                setLimit(Number(e.target.value));
                                setPage(1);
                            }}
                            className="bg-black/30 border border-slate-700 text-slate-300 text-xs rounded px-2 py-1 outline-none focus:border-brand-500"
                        >
                            <option value="10">10 Rows</option>
                            <option value="25">25 Rows</option>
                            <option value="50">50 Rows</option>
                            <option value="100">100 Rows</option>
                        </select>
                    </div>
                </div>

                <div className="overflow-auto custom-scrollbar flex-grow relative bg-slate-900/20">
                    <table className="w-full text-left text-xs text-slate-400 border-collapse">
                        <thead className="bg-slate-900/95 text-[10px] uppercase font-bold sticky top-0 z-10 backdrop-blur-md shadow-sm">
                            <tr>
                                <th className="px-2 py-2 border-b border-white/5 w-24 whitespace-nowrap">Date</th>
                                <th className="px-2 py-2 border-b border-white/5 text-center w-12">Div</th>
                                <th className="px-2 py-2 border-b border-white/5 text-right w-32 whitespace-nowrap">Amount</th>
                                <th className="px-2 py-2 border-b border-white/5 w-32">From</th>
                                <th className="px-2 py-2 border-b border-white/5 w-32">To</th>
                                <th className="px-2 py-2 border-b border-white/5 w-32 whitespace-nowrap">Type</th>
                                <th className="px-2 py-2 border-b border-white/5 w-48">Category</th>
                                <th className="px-2 py-2 border-b border-white/5">Reason</th>
                            </tr>
                            <tr className="bg-slate-900/90 border-b border-white/10">
                                <td className="p-1"></td>
                                <td className="p-1">
                                    <input placeholder="#" value={filters.f_div} onChange={(e) => debouncedSetFilter('f_div', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-1 py-0.5 text-[10px] text-center text-slate-300 focus:border-brand-500 outline-none" />
                                </td>
                                <td className="p-1">
                                    <input placeholder="Min..." value={filters.f_amount} onChange={(e) => debouncedSetFilter('f_amount', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-1 py-0.5 text-[10px] text-right text-slate-300 focus:border-brand-500 outline-none" />
                                </td>
                                <td className="p-1">
                                    <input placeholder="From..." value={filters.f_from} onChange={(e) => debouncedSetFilter('f_from', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-1 py-0.5 text-[10px] text-slate-300 focus:border-brand-500 outline-none" />
                                </td>
                                <td className="p-1">
                                    <input placeholder="To..." value={filters.f_to} onChange={(e) => debouncedSetFilter('f_to', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-1 py-0.5 text-[10px] text-slate-300 focus:border-brand-500 outline-none" />
                                </td>
                                <td className="p-1">
                                    <input placeholder="Type..." value={filters.f_type} onChange={(e) => debouncedSetFilter('f_type', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-1 py-0.5 text-[10px] text-slate-300 focus:border-brand-500 outline-none" />
                                </td>
                                <td className="p-1">
                                    <select value={filters.f_category} onChange={(e) => debouncedSetFilter('f_category', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-1 py-0.5 text-[10px] text-slate-300 focus:border-brand-500 outline-none">
                                        <option value="">All</option>
                                        <option value="uncategorised">Uncategorised</option>
                                        <option value="srp_in">SRP In</option>
                                        <option value="srp_out">SRP Out</option>
                                        <option value="internal_transfer">Internal Transfer</option>
                                        <option value="giveaway">Giveaway</option>
                                        <option value="manual_change">Manual Change</option>
                                        <option value="manual_out">Manual Out</option>
                                        <option value="tax">Tax</option>
                                        <option value="other">Other</option>
                                    </select>
                                </td>
                                <td className="p-1">
                                    <input placeholder="Reason..." value={filters.f_reason} onChange={(e) => debouncedSetFilter('f_reason', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-1 py-0.5 text-[10px] text-slate-300 focus:border-brand-500 outline-none" />
                                </td>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 opacity-100 transition-opacity duration-200" style={{ opacity: loading ? 0.5 : 1 }}>
                            {summary?.transactions?.map(tx => (
                                <TransactionRow key={tx.entry_id} tx={tx} onUpdateCategory={updateCategory} divisionMap={divisionMap} />
                            ))}
                            {summary?.transactions?.length === 0 && (
                                <tr><td colSpan="8" className="p-8 text-center text-slate-500 italic">No transactions found for this period.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination Controls Bottom */}
                <div className="p-3 border-t border-white/5 bg-slate-900/50 flex justify-center items-center relative">
                    <SmartPagination
                        current={page}
                        total={summary?.pagination?.total_pages || 1}
                        onChange={setPage}
                    />
                    <div className="absolute right-4 text-[10px] text-slate-500 font-mono hidden md:block">
                        {summary?.pagination?.total_count} entries
                    </div>
                </div>
            </div>
        </div>
    );
};

// --- SMART PAGINATION ---
const SmartPagination = ({ current, total, onChange }) => {
    // Generate page numbers: <- 2 3 4 5/50 6 7 8 ->
    // We want a window of 7 items centered on current

    if (total <= 1) return null;

    let start = Math.max(1, current - 3);
    let end = Math.min(total, current + 3);

    // Adjust window if close to edges
    if (start === 1) end = Math.min(total, 7);
    if (end === total) start = Math.max(1, total - 6);

    const pages = [];
    for (let i = start; i <= end; i++) {
        pages.push(i);
    }

    return (
        <div className="flex items-center gap-1">
            <button
                onClick={() => onChange(Math.max(1, current - 1))}
                disabled={current === 1}
                className="btn-secondary py-1 px-2 text-[10px] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white/10"
            >
                &larr;
            </button>

            {pages.map(p => (
                <button
                    key={p}
                    onClick={() => onChange(p)}
                    className={clsx(
                        "py-1 px-2.5 text-[10px] rounded transition font-mono",
                        p === current
                            ? "bg-brand-500 text-white font-bold shadow-lg shadow-brand-500/20"
                            : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white"
                    )}
                >
                    {p}
                </button>
            ))}

            {/* Show Total if not visible in range */}
            {end < total && (
                <>
                    <span className="text-slate-600 text-[10px]">...</span>
                    <button onClick={() => onChange(total)} className="py-1 px-2 text-[10px] text-slate-500 hover:text-white">{total}</button>
                </>
            )}

            <button
                onClick={() => onChange(Math.min(total, current + 1))}
                disabled={current === total}
                className="btn-secondary py-1 px-2 text-[10px] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white/10"
            >
                &rarr;
            </button>
        </div>
    );
}

const SummaryCard = ({ label, value, color }) => (
    <div className="glass-panel p-4 text-center">
        <div className="label-text mb-1">{label}</div>
        <div className={clsx("text-2xl font-mono font-bold", color)}>
            {parseFloat(value).toLocaleString()} ISK
        </div>
    </div>
);

// Helper to guess category based on ref_type for display only
const getSuggestedCategory = (tx) => {
    // Mimic backend determine_auto_category logic for visual cue
    const r = tx.ref_type;
    const desc = (tx.reason || "").toLowerCase();

    if (['contract_brokers_fee', 'brokers_fee', 'transaction_tax', 'tax'].includes(r) || desc.includes("broker")) return 'tax';
    if (tx.amount > 0 && (desc.includes('srp') || Math.abs(tx.amount % 20000000) < 0.1)) return 'srp_in';
    if (tx.amount < 0 && (desc.includes('srp'))) return 'srp_out';
    if (tx.amount < 0 && desc.includes('giveaway')) return 'giveaway';

    return ''; // No suggestion
};

const TransactionRow = ({ tx, onUpdateCategory, divisionMap }) => {
    const categories = [
        { id: '', label: 'Select...', class: 'bg-slate-800 border-slate-700 text-slate-400' },
        { id: 'srp_in', label: 'SRP In', class: 'bg-green-600 border-green-500 text-white' },
        { id: 'srp_out', label: 'SRP Out', class: 'bg-red-600 border-red-500 text-white' },
        { id: 'internal_transfer', label: 'Internal Transfer', class: 'bg-purple-600 border-purple-500 text-white' },
        { id: 'giveaway', label: 'Giveaway', class: 'bg-orange-600 border-orange-500 text-white' },
        { id: 'manual_change', label: 'Manual Change', class: 'bg-blue-600 border-blue-500 text-white' },
        { id: 'manual_out', label: 'Manual Out', class: 'bg-blue-600 border-blue-500 text-white' },
        { id: 'tax', label: 'Tax', class: 'bg-slate-600 border-slate-500 text-white' },
        { id: 'other', label: 'Other', class: 'bg-slate-600 border-slate-500 text-white' }
    ];

    // Use suggested category if custom_category is missing
    const effectiveCatId = tx.custom_category || getSuggestedCategory(tx);
    const currentCat = categories.find(c => c.id === effectiveCatId) || categories.find(c => c.id === 'other');

    // Fallback names
    const fromName = tx.first_party_name || `Unknown (${tx.entry_id.toString().substring(0,5)}...)`; // Can't see ID directly in API except entry_id? Backend sends names.
    const toName = tx.second_party_name || `Unknown`;

    return (
        <tr className="hover:bg-white/5 transition group">
            <td className="px-2 py-1 font-mono text-[10px] whitespace-nowrap text-slate-500 group-hover:text-slate-300">
                {new Date(tx.date).toLocaleDateString()} <span className="opacity-50">{new Date(tx.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </td>
            <td className="px-2 py-1 text-center" title={divisionMap[tx.division]}>
                <span className="bg-white/5 px-1.5 py-0.5 rounded text-[10px] border border-white/5">{tx.division}</span>
            </td>
            <td className={clsx("px-2 py-1 text-right font-mono font-bold text-xs whitespace-nowrap", tx.amount > 0 ? 'text-green-400' : 'text-red-400')}>
                {parseFloat(tx.amount).toLocaleString()}
            </td>
            <td className="px-2 py-1 truncate max-w-[120px] text-slate-300" title={tx.first_party_name}>
                {tx.first_party_name || <span className="opacity-50 italic">Unknown</span>}
            </td>
            <td className="px-2 py-1 truncate max-w-[120px] text-slate-300" title={tx.second_party_name}>
                {tx.second_party_name || <span className="opacity-50 italic">Unknown</span>}
            </td>
            <td className="px-2 py-1 whitespace-nowrap"><span className="badge badge-slate text-[9px] text-slate-500">{tx.ref_type.replace(/_/g, ' ')}</span></td>
            <td className="px-2 py-1">
                <select
                    value={tx.custom_category || ''}
                    onChange={(e) => onUpdateCategory(tx.entry_id, e.target.value)}
                    className={clsx("w-full rounded px-1 py-0.5 text-[10px] font-bold border outline-none appearance-none cursor-pointer transition-colors duration-300 focus:ring-1 focus:ring-white/50", currentCat.class)}
                >
                    {/* If we suggested a category but it's not saved, the value is '', so "Select..." shows, BUT the color matches the suggestion.
                        Wait, if value is '', it shows 'Select...'.
                        If user wants to CONFIRM suggestion, they select it.
                        Visually: The dropdown COLOR implies the suggestion. The TEXT is Select... (if not saved).
                        This is good UX to indicate "Not Saved".
                    */}
                    {categories.map(cat => (
                        <option key={cat.id} value={cat.id} className="bg-slate-900 text-white">{cat.label}</option>
                    ))}
                </select>
            </td>
            <td className="px-2 py-1 truncate max-w-[200px] italic text-slate-500 text-[10px]" title={tx.reason}>{tx.reason}</td>
        </tr>
    );
};

const SRPCharts = ({ data }) => {
    const [hiddenCategories, setHiddenCategories] = useState(new Set());

    // Color Mapping matching the Categories List
    const getColor = (c) => {
        const lower = c.toLowerCase().replace(/_/g, ' ');
        if(lower.includes('srp in')) return '#16a34a';
        if(lower.includes('srp out')) return '#dc2626';
        if(lower.includes('internal')) return '#9333ea';
        if(lower.includes('giveaway')) return '#ea580c';
        if(lower.includes('manual')) return '#2563eb';
        if(lower.includes('tax')) return '#475569';
        return '#94a3b8'; // Other/Unknown
    };

    // --- CHART DATA PREP ---
    const months = Object.keys(data.monthly).sort();
    const catKeysIn = Object.keys(data.categories.in);
    const catKeysOut = Object.keys(data.categories.out);
    const allCats = Array.from(new Set([...catKeysIn, ...catKeysOut])).sort();

    // Stacked Bar Chart Datasets (One per category)
    const monthlyDatasets = allCats.map(cat => {
        if (hiddenCategories.has(cat)) return null;
        return {
            label: cat.replace(/_/g, ' '),
            data: months.map(m => data.monthly[m] ? (data.monthly[m][cat] || 0) : 0),
            backgroundColor: getColor(cat),
            stack: 'stack1'
        };
    }).filter(ds => ds !== null);

    const monthlyData = {
        labels: months,
        datasets: monthlyDatasets
    };

    const catData = {
        labels: allCats.map(c => c.replace(/_/g, ' ')),
        datasets: [{
            data: allCats.map(c => {
                if (hiddenCategories.has(c)) return 0;
                return (data.categories.in[c] || 0) + Math.abs(data.categories.out[c] || 0);
            }),
            backgroundColor: allCats.map(c => getColor(c)),
            borderWidth: 0,
        }]
    };

    const payers = Object.entries(data.top_payers).sort((a, b) => b[1].total - a[1].total).slice(0, 5);
    const payerLabels = payers.map(p => p[0]);
    const payerCountData = {
        labels: payerLabels,
        datasets: [{ label: 'Count', data: payers.map(p => p[1].count), backgroundColor: '#38bdf8' }]
    };
    const payerIskData = {
        labels: payerLabels,
        datasets: [{ label: 'Total ISK', data: payers.map(p => p[1].total), backgroundColor: '#facc15' }]
    };

    // Stacked Options for Monthly
    const monthlyChartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }, // Controlled by Doughnut Chart Legend
            tooltip: {
                callbacks: {
                    label: (context) => {
                        let label = context.dataset.label || '';
                        if (label) label += ': ';
                        if (context.parsed.y !== null) {
                            label += parseFloat(context.parsed.y).toLocaleString() + ' ISK';
                        }
                        return label;
                    }
                }
            }
        },
        scales: {
            x: {
                stacked: true,
                ticks: { color: '#94a3b8', font: { size: 10 } },
                grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y: {
                stacked: true,
                ticks: { color: '#94a3b8', font: { size: 10 } },
                grid: { color: 'rgba(255,255,255,0.05)' }
            }
        }
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
        scales: {
            x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
            y: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } }
        }
    };

    const doughnutOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'right',
                labels: {
                    color: '#94a3b8',
                    font: { size: 10 },
                    generateLabels: (chart) => {
                        const original = ChartJS.defaults.plugins.legend.labels.generateLabels(chart);
                        original.forEach(item => {
                            // Map back to raw category key using index
                            const rawCat = allCats[item.index];
                            if (hiddenCategories.has(rawCat)) {
                                item.hidden = true; // Forces strikethrough styling
                            }
                        });
                        return original;
                    }
                },
                onClick: (e, legendItem, legend) => {
                    const catName = allCats[legendItem.index];
                    const newHidden = new Set(hiddenCategories);
                    if (newHidden.has(catName)) newHidden.delete(catName);
                    else newHidden.add(catName);
                    setHiddenCategories(newHidden);
                    // Do NOT call default onClick; state change drives re-render with value=0
                }
            }
        }
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="glass-panel p-4 flex flex-col h-80">
                <h3 className="label-text mb-2">Monthly Cashflow</h3>
                <div className="flex-grow relative min-h-0"><Bar data={monthlyData} options={monthlyChartOptions} /></div>
            </div>
            <div className="glass-panel p-4 flex flex-col h-80">
                <h3 className="label-text mb-2">Category Breakdown (Volume)</h3>
                <div className="flex-grow relative min-h-0"><Doughnut data={catData} options={doughnutOptions} /></div>
            </div>
            <div className="glass-panel p-4 flex flex-col h-80">
                <h3 className="label-text mb-2">Top Payers (Count)</h3>
                <div className="flex-grow relative min-h-0"><Bar data={payerCountData} options={{...chartOptions, indexAxis: 'y'}} /></div>
            </div>
            <div className="glass-panel p-4 flex flex-col h-80">
                <h3 className="label-text mb-2">Top Payers (ISK)</h3>
                <div className="flex-grow relative min-h-0"><Bar data={payerIskData} options={{...chartOptions, indexAxis: 'y'}} /></div>
            </div>
        </div>
    );
};

export default ManagementSRP;