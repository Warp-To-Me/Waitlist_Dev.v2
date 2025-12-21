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
    resetProfileStatus: (state) => {
        state.status = 'idle';
    },
    optimisticToggleAggregate: (state, action) => {
        const { character_id, setting, value } = action.payload;
        if (state.data && state.data.characters) {
            const char = state.data.characters.find(c => c.character_id === character_id);
            if (char) {
                // Update specific aggregate flag
                if (setting === 'wallet') char.include_wallet = value;
                if (setting === 'lp') char.include_lp = value;
                if (setting === 'sp') char.include_sp = value;
            }
            // Also update active_char if it matches
            if (state.data.active_char && state.data.active_char.character_id === character_id) {
                if (setting === 'wallet') state.data.active_char.include_wallet = value;
                if (setting === 'lp') state.data.active_char.include_lp = value;
                if (setting === 'sp') state.data.active_char.include_sp = value;
            }
        }
    },
    optimisticBulkToggleAggregate: (state, action) => {
        const { setting, value } = action.payload;
        if (state.data && state.data.characters) {
            state.data.characters.forEach(char => {
                if (setting === 'wallet') char.include_wallet = value;
                if (setting === 'lp') char.include_lp = value;
                if (setting === 'sp') char.include_sp = value;
            });
            // Update active char too
            if (state.data.active_char) {
                if (setting === 'wallet') state.data.active_char.include_wallet = value;
                if (setting === 'lp') state.data.active_char.include_lp = value;
                if (setting === 'sp') state.data.active_char.include_sp = value;
            }
        }
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

export const { resetProfileStatus, optimisticToggleAggregate, optimisticBulkToggleAggregate } = profileSlice.actions;

export const selectProfileData = (state) => state.profile.data;
export const selectProfileStatus = (state) => state.profile.status;
export const selectProfileError = (state) => state.profile.error;

export default profileSlice.reducer;
