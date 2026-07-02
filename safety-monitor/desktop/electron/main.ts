import { spawn, ChildProcess } from 'child_process';
import { app, BrowserWindow, ipcMain, Notification } from 'electron';
import * as path from 'path';

const BACKEND_URL = process.env.SAFETY_MONITOR_BACKEND_URL ?? 'http://127.0.0.1:8765';

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: '#101014',
    title: 'Safety Monitor',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    void mainWindow.loadURL(devServerUrl);
  } else {
    void mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

async function backendIsUp(): Promise<boolean> {
  try {
    const resp = await fetch(`${BACKEND_URL}/api/health`, {
      signal: AbortSignal.timeout(1500),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

/**
 * Convenience: start the Python backend automatically if it isn't already
 * running. In development you can also just run `python run.py` yourself.
 */
async function ensureBackend(): Promise<void> {
  if (await backendIsUp()) return;
  if (process.env.SAFETY_MONITOR_NO_AUTOSTART) return;

  const backendDir = path.resolve(__dirname, '..', '..', 'backend');
  const python = process.env.SAFETY_MONITOR_PYTHON ?? 'python3';
  try {
    backendProcess = spawn(python, ['run.py'], {
      cwd: backendDir,
      stdio: 'inherit',
    });
    backendProcess.on('exit', () => {
      backendProcess = null;
    });
  } catch (err) {
    console.error('Failed to start backend automatically:', err);
  }
}

ipcMain.handle('notify', (_event, title: string, body: string) => {
  if (Notification.isSupported()) {
    new Notification({ title, body }).show();
  }
});

ipcMain.handle('backend-url', () => BACKEND_URL);

app.whenReady().then(async () => {
  await ensureBackend();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('quit', () => {
  backendProcess?.kill();
});
