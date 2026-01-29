const { contextBridge, ipcRenderer } = require('electron')

// Expose protected methods to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Shuttle events
  onFileComplete: (callback) => ipcRenderer.on('shuttle:file-complete', callback),
  onQueueComplete: (callback) => ipcRenderer.on('shuttle:queue-complete', callback),

  // Send events to main process
  sendFileComplete: (data) => ipcRenderer.send('shuttle:file-complete', data),
  sendQueueComplete: (data) => ipcRenderer.send('shuttle:queue-complete', data)
})
