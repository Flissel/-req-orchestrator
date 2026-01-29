import React, { useRef, useEffect } from 'react';
import { Terminal, Trash2, Download, Filter } from 'lucide-react';
import { cn } from '../utils/cn';
import type { LogEntry } from '../types';

interface LogPanelProps {
  logs: LogEntry[];
  onClear?: () => void;
  onExport?: () => void;
  maxHeight?: string;
  autoScroll?: boolean;
  filter?: 'all' | 'info' | 'warn' | 'error' | 'debug';
  onFilterChange?: (filter: 'all' | 'info' | 'warn' | 'error' | 'debug') => void;
}

const levelColors: Record<LogEntry['level'], string> = {
  info: 'text-blue-400',
  warn: 'text-yellow-400',
  error: 'text-red-400',
  debug: 'text-gray-400',
};

const levelBadges: Record<LogEntry['level'], string> = {
  info: 'bg-blue-500/20 text-blue-400',
  warn: 'bg-yellow-500/20 text-yellow-400',
  error: 'bg-red-500/20 text-red-400',
  debug: 'bg-gray-500/20 text-gray-400',
};

export function LogPanel({
  logs,
  onClear,
  onExport,
  maxHeight = '400px',
  autoScroll = true,
  filter = 'all',
  onFilterChange,
}: LogPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const filteredLogs = filter === 'all' ? logs : logs.filter((log) => log.level === filter);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3,
    });
  };

  return (
    <div className="flex flex-col bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-200">Console</span>
          <span className="text-xs text-gray-500">({filteredLogs.length} entries)</span>
        </div>

        <div className="flex items-center gap-2">
          {onFilterChange && (
            <select
              value={filter}
              onChange={(e) => onFilterChange(e.target.value as any)}
              className="text-xs bg-gray-700 text-gray-200 border border-gray-600 rounded px-2 py-1"
            >
              <option value="all">All</option>
              <option value="info">Info</option>
              <option value="warn">Warn</option>
              <option value="error">Error</option>
              <option value="debug">Debug</option>
            </select>
          )}

          {onExport && (
            <button
              onClick={onExport}
              className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-700 rounded transition-colors"
              title="Export logs"
            >
              <Download className="h-4 w-4" />
            </button>
          )}

          {onClear && (
            <button
              onClick={onClear}
              className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-700 rounded transition-colors"
              title="Clear logs"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Log entries */}
      <div
        ref={containerRef}
        className="overflow-auto font-mono text-sm"
        style={{ maxHeight }}
      >
        {filteredLogs.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500">
            No log entries yet
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {filteredLogs.map((log) => (
              <div
                key={log.id}
                className="flex items-start gap-3 px-4 py-2 hover:bg-gray-800/50"
              >
                <span className="text-xs text-gray-500 whitespace-nowrap">
                  {formatTime(log.timestamp)}
                </span>
                <span className={cn('text-xs px-1.5 py-0.5 rounded uppercase font-medium', levelBadges[log.level])}>
                  {log.level}
                </span>
                {log.source && (
                  <span className="text-xs text-gray-500">[{log.source}]</span>
                )}
                <span className={cn('flex-1', levelColors[log.level])}>
                  {log.message}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
