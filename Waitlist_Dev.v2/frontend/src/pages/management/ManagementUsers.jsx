import React, { useEffect, useState } from 'react';
import { Search } from 'lucide-react';

const ManagementUsers = () => {
    const [users, setUsers] = useState([]);
    const [query, setQuery] = useState('');
    const [page, setPage] = useState(1);

    useEffect(() => {
        const timeout = setTimeout(() => {
            fetch(`/api/management/users/?q=${query}&page=${page}`)
                .then(res => res.json())
                .then(data => setUsers(data.users || []));
        }, 300);
        return () => clearTimeout(timeout);
    }, [query, page]);

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="heading-1">User Management</h1>
                <div className="relative">
                    <Search className="absolute left-3 top-2.5 text-slate-500" size={16} />
                    <input
                        type="text"
                        placeholder="Search pilots..."
                        className="input-field pl-10 w-64"
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                    />
                </div>
            </div>

            <div className="glass-panel overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-white/5 border-b border-white/5 text-xs text-slate-400 uppercase">
                            <th className="p-4 font-bold">Character</th>
                            <th className="p-4 font-bold">Main</th>
                            <th className="p-4 font-bold">Corp</th>
                            <th className="p-4 font-bold">Alts</th>
                            <th className="p-4 font-bold text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-sm text-slate-300">
                        {users.map(u => (
                            <tr key={u.id} className="hover:bg-white/5 transition">
                                <td className="p-4 font-medium text-white">{u.character_name}</td>
                                <td className="p-4 text-brand-400">{u.main_character_name}</td>
                                <td className="p-4">{u.corporation_name}</td>
                                <td className="p-4">{u.linked_count}</td>
                                <td className="p-4 text-right">
                                    <button className="text-brand-400 hover:text-white transition">Inspect</button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {users.length === 0 && <div className="p-8 text-center text-slate-500">No users found.</div>}
            </div>
        </div>
    );
};

export default ManagementUsers;