import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  theme: 'default',
  sidebarOpen: false, // For mobile sidebar toggle if needed
};

export const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setTheme: (state, action) => {
      state.theme = action.payload;
    },
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    closeSidebar: (state) => {
      state.sidebarOpen = false;
    }
  },
});

export const { setTheme, toggleSidebar, closeSidebar } = uiSlice.actions;

export const selectTheme = (state) => state.ui.theme;
export const selectSidebarOpen = (state) => state.ui.sidebarOpen;

export default uiSlice.reducer;
