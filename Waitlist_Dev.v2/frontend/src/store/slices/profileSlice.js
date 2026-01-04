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
    },
    optimisticToggleAggregate: (state, action) => {
      // payload: { character_id, type }
      const { character_id, type } = action.payload;
      if (!state.data || !state.data.characters) return;

      const char = state.data.characters.find(c => c.character_id === character_id);
      if (char) {
        const fieldMap = {
          wallet: 'include_wallet_in_aggregate',
          lp: 'include_lp_in_aggregate',
          sp: 'include_sp_in_aggregate'
        };
        const field = fieldMap[type];
        if (field) {
          char[field] = !char[field];
        }
      }
    },
    optimisticBulkToggleAggregate: (state, action) => {
        const { type, enabled } = action.payload;
        if (!state.data || !state.data.characters) return;

        const fieldMap = {
          wallet: 'include_wallet_in_aggregate',
          lp: 'include_lp_in_aggregate',
          sp: 'include_sp_in_aggregate'
        };
        const field = fieldMap[type];
        if (field) {
            state.data.characters.forEach(c => {
                c[field] = enabled;
            });
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

export const { resetProfileStatus } = profileSlice.actions;

export const selectProfileData = (state) => state.profile.data;
export const selectProfileStatus = (state) => state.profile.status;
export const selectProfileError = (state) => state.profile.error;

export default profileSlice.reducer;
