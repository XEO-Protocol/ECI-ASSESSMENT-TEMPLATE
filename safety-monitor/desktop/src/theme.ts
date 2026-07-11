// Theme handling: dark is the app's home theme (a night watch), light is a
// first-class alternative. Default follows the OS; an explicit user choice
// is persisted and stamped on <html data-theme="...">.

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'safety-monitor-theme';

export function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches
    ? 'light'
    : 'dark';
}

export function currentTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : systemTheme();
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function setTheme(theme: Theme): void {
  localStorage.setItem(STORAGE_KEY, theme);
  applyTheme(theme);
}

export function initTheme(): void {
  applyTheme(currentTheme());
  window
    .matchMedia?.('(prefers-color-scheme: light)')
    .addEventListener?.('change', () => {
      if (!localStorage.getItem(STORAGE_KEY)) applyTheme(systemTheme());
    });
}
