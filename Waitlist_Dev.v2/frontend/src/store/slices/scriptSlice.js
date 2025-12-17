import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiCall } from '../../utils/api';

export const fetchScripts = createAsyncThunk(
    'scripts/fetchScripts',
    async (_, { rejectWithValue }) => {
        try {
            const response = await apiCall('/api/mgmt/scripts/');
            return response;
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const runScript = createAsyncThunk(
    'scripts/runScript',
    async ({ name, args }, { rejectWithValue }) => {
        try {
            const response = await apiCall('/api/mgmt/scripts/run/', {
                method: 'POST',
                body: JSON.stringify({ name, args })
            });
            if (response.success) {
                return response;
            } else {
                return rejectWithValue(response.error);
            }
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const stopScript = createAsyncThunk(
    'scripts/stopScript',
    async (scriptId, { rejectWithValue }) => {
        try {
            const response = await apiCall('/api/mgmt/scripts/stop/', {
                method: 'POST',
                body: JSON.stringify({ script_id: scriptId })
            });
            if (response.success) {
                return scriptId;
            } else {
                return rejectWithValue(response.error);
            }
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

const scriptSlice = createSlice({
    name: 'scripts',
    initialState: {
        available: [],
        active: [],
        status: 'idle', // 'idle' | 'loading' | 'succeeded' | 'failed'
        error: null,
        runStatus: 'idle', // For the run button operation
        stopStatus: 'idle'
    },
    reducers: {
        clearScriptError: (state) => {
            state.error = null;
        }
    },
    extraReducers: (builder) => {
        // Fetch
        builder.addCase(fetchScripts.pending, (state) => {
            if (state.status === 'idle') state.status = 'loading';
        });
        builder.addCase(fetchScripts.fulfilled, (state, action) => {
            state.status = 'succeeded';
            // Defensive coding: ensure arrays
            state.available = Array.isArray(action.payload?.available) ? action.payload.available : [];
            state.active = Array.isArray(action.payload?.active) ? action.payload.active : [];
        });
        builder.addCase(fetchScripts.rejected, (state, action) => {
            state.status = 'failed';
            state.error = action.payload;
        });

        // Run
        builder.addCase(runScript.pending, (state) => {
            state.runStatus = 'loading';
        });
        builder.addCase(runScript.fulfilled, (state) => {
            state.runStatus = 'succeeded';
        });
        builder.addCase(runScript.rejected, (state, action) => {
            state.runStatus = 'failed';
            state.error = action.payload;
        });

        // Stop
        builder.addCase(stopScript.pending, (state) => {
            state.stopStatus = 'loading';
        });
        builder.addCase(stopScript.fulfilled, (state, action) => {
            state.stopStatus = 'succeeded';
            // Optimistically set status to stopping/failed for the item?
            // Actually fetchScripts polling will handle the update.
        });
        builder.addCase(stopScript.rejected, (state, action) => {
            state.stopStatus = 'failed';
            state.error = action.payload;
        });
    }
});

export const { clearScriptError } = scriptSlice.actions;

export const selectAvailableScripts = (state) => state.scripts.available || [];
export const selectActiveScripts = (state) => state.scripts.active || [];
export const selectScriptStatus = (state) => state.scripts.status;

export default scriptSlice.reducer;
