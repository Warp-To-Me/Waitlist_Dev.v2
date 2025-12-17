import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  buckets: {},
  status: 'disconnected'
};

export const notificationSlice = createSlice({
  name: 'notification',
  initialState,
  reducers: {
    handleWsMessage: (state, action) => {
        const { key, data } = action.payload;
        if (key !== 'user_notify') return;

        if (data.type === 'ratelimit') {
            state.buckets[data.bucket] = data;
        }
    }
  },
  extraReducers: (builder) => {
      builder
        .addCase('WS_CONNECTED', (state, action) => {
            if (action.payload.key === 'user_notify') state.status = 'connected';
        })
        .addCase('WS_DISCONNECTED', (state, action) => {
             if (action.payload.key === 'user_notify') state.status = 'disconnected';
        })
        .addCase('WS_MESSAGE_RECEIVED', (state, action) => {
            notificationSlice.caseReducers.handleWsMessage(state, action);
        });
  }
});

export const selectNotificationBuckets = (state) => state.notification.buckets;

export default notificationSlice.reducer;
