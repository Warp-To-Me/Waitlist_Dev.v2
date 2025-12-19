import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchCommandWorkflows, createCommandWorkflow, updateCommandStep, deleteCommandWorkflow } from '../../store/slices/commandSlice';
import SmartPagination from '../../components/SmartPagination';
import { apiCall } from '../../utils/api';
import { format } from 'date-fns';
import { Loader2, Plus, Check, X, AlertTriangle, Trash2 } from 'lucide-react';
import { toast } from 'react-hot-toast';

const ManagementCommandWorkflow = () => {
  const dispatch = useDispatch();
  const { items, total, workflowSteps, status, stepUpdateStatus } = useSelector((state) => state.command);
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ target_user_id: '', program: 'Resident', action: 'Confirmed' });
  const [userSearch, setUserSearch] = useState('');
  const [userSearchResults, setUserSearchResults] = useState([]);
  
  const [banReasonModal, setBanReasonModal] = useState({ open: false, entryId: null, step: null });
  const [banReason, setBanReason] = useState('');

  useEffect(() => {
    dispatch(fetchCommandWorkflows({ limit: pageSize, offset: (page - 1) * pageSize }));
  }, [dispatch, page, pageSize]);

  const handleSearchUsers = async (query) => {
    setUserSearch(query);
    if (query.length > 2) {
      try {
        const res = await apiCall(`/api/mgmt/search_users/?q=${query}`);
        const data = await res.json();
        setUserSearchResults(data.results || []);
      } catch (err) {
        console.error(err);
      }
    } else {
      setUserSearchResults([]);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!formData.target_user_id) {
        toast.error('Please select a user');
        return;
    }
    await dispatch(createCommandWorkflow(formData));
    setShowModal(false);
    setFormData({ target_user_id: '', program: 'Resident', action: 'Confirmed' });
    setUserSearch('');
    // Refresh
    dispatch(fetchCommandWorkflows({ limit: pageSize, offset: (page - 1) * pageSize }));
    toast.success('Workflow Entry Created');
  };

  const handleStepClick = (entry, step) => {
    const currentValue = entry.checklist[step];
    
    // If it's the "Waitlist" step and we are turning it ON
    if (step === 'Waitlist' && !currentValue) {
      // Check if this action likely involves a Ban
      const isBanAction = ['Park', 'Ban'].includes(entry.action);
      if (isBanAction) {
        setBanReasonModal({ open: true, entryId: entry.id, step });
        return;
      }
    }
    
    dispatch(updateCommandStep({ 
        entryId: entry.id, 
        step, 
        value: !currentValue 
    })).unwrap()
       .then(() => toast.success('Updated'))
       .catch(err => toast.error(`Failed: ${err}`));
  };

  const confirmBanStep = () => {
      dispatch(updateCommandStep({
          entryId: banReasonModal.entryId,
          step: banReasonModal.step,
          value: true,
          meta: { reason: banReason }
      })).unwrap()
         .then(() => {
             toast.success('Ban Applied & Step Updated');
             setBanReasonModal({ open: false, entryId: null, step: null });
             setBanReason('');
         })
         .catch(err => toast.error(`Failed: ${err}`));
  };

  const handleDelete = (id) => {
      if (confirm('Are you sure you want to delete this entry?')) {
          dispatch(deleteCommandWorkflow(id))
            .unwrap()
            .then(() => toast.success('Entry Deleted'))
            .catch(err => toast.error(err));
      }
  };

  return (
    <div className="p-4">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-xl font-bold text-slate-100">Command Onboarding</h1>
        <button 
          onClick={() => setShowModal(true)}
          className="btn btn-primary btn-sm flex items-center gap-2"
        >
          <Plus size={16} /> New Entry
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
              <th className="p-2">Date</th>
              <th className="p-2">Target</th>
              <th className="p-2">Program</th>
              <th className="p-2">Action</th>
              {workflowSteps.map(step => (
                <th key={step} className="p-2 text-center whitespace-nowrap">{step}</th>
              ))}
              <th className="p-2">Issuer</th>
              <th className="p-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map(entry => (
              <tr key={entry.id} className="border-b border-slate-800 hover:bg-slate-800/30 text-sm">
                <td className="p-2 text-slate-300 whitespace-nowrap text-xs">
                  {format(new Date(entry.created_at), 'yyyy-MM-dd')}
                </td>
                <td className="p-2 text-slate-200 font-medium">{entry.target_username}</td>
                <td className="p-2 text-blue-400 text-xs">{entry.program}</td>
                <td className="p-2 text-yellow-400 text-xs">{entry.action}</td>
                
                {workflowSteps.map(step => {
                  const isChecked = entry.checklist[step];
                  const updateState = stepUpdateStatus[`${entry.id}-${step}`];
                  const isLoading = updateState === 'pending';
                  const isWaitlist = step === 'Waitlist';

                  return (
                    <td key={step} className="p-2 text-center">
                      <button
                        onClick={() => handleStepClick(entry, step)}
                        disabled={isLoading}
                        className={`
                          w-5 h-5 rounded border flex items-center justify-center transition-colors mx-auto
                          ${isChecked 
                            ? 'bg-green-600 border-green-500 text-white' 
                            : 'bg-slate-800 border-slate-600 text-transparent hover:border-slate-400'}
                          ${isWaitlist && !isChecked ? 'border-blue-500' : ''}
                        `}
                        title={isWaitlist ? "Click to trigger automated permissions" : ""}
                      >
                         {isLoading ? <Loader2 size={12} className="animate-spin text-white" /> : <Check size={12} />}
                      </button>
                    </td>
                  );
                })}
                
                <td className="p-2 text-slate-400 text-xs">{entry.issuer_username}</td>
                <td className="p-2 text-right">
                    <button
                        onClick={() => handleDelete(entry.id)}
                        className="text-slate-500 hover:text-red-400 transition-colors p-1"
                        title="Delete Entry"
                    >
                        <Trash2 size={14} />
                    </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4">
        <SmartPagination
          currentPage={page}
          totalItems={total}
          pageSize={pageSize}
          onPageChange={setPage}
        />
      </div>

      {/* CREATE MODAL */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-md shadow-xl">
            <h2 className="text-xl font-bold mb-4 text-white">New Workflow Entry</h2>
            
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Target User</label>
                <div className="relative">
                    <input 
                        type="text"
                        className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white"
                        placeholder="Search pilot..."
                        value={userSearch}
                        onChange={(e) => handleSearchUsers(e.target.value)}
                    />
                    {userSearchResults.length > 0 && (
                        <div className="absolute top-full left-0 right-0 bg-slate-800 border border-slate-600 mt-1 max-h-48 overflow-y-auto rounded z-10">
                            {userSearchResults.map(u => (
                                <div 
                                    key={u.id}
                                    className="p-2 hover:bg-slate-700 cursor-pointer text-slate-200"
                                    onClick={() => {
                                        setFormData({...formData, target_user_id: u.id});
                                        setUserSearch(`${u.username} (Main: ${u.main_character})`);
                                        setUserSearchResults([]);
                                    }}
                                >
                                    {u.username} <span className="text-slate-500 text-xs">Main: {u.main_character}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">Program</label>
                    <select 
                        className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white"
                        value={formData.program}
                        onChange={e => setFormData({...formData, program: e.target.value})}
                    >
                        {['Resident', 'LC', 'TFC', 'FC', 'Training CT', 'Certified Trainer', 'Officer', 'Leadership', 'Line Pilot'].map(p => (
                            <option key={p} value={p}>{p}</option>
                        ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">Action</label>
                    <select 
                        className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white"
                        value={formData.action}
                        onChange={e => setFormData({...formData, action: e.target.value})}
                    >
                        {['Confirmed', 'Denied', 'Review', 'Removal-CC', 'Demotion', 'Park', 'Un-Park', 'Ban'].map(a => (
                            <option key={a} value={a}>{a}</option>
                        ))}
                    </select>
                  </div>
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 text-slate-300 hover:text-white">Cancel</button>
                <button type="submit" className="btn btn-primary">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* BAN REASON MODAL */}
      {banReasonModal.open && (
         <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-slate-900 border border-red-900/50 rounded-lg p-6 w-full max-w-md shadow-xl">
                 <h2 className="text-xl font-bold mb-4 text-red-400 flex items-center gap-2">
                     <AlertTriangle size={20} /> Ban Confirmation
                 </h2>
                 <p className="text-slate-300 mb-4 text-sm">
                     This action will apply a system ban to the user. Please provide a reason.
                 </p>
                 
                 <textarea
                    className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white min-h-[100px]"
                    placeholder="Enter ban reason..."
                    value={banReason}
                    onChange={e => setBanReason(e.target.value)}
                 />
                 
                 <div className="flex justify-end gap-3 mt-6">
                    <button 
                        onClick={() => setBanReasonModal({open: false, entryId: null, step: null})}
                        className="px-4 py-2 text-slate-300"
                    >Cancel</button>
                    <button 
                        onClick={confirmBanStep}
                        disabled={!banReason.trim()}
                        className="btn bg-red-600 hover:bg-red-500 text-white"
                    >
                        Confirm Ban
                    </button>
                 </div>
            </div>
         </div>
      )}

    </div>
  );
};

export default ManagementCommandWorkflow;
