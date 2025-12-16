import React, { useEffect, useState } from 'react';
import { ArrowLeft, Search } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import SmartPagination from '../../components/SmartPagination';

const ManagementBanAudit = () => {
    const [logs, setLogs] = useState([]);
    const [searchParams, setSearchParams] = useSearchParams();
    const query = searchParams.get('q') || '';
    const page = parseInt(searchParams.get('page')) || 1;
    const [limit, setLimit] = useState(20);
    const [pagination, setPagination] = useState({ total: 1, current: 1 });

    useEffect(() => {
        fetch(`/api/management/bans/audit/?q=${encodeURIComponent(query)}&page=${page}&limit=${limit}`)
            .then(res => res.json())
            .then(data => {
                setLogs(data.logs || []);
                setPagination(data.pagination || { total: 1, current: 1 });
            });
    }, [query, page, limit]);

    const handleSearch = (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        setSearchParams({ q: formData.get('q'), page: 1 });
    };

    const handlePageChange = (newPage) => {
        setSearchParams({ q: query, page: newPage });
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-center gap-4 border-b border-white/5 pb-6">
                <div className="flex-grow">
                    <h1 className="heading-1">Ban Audit Log</h1>
                    <div className="flex items-center gap-4 mt-1">
                        <p className="text-slate-400 text-sm">History of all ban-related actions.</p>
                        <Link to="/management/bans" className="text-xs text-brand-400 hover:text-white transition flex items-center gap-1">
                            <ArrowLeft size={12} /> Manage Bans
                        </Link>
                    </div>
                </div>

                <form onSubmit={handleSearch} className="w-full md:w-auto relative group">
                    <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none transition group-focus-within:text-brand-500">
                        <Search className="w-5 h-5 text-slate-500" />
                    </div>
                    <input 
                        type="text" 
                        name="q" 
                        defaultValue={query}
                        className="input-field pl-10 md:w-64 bg-dark-900/50 border-white/10 focus:border-brand-500"
                        placeholder="Search user or details..." 
                    />
                </form>
            </div>

            {/* Table */}
            <div className="glass-panel overflow-hidden">
                {/* Pagination Controls Top */}
                <div className="p-3 border-b border-white/5 bg-slate-900/50 flex justify-between items-center">
                    <h3 className="label-text mb-0 w-1/3">Audit Entries</h3>
                    <div className="w-1/3 flex justify-center">
                        <SmartPagination
                            current={page}
                            total={pagination.total || 1}
                            onChange={handlePageChange}
                        />
                    </div>
                    <div className="w-1/3 flex justify-end">
                        <select
                            value={limit}
                            onChange={(e) => {
                                setLimit(Number(e.target.value));
                                setSearchParams({ q: query, page: 1 }); // Reset to page 1 on limit change
                            }}
                            className="bg-black/30 border border-slate-700 text-slate-300 text-xs rounded px-2 py-1 outline-none focus:border-brand-500"
                        >
                            <option value="10">10 Rows</option>
                            <option value="20">20 Rows</option>
                            <option value="25">25 Rows</option>
                            <option value="50">50 Rows</option>
                            <option value="100">100 Rows</option>
                        </select>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-slate-400">
                        <thead className="text-xs uppercase bg-white/5 text-slate-300 font-bold border-b border-white/5">
                            <tr>
                                <th className="px-6 py-4">Timestamp</th>
                                <th className="px-6 py-4">Action</th>
                                <th className="px-6 py-4">Target User</th>
                                <th className="px-6 py-4">Performed By</th>
                                <th className="px-6 py-4">Details</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-slate-300">
                            {logs.map(log => (
                                <tr key={log.timestamp + log.action} className="hover:bg-white/5 transition group">
                                    <td className="px-6 py-4 whitespace-nowrap font-mono text-xs">
                                        {new Date(log.timestamp).toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4">
                                        {log.action === 'create' && <span className="badge badge-red bg-red-900/20 text-red-400 border-red-500/30">BANNED</span>}
                                        {log.action === 'update' && <span className="badge badge-brand bg-amber-900/20 text-amber-400 border-amber-500/30">UPDATED</span>}
                                        {log.action === 'remove' && <span className="badge badge-green bg-green-900/20 text-green-400 border-green-500/30">REMOVED</span>}
                                        {log.action === 'expire' && <span className="badge badge-slate bg-slate-800 text-slate-400 border-slate-600">EXPIRED</span>}
                                        {!['create', 'update', 'remove', 'expire'].includes(log.action) && <span className="badge badge-slate">{log.action.toUpperCase()}</span>}
                                    </td>
                                    <td className="px-6 py-4 font-bold text-white">
                                        {log.target_name || "Unknown"}
                                    </td>
                                    <td className="px-6 py-4 text-slate-400">
                                        {log.actor_name || "System"}
                                    </td>
                                    <td className="px-6 py-4 text-xs text-slate-500 italic max-w-md truncate group-hover:text-slate-300 transition" title={log.details}>
                                        {log.details}
                                    </td>
                                </tr>
                            ))}
                            {logs.length === 0 && (
                                <tr>
                                    <td colSpan="5" className="p-12 text-center text-slate-500 italic">
                                        No audit logs found.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination Controls Bottom */}
                <div className="p-3 border-t border-white/5 bg-slate-900/50 flex justify-center items-center">
                    <SmartPagination
                        current={page}
                        total={pagination.total || 1}
                        onChange={handlePageChange}
                    />
                </div>
            </div>
        </div>
    );
};

export default ManagementBanAudit;
