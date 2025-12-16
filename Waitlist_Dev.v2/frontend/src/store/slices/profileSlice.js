import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

export const fetchProfileData = createAsyncThunk(
  'profile/fetchData',
  async (args, { rejectWithValue }) => {
    try {
      let url = '/api/profile/';
      // Support object with userId/charId or empty/undefined
      const userId = args?.userId;
      const charId = args?.charId;
      
      if (userId) {
          url = `/api/management/users/${userId}/inspect/`;
          if (charId) {
              url += `${charId}/`;
          }
      }
      
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error('Failed to fetch profile data');
      }
      return await res.json();
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

const initialState = {
  data: null,
  status: 'idle', // 'idle' | 'loading' | 'succeeded' | 'failed'
  error: null,
};

export const profileSlice = createSlice({
  name: 'profile',
  initialState,
  reducers: {
    // We might add actions like 'addAlt' or 'removeAlt' here later if we want optimistic updates
    // For now, simple fetching is enough
    resetProfileStatus: (state) => {
        state.status = 'idle';
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchProfileData.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchProfileData.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.data = action.payload;
      })
      .addCase(fetchProfileData.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.payload;
      });
  }
});

export const { resetProfileStatus } = profileSlice.actions;

export const selectProfileData = (state) => state.profile.data;
export const selectProfileStatus = (state) => state.profile.status;
export const selectProfileError = (state) => state.profile.error;

export default profileSlice.reducer;
