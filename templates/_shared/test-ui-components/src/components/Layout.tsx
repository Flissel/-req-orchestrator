import React, { useState } from 'react';
import { HelpCircle, Menu, X } from 'lucide-react';
import { cn } from '../utils/cn';
import { StatusBar } from './StatusBar';
import { ThemeToggle } from './ThemeToggle';
import { HelpModal } from './HelpModal';
import type { StatusType } from '../types';

interface LayoutProps {
  title: string;
  status: StatusType;
  onStart?: () => void;
  onStop?: () => void;
  onRestart?: () => void;
  sidebar?: React.ReactNode;
  children: React.ReactNode;
  helpTitle?: string;
  helpDescription?: string;
  helpSections?: { title: string; content: string | React.ReactNode }[];
  docsUrl?: string;
  sourceUrl?: string;
}

export function Layout({
  title,
  status,
  onStart,
  onStop,
  onRestart,
  sidebar,
  children,
  helpTitle,
  helpDescription,
  helpSections = [],
  docsUrl,
  sourceUrl,
}: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      {/* Status Bar */}
      <StatusBar
        title={title}
        status={status}
        onStart={onStart}
        onStop={onStop}
        onRestart={onRestart}
      >
        <ThemeToggle />

        {helpSections.length > 0 && (
          <button
            onClick={() => setHelpOpen(true)}
            className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors"
            title="Help"
          >
            <HelpCircle className="h-5 w-5" />
          </button>
        )}

        {sidebar && (
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        )}
      </StatusBar>

      {/* Main Content */}
      <div className="flex">
        {/* Sidebar */}
        {sidebar && (
          <aside
            className={cn(
              "fixed lg:static inset-y-0 left-0 z-40 w-80 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 transform transition-transform lg:transform-none",
              sidebarOpen ? "translate-x-0" : "-translate-x-full"
            )}
            style={{ top: '57px' }}
          >
            <div className="h-full overflow-y-auto p-4">
              {sidebar}
            </div>
          </aside>
        )}

        {/* Backdrop for mobile sidebar */}
        {sidebar && sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
            style={{ top: '57px' }}
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Main content area */}
        <main className={cn(
          "flex-1 p-4 lg:p-6",
          sidebar && "lg:ml-0"
        )}>
          {children}
        </main>
      </div>

      {/* Help Modal */}
      <HelpModal
        isOpen={helpOpen}
        onClose={() => setHelpOpen(false)}
        title={helpTitle || `${title} Help`}
        description={helpDescription}
        sections={helpSections}
        docsUrl={docsUrl}
        sourceUrl={sourceUrl}
      />
    </div>
  );
}
