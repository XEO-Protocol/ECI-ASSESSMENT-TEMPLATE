import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  notify: (title: string, body: string): Promise<void> =>
    ipcRenderer.invoke('notify', title, body),
  backendUrl: (): Promise<string> => ipcRenderer.invoke('backend-url'),
});
