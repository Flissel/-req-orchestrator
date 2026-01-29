/**
 * Database IPC handlers for {{PROJECT_NAME}}
 */

import { IpcMainInvokeEvent } from 'electron';
import { database } from '../services/database';

export const dbHandlers = {
  'db:getAll': async (_event: IpcMainInvokeEvent, table: string): Promise<unknown[]> => {
    return database.getAll(table);
  },

  'db:getById': async (_event: IpcMainInvokeEvent, table: string, id: number): Promise<unknown> => {
    return database.getById(table, id);
  },

  'db:insert': async (_event: IpcMainInvokeEvent, table: string, data: Record<string, unknown>): Promise<number> => {
    return database.insert(table, data);
  },

  'db:update': async (_event: IpcMainInvokeEvent, table: string, id: number, data: Record<string, unknown>): Promise<void> => {
    return database.update(table, id, data);
  },

  'db:delete': async (_event: IpcMainInvokeEvent, table: string, id: number): Promise<void> => {
    return database.delete(table, id);
  },
};