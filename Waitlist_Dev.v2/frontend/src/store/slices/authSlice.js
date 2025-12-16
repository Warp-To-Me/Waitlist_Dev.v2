import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

export const fetchUserMe = createAsyncThunk(
  'auth/fetchUserMe',
  async (_, { rejectWithValue }) => {
    try {
      const res = await fetch('/api/me/');
      if (res.ok) {
        const data = await res.json();
        return data;
      } else {
        // If 403/401, we just return null user, not necessarily an error that crashes app
        return null;
      }
    } catch (error) {
      console.error("Failed to fetch user:", error);
      return rejectWithValue(error.message);
    }
  }
);

const initialState = {
  user: null,
  status: 'idle', // 'idle' | 'loading' | 'succeeded' | 'failed'
  error: null,
};

export const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearUser: (state) => {
        state.user = null;
        state.status = 'idle';
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchUserMe.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchUserMe.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.user = action.payload;
        
        // Handle ban check logic here if appropriate, or keep in component
        if (action.payload && action.payload.is_banned) {
             // Side effects usually belong in middleware or components, 
             // but strictly state updates happen here.
        }
      })
      .addCase(fetchUserMe.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.payload;
        state.user = null;
      });
  },
});

export const { clearUser } = authSlice.actions;

export const selectUser = (state) => state.auth.user;
export const selectAuthStatus = (state) => state.auth.status;
export const selectAuthLoading = (state) => state.auth.status === 'loading' || state.auth.status === 'idle';

export default authSlice.reducer;
