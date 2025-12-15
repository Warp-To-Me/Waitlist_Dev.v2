import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import authReducer from './slices/authSlice';
import fleetReducer from './slices/fleetSlice';
import socketMiddleware from './middleware/socketMiddleware';

export const store = configureStore({
  reducer: {
    ui: uiReducer,
    auth: authReducer,
    fleet: fleetReducer,
  },
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(socketMiddleware()),
});
