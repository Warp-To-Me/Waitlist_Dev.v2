import React, { useEffect, useState } from 'react';
import { RefreshCw, DollarSign, TrendingUp, TrendingDown } from 'lucide-react';

const ManagementSRP = () => {
    const [status, setStatus] = useState(null);
    const [summary, setSummary] = useState(null);

    useEffect(() => {
        // Fetch Status
        fetch('/api/srp/status/')
            .then(res => res.json())
            .then(setStatus);

        // Fetch Data (Simplified for dashboard overview)
        // In a real implementation, we would pass date filters, etc.
        fetch('/api/srp/data/?limit=10')
            .then(res => res.json())
            .then(setSummary);
    }, []);

    const handleSync = () => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch('/api/mgmt/srp/sync/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf }
        })
        .then(res => res.json())
        .then(data => alert(data.message));
    };

    if (!status || !summary) return <div>Loading Financial Data...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="heading-1">SRP Financials</h1>
                <div className="flex gap-4 items-center">
                    <div className="text-right text-xs text-slate-400">
                        <div>Last Sync: {status.last_sync ? new Date(status.last_sync).toLocaleString() : 'Never'}</div>
                        <div>Next Sync: {status.next_sync ? new Date(status.next_sync).toLocaleTimeString() : 'Unknown'}</div>
                    </div>
                    <button onClick={handleSync} className="btn-secondary text-xs">
                        <RefreshCw size={14} /> Sync Wallet
                    </button>
                </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-3 gap-6">
                <div className="glass-panel p-6 border-l-4 border-green-500">
                    <div className="flex items-center gap-2 text-green-400 font-bold uppercase text-xs mb-2">
                        <TrendingUp size={16} /> Income
                    </div>
                    <div className="text-2xl font-mono text-white">
                        {summary.summary.income.toLocaleString()} ISK
                    </div>
                </div>
                <div className="glass-panel p-6 border-l-4 border-red-500">
                    <div className="flex items-center gap-2 text-red-400 font-bold uppercase text-xs mb-2">
                        <TrendingDown size={16} /> Expenses
                    </div>
                    <div className="text-2xl font-mono text-white">
                        {Math.abs(summary.summary.outcome).toLocaleString()} ISK
                    </div>
                </div>
                <div className="glass-panel p-6 border-l-4 border-brand-500">
                    <div className="flex items-center gap-2 text-brand-400 font-bold uppercase text-xs mb-2">
                        <DollarSign size={16} /> Net Change
                    </div>
                    <div className={`text-2xl font-mono ${summary.summary.net >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                        {summary.summary.net > 0 ? '+' : ''}{summary.summary.net.toLocaleString()} ISK
                    </div>
                </div>
            </div>

            {/* Recent Transactions */}
            <div className="glass-panel overflow-hidden">
                <div className="p-4 bg-white/5 font-bold text-slate-300 text-sm uppercase">Recent Transactions</div>
                <table className="w-full text-left">
                    <tbody className="divide-y divide-white/5 text-sm text-slate-300">
                        {summary.transactions.map(tx => (
                            <tr key={tx.entry_id} className="hover:bg-white/5 transition">
                                <td className="p-3 text-xs text-slate-400 font-mono">
                                    {new Date(tx.date).toLocaleDateString()}
                                </td>
                                <td className="p-3 font-medium text-white">
                                    {tx.first_party_name || "Unknown"} 
                                    <span className="text-slate-500 mx-2">→</span>
                                    {tx.second_party_name || "Unknown"}
                                </td>
                                <td className="p-3 text-slate-400 text-xs truncate max-w-[200px]">
                                    {tx.reason || tx.ref_type}
                                </td>
                                <td className={`p-3 font-mono text-right ${tx.amount > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {tx.amount.toLocaleString()}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ManagementSRP;