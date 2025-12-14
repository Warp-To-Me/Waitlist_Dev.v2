import React, { useEffect, useState } from 'react';
import { Database } from 'lucide-react';

const ManagementSDE = () => {
    const [data, setData] = useState(null);

    useEffect(() => {
        fetch('/api/management/sde/')
            .then(res => res.json())
            .then(setData);
    }, []);

    if (!data) return <div>Loading Database Stats...</div>;

    return (
        <div className="space-y-6">
            <h1 className="heading-1">SDE Database</h1>

            <div className="grid grid-cols-3 gap-6">
                <div className="glass-panel p-6">
                    <div className="label-text">Items</div>
                    <div className="text-3xl font-mono text-white">{data.counts.items.toLocaleString()}</div>
                </div>
                <div className="glass-panel p-6">
                    <div className="label-text">Groups</div>
                    <div className="text-3xl font-mono text-white">{data.counts.groups.toLocaleString()}</div>
                </div>
                <div className="glass-panel p-6">
                    <div className="label-text">Attributes</div>
                    <div className="text-3xl font-mono text-white">{data.counts.attrs.toLocaleString()}</div>
                </div>
            </div>

            <div className="glass-panel p-6">
                <h3 className="text-lg font-bold text-white mb-4">Top Item Groups</h3>
                <div className="h-64 flex items-end justify-between gap-2">
                    {data.chart.data.map((val, idx) => (
                        <div key={idx} className="flex-1 flex flex-col justify-end group relative">
                            <div
                                className="bg-brand-600/50 hover:bg-brand-500 transition rounded-t w-full"
                                style={{ height: `${(val / Math.max(...data.chart.data)) * 100}%` }}
                            ></div>
                            <div className="absolute bottom-0 w-full text-[10px] text-slate-500 truncate text-center opacity-0 group-hover:opacity-100 transition">
                                {data.chart.labels[idx]}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default ManagementSDE;