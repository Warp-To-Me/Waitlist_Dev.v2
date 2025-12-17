import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  buckets: {},
  status: 'disconnected',
};

export const notificationSlice = createSlice({
  name: 'notification',
  initialState,
  reducers: {
    handleWsMessage: (state, action) => {
      const msg = action.payload;
      if (msg.type === 'ratelimit') {
        state.buckets[msg.bucket] = msg;
      }
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase('WS_CONNECTED', (state, action) => {
        if (action.payload.channelKey === 'user') {
          state.status = 'connected';
        }
      })
      .addCase('WS_DISCONNECTED', (state, action) => {
        if (action.payload.channelKey === 'user') {
          state.status = 'disconnected';
        }
      })
      .addCase('WS_MESSAGE_RECEIVED', (state, action) => {
        if (action.payload.channelKey === 'user') {
          notificationSlice.caseReducers.handleWsMessage(state, { payload: action.payload.msg });
        }
      });
  }
});

export const selectRateLimitBuckets = (state) => state.notification.buckets;
export const selectNotificationStatus = (state) => state.notification.status;

export default notificationSlice.reducer;
