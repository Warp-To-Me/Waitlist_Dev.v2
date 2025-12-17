import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import authReducer from './slices/authSlice';
import fleetReducer from './slices/fleetSlice';
import systemReducer from './slices/systemSlice';
import srpReducer from './slices/srpSlice';
import profileReducer from './slices/profileSlice';
import usersReducer from './slices/usersSlice';
import notificationReducer from './slices/notificationSlice';
import socketMiddleware from './middleware/socketMiddleware';

export const store = configureStore({
  reducer: {
    ui: uiReducer,
    auth: authReducer,
    fleet: fleetReducer,
    system: systemReducer,
    srp: srpReducer,
    profile: profileReducer,
    users: usersReducer,
    notification: notificationReducer,
  },
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(socketMiddleware()),
});
