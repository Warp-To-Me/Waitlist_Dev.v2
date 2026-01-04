import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiCall } from '../../utils/api';

// --- Thunks ---

export const fetchSRPDivisions = createAsyncThunk(
  'srp/fetchDivisions',
  async (_, { rejectWithValue }) => {
    try {
      const res = await apiCall('/api/mgmt/srp/divisions/');
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchSRPStatus = createAsyncThunk(
  'srp/fetchStatus',
  async (_, { rejectWithValue }) => {
    try {
      const res = await apiCall('/api/srp/status/');
      return await res.json();
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchSRPData = createAsyncThunk(
  'srp/fetchData',
  async (_, { getState, rejectWithValue }) => {
    const state = getState().srp;
    const { dateRange, pagination, filters, activeDivisions } = state;

    const params = new URLSearchParams({
      start_date: dateRange.start,
      end_date: dateRange.end,
      page: pagination.page,
      limit: pagination.limit,
      ...filters
    });
    
    activeDivisions.forEach(d => params.append('divisions[]', d));

    try {
      const res = await apiCall(`/api/srp/data/?${params.toString()}`);
      return await res.json();
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const updateSRPCategory = createAsyncThunk(
  'srp/updateCategory',
  async ({ entryId, category }, { dispatch, rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall('/api/mgmt/srp/update_category/', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf
        },
        body: JSON.stringify({ entry_id: entryId, category })
      });
      const data = await res.json();
      if (!data.success) throw new Error("Failed to update");
      
      // Refresh data to reflect changes (re-calculation of charts etc)
      dispatch(fetchSRPData());
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const generateSRPList = createAsyncThunk(
  'srp/generateList',
  async ({ start_date, end_date, amount, ref_type }, { rejectWithValue }) => {
    try {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
      const res = await apiCall('/api/mgmt/srp/generate_list/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf
        },
        body: JSON.stringify({ start_date, end_date, amount, ref_type })
      });
      const data = await res.json();
      return data.names || [];
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

// --- Slice ---

const now = new Date();
const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

const initialState = {
  summary: null,      // The main data object (transactions, charts, etc.)
  status: null,       // { last_sync, next_sync }
  divisionMap: {},    // { 1: "Wallet", ... }
  
  // Filters State
  dateRange: { start, end },
  activeDivisions: ['1','2','3','4','5','6','7'],
  filters: {
    f_div: '',
    f_amount: '',
    f_from: '',
    f_to: '',
    f_type: '',
    f_category: '',
    f_reason: ''
  },
  
  // Pagination
  pagination: {
    page: 1,
    limit: 25,
    total_pages: 1,
    total_count: 0
  },

  loading: false,
  error: null
};

export const srpSlice = createSlice({
  name: 'srp',
  initialState,
  reducers: {
    setFilter: (state, action) => {
      const { key, value } = action.payload;
      state.filters[key] = value;
      state.pagination.page = 1; // Reset page on filter change
    },
    setFilters: (state, action) => {
      state.filters = { ...state.filters, ...action.payload };
      state.pagination.page = 1;
    },
    setDateRange: (state, action) => {
      state.dateRange = { ...state.dateRange, ...action.payload };
    },
    toggleDivision: (state, action) => {
      const div = action.payload;
      if (state.activeDivisions.includes(div)) {
        state.activeDivisions = state.activeDivisions.filter(d => d !== div);
      } else {
        state.activeDivisions.push(div);
      }
    },
    setPage: (state, action) => {
      state.pagination.page = action.payload;
    },
    setLimit: (state, action) => {
      state.pagination.limit = action.payload;
      state.pagination.page = 1;
    }
  },
  extraReducers: (builder) => {
    builder
      // Divisions
      .addCase(fetchSRPDivisions.fulfilled, (state, action) => {
        state.divisionMap = action.payload;
      })
      // Status
      .addCase(fetchSRPStatus.fulfilled, (state, action) => {
        state.status = action.payload;
      })
      // Data
      .addCase(fetchSRPData.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchSRPData.fulfilled, (state, action) => {
        state.loading = false;
        state.summary = action.payload;
        // Update pagination from response if available
        if (action.payload.pagination) {
             state.pagination.total_pages = action.payload.pagination.total_pages;
             state.pagination.total_count = action.payload.pagination.total_count;
        }
      })
      .addCase(fetchSRPData.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      });
  }
});

export const { setFilter, setFilters, setDateRange, toggleDivision, setPage, setLimit } = srpSlice.actions;

export const selectSRPSummary = (state) => state.srp.summary;
export const selectSRPStatus = (state) => state.srp.status;
export const selectSRPDivisions = (state) => state.srp.divisionMap;
export const selectSRPActiveDivisions = (state) => state.srp.activeDivisions;
export const selectSRPFilters = (state) => state.srp.filters;
export const selectSRPDateRange = (state) => state.srp.dateRange;
export const selectSRPPagination = (state) => state.srp.pagination;
export const selectSRPLoading = (state) => state.srp.loading;

export default srpSlice.reducer;
