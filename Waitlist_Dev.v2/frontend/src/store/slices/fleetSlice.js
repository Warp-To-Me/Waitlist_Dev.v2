import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  data: null, // The full fleet object
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
  loading: true,
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
    // In a real app, you'd have specific message types like 'USER_JOINED', 'USER_LEFT'
    // For now, we assume the backend might send a full snapshot OR partials
    handleWsMessage: (state, action) => {
        const msg = action.payload;
        if (msg.type === 'fleet_update') {
            // Full snapshot update
            if (msg.data) {
                if (msg.data.fleet) state.data = msg.data.fleet;
                if (msg.data.columns) state.columns = msg.data.columns;
            }
        }
        // Add more handlers for granular updates here
    }
  },
  extraReducers: (builder) => {
      builder
        .addCase('WS_CONNECTED', (state) => {
            state.status = 'connected';
        })
        .addCase('WS_DISCONNECTED', (state) => {
            state.status = 'disconnected';
        })
        .addCase('WS_MESSAGE_RECEIVED', (state, action) => {
             // Dispatch to internal reducer logic
             fleetSlice.caseReducers.handleWsMessage(state, action);
        });
  }
});

export const { setFleetData, setFleetError, setConnectionStatus } = fleetSlice.actions;

export const selectFleetData = (state) => state.fleet.data;
export const selectFleetColumns = (state) => state.fleet.columns;
export const selectFleetPermissions = (state) => state.fleet.permissions;
export const selectFleetLoading = (state) => state.fleet.loading;
export const selectFleetError = (state) => state.fleet.error;
export const selectConnectionStatus = (state) => state.fleet.status;

export default fleetSlice.reducer;
