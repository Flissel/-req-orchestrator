import React from 'react';
import { Settings, Info } from 'lucide-react';
import { cn } from '../utils/cn';
import type { ConfigItem } from '../types';

interface ConfigPanelProps {
  title?: string;
  items: ConfigItem[];
  onChange: (key: string, value: string | number | boolean) => void;
  className?: string;
}

export function ConfigPanel({ title = 'Configuration', items, onChange, className }: ConfigPanelProps) {
  const renderInput = (item: ConfigItem) => {
    const baseInputClass = "w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500";

    switch (item.type) {
      case 'boolean':
        return (
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={item.value as boolean}
              onChange={(e) => onChange(item.key, e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
          </label>
        );

      case 'select':
        return (
          <select
            value={item.value as string}
            onChange={(e) => onChange(item.key, e.target.value)}
            className={baseInputClass}
          >
            {item.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        );

      case 'number':
        return (
          <input
            type="number"
            value={item.value as number}
            onChange={(e) => onChange(item.key, parseFloat(e.target.value) || 0)}
            className={baseInputClass}
          />
        );

      default:
        return (
          <input
            type="text"
            value={item.value as string}
            onChange={(e) => onChange(item.key, e.target.value)}
            className={baseInputClass}
          />
        );
    }
  };

  return (
    <div className={cn("bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700", className)}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <Settings className="h-4 w-4 text-gray-500" />
        <h3 className="text-sm font-medium text-gray-900 dark:text-white">{title}</h3>
      </div>

      <div className="p-4 space-y-4">
        {items.map((item) => (
          <div key={item.key} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {item.label}
              </label>
              {item.type === 'boolean' && renderInput(item)}
            </div>

            {item.type !== 'boolean' && renderInput(item)}

            {item.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400 flex items-start gap-1">
                <Info className="h-3 w-3 mt-0.5 flex-shrink-0" />
                {item.description}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
