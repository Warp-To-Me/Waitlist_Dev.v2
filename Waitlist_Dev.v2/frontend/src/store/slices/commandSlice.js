import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiCall } from '../../utils/api';

export const fetchCommandWorkflows = createAsyncThunk(
  'command/fetchCommandWorkflows',
  async ({ limit = 20, offset = 0 } = {}, { rejectWithValue }) => {
    try {
      const response = await apiCall(`/api/management/command/?limit=${limit}&offset=${offset}`);
      return response;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

export const createCommandWorkflow = createAsyncThunk(
  'command/createCommandWorkflow',
  async (payload, { rejectWithValue }) => {
    try {
      const response = await apiCall('/api/management/command/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      return response;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

export const updateCommandStep = createAsyncThunk(
  'command/updateCommandStep',
  async ({ entryId, step, value, meta }, { rejectWithValue }) => {
    try {
      const response = await apiCall(`/api/management/command/${entryId}/step/`, {
        method: 'PATCH',
        body: JSON.stringify({ step, value, meta }),
      });
      if (response.error) {
          throw new Error(response.error);
      }
      return { entryId, step, value };
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

const commandSlice = createSlice({
  name: 'command',
  initialState: {
    items: [],
    total: 0,
    workflowSteps: [],
    status: 'idle',
    error: null,
    stepUpdateStatus: {}, // { [entryId-step]: 'pending' | 'success' | 'error' }
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      // Fetch
      .addCase(fetchCommandWorkflows.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchCommandWorkflows.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.items = action.payload.items;
        state.total = action.payload.total;
        state.workflowSteps = action.payload.workflow_steps;
      })
      .addCase(fetchCommandWorkflows.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.payload;
      })
      // Create
      .addCase(createCommandWorkflow.fulfilled, (state) => {
        // Trigger a re-fetch or manual update? For now, we'll let component handle re-fetch
      })
      // Update Step
      .addCase(updateCommandStep.pending, (state, action) => {
        const { entryId, step } = action.meta.arg;
        state.stepUpdateStatus[`${entryId}-${step}`] = 'pending';
      })
      .addCase(updateCommandStep.fulfilled, (state, action) => {
        const { entryId, step, value } = action.payload;
        state.stepUpdateStatus[`${entryId}-${step}`] = 'success';

        const entry = state.items.find((e) => e.id === entryId);
        if (entry) {
          entry.checklist[step] = value;
        }
      })
      .addCase(updateCommandStep.rejected, (state, action) => {
        const { entryId, step } = action.meta.arg;
        state.stepUpdateStatus[`${entryId}-${step}`] = 'error';
      });
  },
});

export default commandSlice.reducer;
