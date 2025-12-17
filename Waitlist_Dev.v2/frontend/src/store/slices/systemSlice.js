import { createSlice } from '@reduxjs/toolkit';

const initialState = {
    celeryStatus: null, // Stores the raw JSON data from the backend
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
            // The backend sends a JSON object with telemetry data.
            // Legacy format used { html: ... }, but now we receive the data object directly.
            // We store the entire payload as celeryStatus.
            state.celeryStatus = action.payload;
        }
    },
    extraReducers: (builder) => {
        builder
            .addCase('WS_CONNECTED', (state, action) => {
                if (action.payload.channelKey === 'system') {
                    state.status = 'connected';
                }
            })
            .addCase('WS_DISCONNECTED', (state, action) => {
                if (action.payload.channelKey === 'system') {
                    state.status = 'disconnected';
                }
            })
            .addCase('WS_MESSAGE_RECEIVED', (state, action) => {
                if (action.payload.channelKey === 'system') {
                    // Dispatch to internal reducer logic with unwrapped message
                    systemSlice.caseReducers.handleWsMessage(state, { payload: action.payload.msg });
                }
            });
    }
});

export const { setSystemStatus } = systemSlice.actions;

export const selectCeleryStatus = (state) => state.system.celeryStatus;
export const selectSystemConnectionStatus = (state) => state.system.status;

export default systemSlice.reducer;
