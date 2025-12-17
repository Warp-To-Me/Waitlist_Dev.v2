import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  celeryStatus: null, // Stores the raw HTML or data from the backend
  status: 'disconnected', // 'connecting' | 'connected' | 'disconnected'
};

export const systemSlice = createSlice({
  name: 'system',
  initialState,
  reducers: {
    setSystemStatus: (state, action) => {
      state.status = action.payload;
    },
    // Handler for WebSocket messages
    handleWsMessage: (state, action) => {
        const { key, data } = action.payload;
        // Only process messages for the 'system' socket
        if (key !== 'system') return;

        // The backend sends { html: "..." } or { data: ... }
        if (data.html) {
            state.celeryStatus = data.html;
        } else if (data.data) {
             // New JSON format
             state.celeryStatus = data.data;
        }
    }
  },
  extraReducers: (builder) => {
      builder
        .addCase('WS_CONNECTED', (state, action) => {
            if (action.payload.key === 'system') {
                state.status = 'connected';
            }
        })
        .addCase('WS_DISCONNECTED', (state, action) => {
            if (action.payload.key === 'system') {
                state.status = 'disconnected';
            }
        })
        .addCase('WS_MESSAGE_RECEIVED', (state, action) => {
             // Dispatch to internal reducer logic
             systemSlice.caseReducers.handleWsMessage(state, action);
        });
  }
});

export const { setSystemStatus } = systemSlice.actions;

export const selectCeleryStatus = (state) => state.system.celeryStatus;
export const selectSystemConnectionStatus = (state) => state.system.status;

export default systemSlice.reducer;
