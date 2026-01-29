/**
 * SQLite Database Service for {{PROJECT_NAME}}
 */

import Database from 'better-sqlite3';
import { app } from 'electron';
import * as path from 'path';

class DatabaseService {
  private db: Database.Database | null = null;
  private dbPath: string;

  constructor() {
    this.dbPath = path.join(app.getPath('userData'), '{{PROJECT_NAME_SNAKE}}.sqlite');
  }

  async init(): Promise<void> {
    this.db = new Database(this.dbPath);
    this.db.pragma('journal_mode = WAL');
    this.migrate();
  }

  private migrate(): void {
    // Create default tables
    this.db?.exec(`
      CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        data TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
    `);
  }

  getAll(table: string): unknown[] {
    const stmt = this.db?.prepare(`SELECT * FROM ${table}`);
    return stmt?.all() || [];
  }

  getById(table: string, id: number): unknown {
    const stmt = this.db?.prepare(`SELECT * FROM ${table} WHERE id = ?`);
    return stmt?.get(id);
  }

  insert(table: string, data: Record<string, unknown>): number {
    const keys = Object.keys(data);
    const values = Object.values(data);
    const placeholders = keys.map(() => '?').join(', ');
    
    const stmt = this.db?.prepare(
      `INSERT INTO ${table} (${keys.join(', ')}) VALUES (${placeholders})`
    );
    const result = stmt?.run(...values);
    return result?.lastInsertRowid as number;
  }

  update(table: string, id: number, data: Record<string, unknown>): void {
    const keys = Object.keys(data);
    const values = Object.values(data);
    const setClause = keys.map(k => `${k} = ?`).join(', ');
    
    const stmt = this.db?.prepare(
      `UPDATE ${table} SET ${setClause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?`
    );
    stmt?.run(...values, id);
  }

  delete(table: string, id: number): void {
    const stmt = this.db?.prepare(`DELETE FROM ${table} WHERE id = ?`);
    stmt?.run(id);
  }

  close(): void {
    this.db?.close();
  }
}

export const database = new DatabaseService();

export async function initDatabase(): Promise<void> {
  await database.init();
}