import { createSlice } from '@reduxjs/toolkit';

const initialState = {
    celeryStatus: null, // Stores the raw JSON data from the backend
    activeTasks: [],    // Real-time task stream
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
            const payload = action.payload;

            // Check if this is a task update
            if (payload.type === 'celery_task_update') {
                const { event, task } = payload;
                const now = Date.now();

                if (event === 'started') {
                    // Add to list (or update if ID exists, though unlikely for new start)
                    state.activeTasks.unshift({
                        ...task,
                        status: 'STARTED',
                        receivedAt: now
                    });
                    // Keep list size manageable
                    if (state.activeTasks.length > 100) state.activeTasks.pop();
                }
                else if (event === 'finished') {
                    // Update existing task
                    const existing = state.activeTasks.find(t => t.id === task.id);
                    if (existing) {
                        existing.state = task.state; // SUCCESS / FAILURE
                        existing.finishedAt = now;
                        // Trigger fade out logic in UI via finishedAt
                    }
                }
            }
            else {
                // Regular System Status Update
                // Merge the legacy status object
                state.celeryStatus = payload;
            }
        },
        pruneTasks: (state) => {
            const now = Date.now();
            state.activeTasks = state.activeTasks.filter(t => {
                // 1. Remove tasks that finished more than 4 seconds ago (2s visible + 1s fade + buffer)
                if (t.finishedAt) {
                    return (now - t.finishedAt) < 4000;
                }

                // 2. Safety Net: Remove tasks stuck in 'STARTED' for > 15 minutes
                if (t.receivedAt && (now - t.receivedAt) > 15 * 60 * 1000) {
                    return false;
                }

                return true; // Keep active tasks
            });
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

export const { setSystemStatus, pruneTasks } = systemSlice.actions;

export const selectCeleryStatus = (state) => state.system.celeryStatus;
export const selectSystemConnectionStatus = (state) => state.system.status;
export const selectActiveTasks = (state) => state.system.activeTasks;

export default systemSlice.reducer;
