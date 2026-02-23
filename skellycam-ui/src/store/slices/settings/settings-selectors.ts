import { RootState } from "../../types";

export const selectLocale = (state: RootState) => state.settings.locale;
export const selectShowTranslationIndicator = (state: RootState) =>
  state.settings.showTranslationIndicator;
