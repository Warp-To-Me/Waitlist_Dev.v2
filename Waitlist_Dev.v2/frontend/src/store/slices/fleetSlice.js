import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

// --- Thunks ---

export const fetchFleetList = createAsyncThunk(
  'fleet/fetchList',
  async (_, { rejectWithValue }) => {
    try {
      const res = await fetch('/api/management/fleets/');
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
      const res = await fetch('/api/management/fleets/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'created') return data;
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
      const res = await fetch('/api/management/fleets/action/', {
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
      const res = await fetch('/api/management/fleets/action/', {
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
      const res = await fetch(`/api/management/fleets/${token}/settings/`);
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
      const res = await fetch(`/api/management/fleets/${token}/update_settings/`, {
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
      const res = await fetch(`/api/management/fleets/${token}/link_esi/`, {
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
      const res = await fetch(`/api/management/fleets/${token}/close/`, {
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

export const fetchFleetHistory = createAsyncThunk(
  'fleet/fetchHistory',
  async (token, { rejectWithValue }) => {
    try {
      const res = await fetch(`/api/management/fleets/${token}/history/`);
      const data = await res.json();
      return data;
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
  settings: null, // For settings page
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
  permissions: {},
  user_status: {},

  loading: false, // General loading state for async ops
  error: null,
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
        if (msg.type === 'fleet_update') {
            if (msg.data) {
                if (msg.data.fleet) state.data = msg.data.fleet;
                if (msg.data.columns) state.columns = msg.data.columns;
            }
        }
    }
  },
  extraReducers: (builder) => {
      builder
        // WS Events
        .addCase('WS_CONNECTED', (state) => { state.status = 'connected'; })
        .addCase('WS_DISCONNECTED', (state) => { state.status = 'disconnected'; })
        .addCase('WS_MESSAGE_RECEIVED', (state, action) => {
             fleetSlice.caseReducers.handleWsMessage(state, action);
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
            state.settings = action.payload;
        })
        .addCase(fetchFleetSettings.rejected, (state, action) => {
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
export const selectFleetHistory = (state) => state.fleet.history;
export const selectCanViewAdmin = (state) => state.fleet.canViewAdmin;
export const selectFleetColumns = (state) => state.fleet.columns;
export const selectFleetPermissions = (state) => state.fleet.permissions;
export const selectFleetLoading = (state) => state.fleet.loading;
export const selectFleetError = (state) => state.fleet.error;
export const selectConnectionStatus = (state) => state.fleet.status;

export default fleetSlice.reducer;
