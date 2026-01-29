import React, { Fragment } from 'react';
import { X, HelpCircle, ExternalLink, Book, Code, Terminal } from 'lucide-react';
import { cn } from '../utils/cn';

interface HelpSection {
  title: string;
  icon?: React.ElementType;
  content: string | React.ReactNode;
}

interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  sections: HelpSection[];
  docsUrl?: string;
  sourceUrl?: string;
}

export function HelpModal({
  isOpen,
  onClose,
  title,
  description,
  sections,
  docsUrl,
  sourceUrl,
}: HelpModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-2xl bg-white dark:bg-gray-900 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <HelpCircle className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {title}
                </h2>
                {description && (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {description}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4 space-y-6 max-h-[60vh] overflow-y-auto">
            {sections.map((section, index) => {
              const Icon = section.icon || Book;
              return (
                <div key={index} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-gray-500" />
                    <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                      {section.title}
                    </h3>
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 pl-6">
                    {typeof section.content === 'string' ? (
                      <p>{section.content}</p>
                    ) : (
                      section.content
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer with links */}
          {(docsUrl || sourceUrl) && (
            <div className="flex items-center gap-4 px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700 rounded-b-xl">
              {docsUrl && (
                <a
                  href={docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                >
                  <Book className="h-4 w-4" />
                  Documentation
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {sourceUrl && (
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                >
                  <Code className="h-4 w-4" />
                  Source Code
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
