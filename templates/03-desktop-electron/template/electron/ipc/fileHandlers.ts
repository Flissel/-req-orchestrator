/**
 * File system IPC handlers for {{PROJECT_NAME}}
 */

import { IpcMainInvokeEvent } from 'electron';
import * as fs from 'fs/promises';
import * as path from 'path';

// Allowed paths for security
const ALLOWED_PATHS = [process.cwd()];

function isAllowedPath(filePath: string): boolean {
  const resolved = path.resolve(filePath);
  return ALLOWED_PATHS.some(allowed => resolved.startsWith(allowed));
}

export const fileHandlers = {
  'file:read': async (_event: IpcMainInvokeEvent, filePath: string): Promise<string> => {
    if (!isAllowedPath(filePath)) {
      throw new Error('Access denied: path not allowed');
    }
    return fs.readFile(filePath, 'utf-8');
  },

  'file:write': async (_event: IpcMainInvokeEvent, filePath: string, data: string): Promise<void> => {
    if (!isAllowedPath(filePath)) {
      throw new Error('Access denied: path not allowed');
    }
    await fs.writeFile(filePath, data, 'utf-8');
  },

  'file:readDir': async (_event: IpcMainInvokeEvent, dirPath: string): Promise<string[]> => {
    if (!isAllowedPath(dirPath)) {
      throw new Error('Access denied: path not allowed');
    }
    return fs.readdir(dirPath);
  },

  'file:exists': async (_event: IpcMainInvokeEvent, filePath: string): Promise<boolean> => {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  },
};