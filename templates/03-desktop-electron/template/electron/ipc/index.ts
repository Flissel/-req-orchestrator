/**
 * IPC Handler Registration for {{PROJECT_NAME}}
 */

import { ipcMain } from 'electron';
import { fileHandlers } from './fileHandlers';
import { dbHandlers } from './dbHandlers';

export function registerIpcHandlers(): void {
  // Register file handlers
  Object.entries(fileHandlers).forEach(([channel, handler]) => {
    ipcMain.handle(channel, handler);
  });

  // Register database handlers
  Object.entries(dbHandlers).forEach(([channel, handler]) => {
    ipcMain.handle(channel, handler);
  });

  console.log('✅ IPC handlers registered');
}