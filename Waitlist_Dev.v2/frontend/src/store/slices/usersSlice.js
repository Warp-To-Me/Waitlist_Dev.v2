import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiCall } from '../../utils/api';

export const fetchUsers = createAsyncThunk(
  'users/fetchList',
  async ({ query = '', page = 1, sort = 'character', dir = 'asc' }, { rejectWithValue }) => {
    try {
      const res = await apiCall(`/api/management/users/?q=${query}&page=${page}&sort=${sort}&dir=${dir}`);
      const data = await res.json();
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchUserProfile = createAsyncThunk(
  'users/fetchProfile',
  async (userId, { rejectWithValue }) => {
    try {
      const res = await apiCall(`/api/management/users/${userId}/inspect/`);
      if (!res.ok) throw new Error('Failed to fetch profile');
      return await res.json();
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchUserRoles = createAsyncThunk(
    'users/fetchRoles',
    async (userId, { rejectWithValue }) => {
        try {
            const res = await apiCall(`/api/mgmt/user_roles/${userId}/`);
            if (!res.ok) throw new Error('Failed to fetch roles');
            return await res.json();
        } catch (err) {
            return rejectWithValue(err.message);
        }
    }
);

const initialState = {
  list: [],
  pagination: {
      current: 1,
      total: 1,
      has_next: false,
      has_previous: false
  },
  query: '',
  sort: 'character',
  sortDir: 'asc',
  loading: false,
  error: null,
  
  // Inspect Data
  inspectProfile: null,
  inspectLoading: false,
  
  // Roles Data
  userRoles: { current_roles: [], available_roles: [] },
  rolesLoading: false,
};

export const usersSlice = createSlice({
  name: 'users',
  initialState,
  reducers: {
    setQuery: (state, action) => {
        state.query = action.payload;
        state.pagination.current = 1; // Reset page on new search
    },
    setPage: (state, action) => {
        state.pagination.current = action.payload;
    },
    setSort: (state, action) => {
        if (state.sort === action.payload) {
            state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
        } else {
            state.sort = action.payload;
            state.sortDir = 'asc';
        }
    },
    clearInspect: (state) => {
        state.inspectProfile = null;
        state.userRoles = { current_roles: [], available_roles: [] };
    }
  },
  extraReducers: (builder) => {
    builder
      // List
      .addCase(fetchUsers.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchUsers.fulfilled, (state, action) => {
        state.loading = false;
        state.list = action.payload.users || [];
        state.pagination = action.payload.pagination;
      })
      .addCase(fetchUsers.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      // Profile
      .addCase(fetchUserProfile.pending, (state) => {
          state.inspectLoading = true;
      })
      .addCase(fetchUserProfile.fulfilled, (state, action) => {
          state.inspectLoading = false;
          state.inspectProfile = action.payload;
      })
      .addCase(fetchUserProfile.rejected, (state) => {
          state.inspectLoading = false;
      })
      // Roles
      .addCase(fetchUserRoles.pending, (state) => {
          state.rolesLoading = true;
      })
      .addCase(fetchUserRoles.fulfilled, (state, action) => {
          state.rolesLoading = false;
          state.userRoles = action.payload;
      });
  }
});

export const { setQuery, setPage, setSort, clearInspect } = usersSlice.actions;

export const selectUsersList = (state) => state.users.list;
export const selectUsersPagination = (state) => state.users.pagination;
export const selectUsersQuery = (state) => state.users.query;
export const selectUsersSort = (state) => ({ field: state.users.sort, dir: state.users.sortDir });
export const selectUsersLoading = (state) => state.users.loading;
export const selectInspectProfile = (state) => state.users.inspectProfile;
export const selectInspectLoading = (state) => state.users.inspectLoading;
export const selectUserRoles = (state) => state.users.userRoles;
export const selectUserRolesLoading = (state) => state.users.rolesLoading;

export default usersSlice.reducer;
