import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { defaultLocale, type Locale } from '@/lib/i18n';

// Global UI settings: locale and navigation state. Server data is NOT stored in
// Redux (that is TanStack Query's responsibility).
interface UiState {
  locale: Locale;
  /** Desktop: the sidebar shrinks to an icon rail. */
  sidebarCollapsed: boolean;
  /** Phone/tablet: the sidebar is an overlay drawer. */
  mobileNavOpen: boolean;
}

const initialState: UiState = {
  locale: defaultLocale,
  sidebarCollapsed: false,
  mobileNavOpen: false,
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
    setMobileNavOpen(state, action: PayloadAction<boolean>) {
      state.mobileNavOpen = action.payload;
    },
  },
});

export const { setLocale, toggleSidebar, setMobileNavOpen } = uiSlice.actions;
export default uiSlice.reducer;
