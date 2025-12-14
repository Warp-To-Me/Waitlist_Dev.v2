import React, { useEffect, useState } from 'react';

const ManagementDashboard = () => {
    const [stats, setStats] = useState(null);

    useEffect(() => {
        fetch('/api/management/') // Maps to management_dashboard
            .then(res => res.json())
            .then(data => setStats(data));
    }, []);

    if (!stats) return <div>Loading Stats...</div>;

    return (
        <div className="space-y-6">
            <h1 className="heading-1">System Overview</h1>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard label="Total Users" value={stats.stats.total_users} />
                <StatCard label="Total Characters" value={stats.stats.total_characters} />
                <StatCard label="Active Fleets" value={stats.stats.active_fleets_count} />
                <StatCard label="Total Fleets History" value={stats.stats.total_fleets} />
            </div>

            {/* Placeholder for Charts */}
            <div className="glass-panel p-6 h-64 flex items-center justify-center text-slate-500">
                Waitlist Growth Chart (Coming Soon)
            </div>
        </div>
    );
};

const StatCard = ({ label, value }) => (
    <div className="glass-panel p-6">
        <div className="text-sm text-slate-500 font-bold uppercase tracking-wider mb-2">{label}</div>
        <div className="text-3xl font-mono text-white">{value}</div>
    </div>
);

export default ManagementDashboard;