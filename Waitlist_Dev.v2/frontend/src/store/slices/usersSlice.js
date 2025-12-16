import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

export const fetchUsers = createAsyncThunk(
  'users/fetchList',
  async ({ query = '', page = 1 }, { rejectWithValue }) => {
    try {
      const res = await fetch(`/api/management/users/?q=${query}&page=${page}`);
      const data = await res.json();
      return data;
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
  loading: false,
  error: null,
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
    }
  },
  extraReducers: (builder) => {
    builder
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
      });
  }
});

export const { setQuery, setPage } = usersSlice.actions;

export const selectUsersList = (state) => state.users.list;
export const selectUsersPagination = (state) => state.users.pagination;
export const selectUsersQuery = (state) => state.users.query;
export const selectUsersLoading = (state) => state.users.loading;

export default usersSlice.reducer;
