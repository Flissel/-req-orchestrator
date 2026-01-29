export type StatusType = 'running' | 'stopped' | 'error' | 'loading';

export interface LogEntry {
  id: string;
  timestamp: Date;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  source?: string;
}

export interface ConfigItem {
  key: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'select';
  value: string | number | boolean;
  options?: { label: string; value: string }[];
  description?: string;
}
