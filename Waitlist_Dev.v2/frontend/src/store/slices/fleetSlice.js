import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiCall } from '../../utils/api';

// --- Thunks ---

export const fetchFleetList = createAsyncThunk(
  'fleet/fetchList',
  async (_, { rejectWithValue }) => {
    try {
      const res = await apiCall('/api/management/fleets/');
      const data = await res.json();
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const createFleet = createAsyncThunk(
  'fleet/create',
  async (payload, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      
      // Remap name -> fleet_name for the structured endpoint
      const bodyPayload = {
          ...payload,
          fleet_name: payload.name
      };
      
      const res = await apiCall('/api/management/fleets/create_structured/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(bodyPayload)
      });
      const data = await res.json();
      if (data.success) return data; // structured endpoint returns success: true
      throw new Error(data.error || "Creation failed");
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const closeFleet = createAsyncThunk(
  'fleet/close',
  async (fleetId, { dispatch, rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall('/api/management/fleets/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ action: 'close', fleet_id: fleetId })
      });
      const data = await res.json();
      if (data.success) {
          dispatch(fetchFleetList()); // Refresh list
          return data;
      }
      throw new Error(data.error);
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const deleteFleet = createAsyncThunk(
  'fleet/delete',
  async (fleetId, { dispatch, rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall('/api/management/fleets/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ action: 'delete', fleet_id: fleetId })
      });
      const data = await res.json();
      if (data.success) {
          dispatch(fetchFleetList()); 
          return data;
      }
      throw new Error(data.error);
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchFleetSettings = createAsyncThunk(
  'fleet/fetchSettings',
  async (token, { rejectWithValue }) => {
    try {
      const res = await apiCall(`/api/management/fleets/${token}/settings/`);
      const data = await res.json();
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const updateFleetSettings = createAsyncThunk(
  'fleet/updateSettings',
  async ({ token, payload }, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall(`/api/management/fleets/${token}/update_settings/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) return data;
      throw new Error(data.error);
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const linkEsiFleet = createAsyncThunk(
  'fleet/linkEsi',
  async (token, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall(`/api/management/fleets/${token}/link_esi/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf }
      });
      const data = await res.json();
      if (data.success) return data;
      throw new Error(data.error);
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const closeFleetByToken = createAsyncThunk(
  'fleet/closeByToken',
  async (token, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall(`/api/management/fleets/${token}/close/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf }
      });
      const data = await res.json();
      if (data.success) return data;
      throw new Error(data.error);
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const takeOverFleet = createAsyncThunk(
  'fleet/takeOver',
  async (token, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall(`/api/management/fleets/${token}/take_over/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf }
      });
      const data = await res.json();
      if (data.success) return data; // { success: true, warning: '...' }
      throw new Error(data.error || data.message);
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchFleetHistory = createAsyncThunk(
  'fleet/fetchHistory',
  async (token, { rejectWithValue }) => {
    try {
      const res = await apiCall(`/api/management/fleets/${token}/history/`);
      const data = await res.json();
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchFleetSetupInit = createAsyncThunk(
  'fleet/fetchSetupInit',
  async (_, { rejectWithValue }) => {
    try {
      const res = await apiCall('/api/management/fleets/setup/init/');
      const data = await res.json();
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const saveFleetTemplate = createAsyncThunk(
  'fleet/saveTemplate',
  async (payload, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall('/api/management/fleets/templates/save/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) return data.template;
      throw new Error(data.error);
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const deleteFleetTemplate = createAsyncThunk(
  'fleet/deleteTemplate',
  async (templateId, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall('/api/management/fleets/templates/delete/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ template_id: templateId })
      });
      const data = await res.json();
      if (data.success) return templateId;
      throw new Error(data.error);
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

// --- Slice ---

const initialState = {
  data: null, // The active fleet object (for Dashboard)
  
  // Management State
  list: [],
  settings: null, // For settings page (fleet, structure)
  templates: [], // Shared templates
  setup: { fc_chars: [] }, // Setup wizard state
  history: null, // For history page { fleet, stats, logs }
  canViewAdmin: false,
  
  status: 'idle', // 'idle' | 'connecting' | 'connected' | 'disconnected'
  columns: {
      pending: [],
      logi: [],
      dps: [],
      sniper: [],
      other: []
  },
  overview: null, // Fleet Overview (Hierarchy)
  permissions: {},
  user_status: {},
  
  // X-Up Modal data
  user_chars: [],

  loading: false, // General loading state for async ops
  error: null,
};

// Helper to remove entry from all columns
const removeEntry = (columns, entryId) => {
    Object.keys(columns).forEach(key => {
        columns[key] = columns[key].filter(e => e.id !== entryId);
    });
};

// Helper to insert entry sorted by creation time (Oldest first)
const insertSorted = (list, entry) => {
    const newTs = new Date(entry.created_at).getTime();
    let index = list.length;
    for (let i = 0; i < list.length; i++) {
        const childTs = new Date(list[i].created_at).getTime();
        if (newTs < childTs) {
            index = i;
            break;
        }
    }
    list.splice(index, 0, entry);
};

export const fleetSlice = createSlice({
  name: 'fleet',
  initialState,
  reducers: {
    setFleetData: (state, action) => {
        state.data = action.payload.fleet;
        state.columns = action.payload.columns;
        state.permissions = action.payload.permissions;
        state.user_status = action.payload.user_status;
        state.user_chars = action.payload.user_chars || []; // Load user characters with implants
        state.loading = false;
        state.error = null;
    },
    setFleetError: (state, action) => {
        state.error = action.payload;
        state.loading = false;
    },
    setConnectionStatus: (state, action) => {
        state.status = action.payload;
    },
    // Handler for generic WebSocket updates
    handleWsMessage: (state, action) => {
        const msg = action.payload;
        
        if (msg.type === 'fleet_overview') {
            // Update the FC Overview hierarchy
            state.overview = {
                member_count: msg.member_count,
                summary: msg.summary,
                hierarchy: msg.hierarchy
            };
            state.error = null; // Clear error on success
            return;
        }
        
        if (msg.type === 'fleet_success') {
            state.error = null;
            return;
        }

        if (msg.type === 'fleet_error') {
            state.error = msg.error;
            return;
        }

        if (msg.type === 'fleet_update') {
            // Meta updates (e.g. takeover)
            if (msg.action === 'fleet_meta' && msg.data && msg.data.fleet) {
                // Merge fleet data
                state.data = { ...state.data, ...msg.data.fleet };
                // Clear error if we just got a valid meta update
                if (state.error) state.error = null;
                return;
            }

            // Granular updates
            if (msg.action === 'remove') {
                removeEntry(state.columns, msg.entry_id);
                return;
            }

            if ((msg.action === 'add' || msg.action === 'move') && msg.data) {
                // Remove first (in case moving between columns)
                removeEntry(state.columns, msg.entry_id);
                
                const targetCol = msg.target_col || 'other';
                if (state.columns[targetCol]) {
                    insertSorted(state.columns[targetCol], msg.data);
                }
                return;
            }
            
            if (msg.action === 'update' && msg.data) {
                 // Find and update in place
                 Object.keys(state.columns).forEach(key => {
                     const idx = state.columns[key].findIndex(e => e.id === msg.entry_id);
                     if (idx !== -1) {
                         state.columns[key][idx] = msg.data;
                     }
                 });
                 return;
            }

            // Legacy fallback (if message has full fleet object)
            if (msg.data && msg.data.fleet) {
                state.data = msg.data.fleet;
                if (msg.data.columns) state.columns = msg.data.columns;
            }
        }
    }
  },
  extraReducers: (builder) => {
      builder
        // WS Events
        .addCase('WS_CONNECTED', (state, action) => {
             if (action.payload.channelKey === 'fleet') {
                 state.status = 'connected'; 
             }
        })
        .addCase('WS_DISCONNECTED', (state, action) => { 
             if (action.payload.channelKey === 'fleet') {
                 state.status = 'disconnected'; 
             }
        })
        .addCase('WS_MESSAGE_RECEIVED', (state, action) => {
             if (action.payload.channelKey === 'fleet') {
                 // Unwrap the message from the payload
                 fleetSlice.caseReducers.handleWsMessage(state, { payload: action.payload.msg });
             }
        })
        
        // List Fetch
        .addCase(fetchFleetList.pending, (state) => { state.loading = true; })
        .addCase(fetchFleetList.fulfilled, (state, action) => {
            state.loading = false;
            state.list = action.payload.fleets || [];
            state.canViewAdmin = action.payload.can_view_admin;
        })
        .addCase(fetchFleetList.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload;
        })

        // Create
        .addCase(createFleet.pending, (state) => { state.loading = true; })
        .addCase(createFleet.fulfilled, (state) => { state.loading = false; })
        .addCase(createFleet.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload;
        })
        
        // Settings
        .addCase(fetchFleetSettings.pending, (state) => { state.loading = true; })
        .addCase(fetchFleetSettings.fulfilled, (state, action) => {
            state.loading = false;
            // Extract templates to shared state
            state.templates = action.payload.templates || [];
            // Remove templates from settings to avoid duplication (optional but cleaner)
            const { templates, ...settings } = action.payload;
            state.settings = settings;
        })
        .addCase(fetchFleetSettings.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload;
        })
        
        // Setup Init
        .addCase(fetchFleetSetupInit.pending, (state) => { state.loading = true; })
        .addCase(fetchFleetSetupInit.fulfilled, (state, action) => {
            state.loading = false;
            state.setup.fc_chars = action.payload.fc_chars || [];
            state.templates = action.payload.templates || [];
        })
        .addCase(fetchFleetSetupInit.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload;
        })

        // Template Actions
        .addCase(saveFleetTemplate.pending, (state) => { state.loading = true; })
        .addCase(saveFleetTemplate.fulfilled, (state, action) => {
            state.loading = false;
            // Add or Update template in list
            const idx = state.templates.findIndex(t => t.id === action.payload.id);
            if (idx >= 0) state.templates[idx] = action.payload;
            else state.templates.push(action.payload);
        })
        .addCase(saveFleetTemplate.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload;
        })

        .addCase(deleteFleetTemplate.pending, (state) => { state.loading = true; })
        .addCase(deleteFleetTemplate.fulfilled, (state, action) => {
            state.loading = false;
            state.templates = state.templates.filter(t => t.id !== action.payload);
        })
        .addCase(deleteFleetTemplate.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload;
        })
        
        // Update Settings
        .addCase(updateFleetSettings.pending, (state) => { state.loading = true; })
        .addCase(updateFleetSettings.fulfilled, (state) => { state.loading = false; })
        .addCase(updateFleetSettings.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload;
        })
        
        // Link ESI
        .addCase(linkEsiFleet.fulfilled, (state, action) => {
             // We need to update the settings fleet ID locally
             if (state.settings && state.settings.fleet) {
                 state.settings.fleet.esi_fleet_id = action.payload.fleet_id;
             }
        })
        
        // Take Over
        .addCase(takeOverFleet.fulfilled, (state, action) => {
            // Update happens via WebSocket broadcast usually, but we can optimistically update here or handle warning
            state.error = null; // Clear connection error
        })

        // History
        .addCase(fetchFleetHistory.pending, (state) => { state.loading = true; })
        .addCase(fetchFleetHistory.fulfilled, (state, action) => {
            state.loading = false;
            state.history = action.payload;
        })
        .addCase(fetchFleetHistory.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload;
        });
  }
});

export const { setFleetData, setFleetError, setConnectionStatus } = fleetSlice.actions;

export const selectFleetData = (state) => state.fleet.data;
export const selectFleetList = (state) => state.fleet.list;
export const selectFleetSettings = (state) => state.fleet.settings;
export const selectFleetTemplates = (state) => state.fleet.templates;
export const selectFleetSetup = (state) => state.fleet.setup;
export const selectFleetHistory = (state) => state.fleet.history;
export const selectCanViewAdmin = (state) => state.fleet.canViewAdmin;
export const selectFleetColumns = (state) => state.fleet.columns;
export const selectFleetOverview = (state) => state.fleet.overview;
export const selectFleetPermissions = (state) => state.fleet.permissions;
export const selectUserChars = (state) => state.fleet.user_chars;
export const selectFleetLoading = (state) => state.fleet.loading;
export const selectFleetError = (state) => state.fleet.error;
export const selectConnectionStatus = (state) => state.fleet.status;

// Memoized-like selector (not using createSelector but efficient enough for this scope)
export const selectSiblingCategories = (state, characterId, excludeEntryId) => {
    const columns = state.fleet.columns;
    const categories = new Set();
    
    Object.values(columns).forEach(list => {
        list.forEach(entry => {
            if (entry.character.id === characterId && entry.id !== excludeEntryId) {
                // If the entry has a 'category' or 'real_category' field from backend
                // or if we infer it from the column key (less reliable for pending)
                // We use 'category' field added in serialization.
                if (entry.category && ['logi', 'dps', 'sniper'].includes(entry.category)) {
                    categories.add(entry.category);
                }
            }
        });
    });
    
    return Array.from(categories);
};

export default fleetSlice.reducer;
