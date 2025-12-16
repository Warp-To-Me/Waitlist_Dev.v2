import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Search } from 'lucide-react';
import { 
    fetchUsers, setQuery, setPage, 
    selectUsersList, selectUsersQuery, selectUsersPagination 
} from '../../store/slices/usersSlice';

const ManagementUsers = () => {
    const dispatch = useDispatch();
    const users = useSelector(selectUsersList);
    const query = useSelector(selectUsersQuery);
    const pagination = useSelector(selectUsersPagination);

    // Debounce search
    useEffect(() => {
        const timeout = setTimeout(() => {
            dispatch(fetchUsers({ query, page: pagination.current }));
        }, 300);
        return () => clearTimeout(timeout);
    }, [query, pagination.current, dispatch]);

    const handleSearch = (e) => {
        dispatch(setQuery(e.target.value));
    };

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
                        onChange={handleSearch}
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