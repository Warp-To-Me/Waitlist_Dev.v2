import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiCall } from '../../utils/api';

export const fetchCommandWorkflows = createAsyncThunk(
  'command/fetchCommandWorkflows',
  async ({ limit = 20, offset = 0 } = {}, { rejectWithValue }) => {
    try {
      const response = await apiCall(`/api/management/command/?limit=${limit}&offset=${offset}`);
      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

export const deleteCommandWorkflow = createAsyncThunk(
  'command/deleteCommandWorkflow',
  async (entryId, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const response = await apiCall(`/api/management/command/${entryId}/`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf
        }
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
          throw new Error(data.error || "Delete failed");
      }
      return entryId;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

export const createCommandWorkflow = createAsyncThunk(
  'command/createCommandWorkflow',
  async (payload, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const response = await apiCall('/api/management/command/', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf 
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
          throw new Error(data.error || "Request failed");
      }
      return data;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

export const updateCommandStep = createAsyncThunk(
  'command/updateCommandStep',
  async ({ entryId, step, value, meta }, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const response = await apiCall(`/api/management/command/${entryId}/step/`, {
        method: 'PATCH',
        headers: { 
            'Content-Type': 'application/json', 
            'X-CSRFToken': csrf
        },
        body: JSON.stringify({ step, value, meta }),
      });
      
      const data = await response.json();
      
      if (!response.ok || data.error) {
          throw new Error(data.error || "Update failed");
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
        state.items = action.payload.items || [];
        state.total = action.payload.total || 0;
        state.workflowSteps = action.payload.workflow_steps || [];
        state.error = null;
      })
      .addCase(fetchCommandWorkflows.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.payload;
        // Keep existing data on error? Or clear? 
        // Safer to keep existing structure but maybe empty items if critical failure
        // But for now, let's just ensure we don't break types
        if (!state.items) state.items = [];
        if (!state.workflowSteps) state.workflowSteps = [];
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
      })
      // Delete
      .addCase(deleteCommandWorkflow.fulfilled, (state, action) => {
        state.items = state.items.filter(item => item.id !== action.payload);
        state.total -= 1;
      });
  },
});

export default commandSlice.reducer;
