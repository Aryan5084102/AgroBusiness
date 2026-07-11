import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { defaultLocale, type Locale } from '@/lib/i18n';

// Global UI settings: locale and sidebar state. Server data is NOT stored in
// Redux (that is TanStack Query's responsibility).
interface UiState {
  locale: Locale;
  sidebarCollapsed: boolean;
}

const initialState: UiState = {
  locale: defaultLocale,
  sidebarCollapsed: false,
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setLocale(state, action: PayloadAction<Locale>) {
      state.locale = action.payload;
    },
    toggleSidebar(state) {
      state.sidebarCollapsed = !state.sidebarCollapsed;
    },
  },
});

export const { setLocale, toggleSidebar } = uiSlice.actions;
export default uiSlice.reducer;
