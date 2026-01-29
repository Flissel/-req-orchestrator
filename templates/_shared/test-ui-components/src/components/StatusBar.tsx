import React from 'react';
import { Circle, Play, Square, AlertCircle, Loader2 } from 'lucide-react';
import { cn } from '../utils/cn';
import type { StatusType } from '../types';

interface StatusBarProps {
  title: string;
  status: StatusType;
  onStart?: () => void;
  onStop?: () => void;
  onRestart?: () => void;
  children?: React.ReactNode;
}

const statusConfig: Record<StatusType, { icon: React.ElementType; color: string; label: string }> = {
  running: { icon: Circle, color: 'text-green-500', label: 'Running' },
  stopped: { icon: Square, color: 'text-gray-500', label: 'Stopped' },
  error: { icon: AlertCircle, color: 'text-red-500', label: 'Error' },
  loading: { icon: Loader2, color: 'text-blue-500', label: 'Loading' },
};

export function StatusBar({ title, status, onStart, onStop, onRestart, children }: StatusBarProps) {
  const { icon: Icon, color, label } = statusConfig[status];

  return (
    <div className="flex items-center justify-between px-4 py-3 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h1>
        <div className="flex items-center gap-2">
          <Icon className={cn('h-4 w-4', color, status === 'loading' && 'animate-spin')} />
          <span className={cn('text-sm font-medium', color)}>{label}</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {children}

        {status === 'stopped' && onStart && (
          <button
            onClick={onStart}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md transition-colors"
          >
            <Play className="h-4 w-4" />
            Start
          </button>
        )}

        {status === 'running' && onStop && (
          <button
            onClick={onStop}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md transition-colors"
          >
            <Square className="h-4 w-4" />
            Stop
          </button>
        )}

        {onRestart && status !== 'loading' && (
          <button
            onClick={onRestart}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-200 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-md transition-colors"
          >
            Restart
          </button>
        )}
      </div>
    </div>
  );
}
