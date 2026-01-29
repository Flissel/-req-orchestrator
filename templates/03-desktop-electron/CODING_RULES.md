# {{PROJECT_NAME}} - Coding Rules

## Electron Desktop App Implementierungsrichtlinien

---

## 1. Projekt-Architektur

### 1.1 Electron Process Model
```
┌─────────────────────────────────────────────────────┐
│                    MAIN PROCESS                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   main.ts    │  │  ipc/*.ts    │  │ services  │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
└────────────────────────┬────────────────────────────┘
                         │ IPC
┌────────────────────────▼────────────────────────────┐
│                  RENDERER PROCESS                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   React UI   │  │  Components  │  │   Hooks   │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────┘
```

### 1.2 Datei-Benennungen

| Typ | Convention | Beispiel |
|-----|-----------|----------|
| Components | PascalCase | `MainWindow.tsx` |
| IPC Handlers | camelCase | `fileHandlers.ts` |
| Services | camelCase | `databaseService.ts` |
| Hooks | camelCase + use | `useIpcInvoke.ts` |

---

## 2. Main Process Regeln

### 2.1 Window Management

```typescript
// ✅ RICHTIG: Zentrale Window-Factory
export function createMainWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  return win;
}

// ❌ FALSCH: Inline Window-Erstellung
const win = new BrowserWindow({...});
```

### 2.2 IPC Security

```typescript
// ✅ RICHTIG: Typisierte IPC Handler
// electron/ipc/fileHandlers.ts
export const fileHandlers = {
  'file:read': async (event, path: string): Promise<string> => {
    // Validate path first!
    if (!isAllowedPath(path)) {
      throw new Error('Path not allowed');
    }
    return fs.promises.readFile(path, 'utf-8');
  },
};

// ❌ FALSCH: Unvalidierte Pfade
ipcMain.handle('read-file', (e, path) => fs.readFileSync(path));
```

### 2.3 Preload Script

```typescript
// electron/preload.ts
import { contextBridge, ipcRenderer } from 'electron';

// ✅ RICHTIG: Expose nur benötigte APIs
contextBridge.exposeInMainWorld('api', {
  readFile: (path: string) => ipcRenderer.invoke('file:read', path),
  writeFile: (path: string, data: string) => 
    ipcRenderer.invoke('file:write', path, data),
  onUpdate: (callback: () => void) => 
    ipcRenderer.on('update-available', callback),
});

// ❌ FALSCH: Electron APIs direkt exposen
contextBridge.exposeInMainWorld('electron', require('electron'));
```

---

## 3. Renderer Process Regeln

### 3.1 IPC Hook Pattern

```typescript
// src/hooks/useIpc.ts
export function useIpcInvoke<T>(channel: string) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const invoke = useCallback(async (...args: unknown[]): Promise<T> => {
    setLoading(true);
    setError(null);
    try {
      const result = await window.api[channel](...args);
      return result as T;
    } catch (e) {
      setError(e as Error);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [channel]);

  return { invoke, loading, error };
}
```

### 3.2 Component Structure

```typescript
// src/components/FileExplorer/FileExplorer.tsx
interface FileExplorerProps {
  initialPath?: string;
  onFileSelect: (path: string) => void;
}

export function FileExplorer({ initialPath, onFileSelect }: FileExplorerProps) {
  const { invoke: readDir } = useIpcInvoke<string[]>('readDir');
  const [files, setFiles] = useState<string[]>([]);

  useEffect(() => {
    readDir(initialPath || '.').then(setFiles);
  }, [initialPath]);

  return (
    <div className="file-explorer">
      {files.map(file => (
        <FileItem key={file} name={file} onClick={() => onFileSelect(file)} />
      ))}
    </div>
  );
}
```

---

## 4. Database Integration (SQLite)

### 4.1 Database Service

```typescript
// electron/services/database.ts
import Database from 'better-sqlite3';

class DatabaseService {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.migrate();
  }

  private migrate() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
  }

  getAll() {
    return this.db.prepare('SELECT * FROM items').all();
  }

  insert(name: string) {
    return this.db.prepare('INSERT INTO items (name) VALUES (?)').run(name);
  }
}

export const database = new DatabaseService(
  path.join(app.getPath('userData'), 'database.sqlite')
);
```

---

## 5. Python Backend Integration (Optional)

### 5.1 Python Process Spawning

```typescript
// electron/services/pythonBackend.ts
import { spawn, ChildProcess } from 'child_process';

class PythonBackend {
  private process: ChildProcess | null = null;

  async start(): Promise<void> {
    const pythonPath = this.getPythonPath();
    this.process = spawn(pythonPath, ['main.py'], {
      cwd: path.join(__dirname, '..', 'python-backend'),
    });

    return new Promise((resolve, reject) => {
      this.process?.stdout?.on('data', (data) => {
        if (data.toString().includes('Started')) resolve();
      });
      this.process?.stderr?.on('data', reject);
    });
  }

  async stop(): Promise<void> {
    this.process?.kill();
    this.process = null;
  }

  private getPythonPath(): string {
    return process.platform === 'win32' ? 'python' : 'python3';
  }
}
```

---

## 6. Build & Distribution

### 6.1 electron-builder.yml

```yaml
appId: com.{{PROJECT_NAME_KEBAB}}.app
productName: {{PROJECT_NAME}}
directories:
  output: dist
  buildResources: build

files:
  - "dist-electron/**/*"
  - "dist/**/*"
  - "python-backend/**/*"

win:
  target: nsis
  icon: build/icon.ico

mac:
  target: dmg
  icon: build/icon.icns

linux:
  target: AppImage
  icon: build/icon.png

extraResources:
  - from: python-backend
    to: python-backend
    filter:
      - "**/*"
      - "!venv/**"
```

---

## 7. Checkliste vor Commit

- [ ] TypeScript kompiliert ohne Fehler
- [ ] Keine Sicherheitslücken in IPC Handlern
- [ ] contextIsolation ist aktiviert
- [ ] nodeIntegration ist deaktiviert
- [ ] Preload exposes nur notwendige APIs
- [ ] Alle Pfade werden validiert
- [ ] Cross-Platform-Kompatibilität geprüft