const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')

let mainWindow

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    backgroundColor: '#0a0a1a',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    frame: true,
    titleBarStyle: 'default',
    title: 'Arch Platform - Space Mission Control'
  })

  // Load the Space UI with Shuttle
  mainWindow.loadFile('index.html')

  // Open DevTools in dev mode
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools()
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})

// IPC handlers for Shuttle communication
ipcMain.on('shuttle:file-complete', (event, data) => {
  console.log('[Shuttle] File processed:', data.fileName)
})

ipcMain.on('shuttle:queue-complete', (event, data) => {
  console.log('[Shuttle] Queue complete:', data.fileCount, 'files processed')
})
