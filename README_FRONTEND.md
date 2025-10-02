# arch_team React Frontend

Modern React-based frontend for the arch_team requirements mining and knowledge graph generation platform.

## Features

- **Requirements Mining**: Upload documents (Markdown, PDF, DOCX) and extract structured requirements using the ChunkMiner agent
- **Knowledge Graph Visualization**: Interactive cytoscape.js visualization of extracted requirements and their relationships
- **File Preview**: Live preview of uploaded documents
- **Real-time Logs**: Monitor the mining process with detailed logs
- **Agent Status**: Track the status of ChunkMiner and KG agents in real-time

## Prerequisites

1. **Backend Service Running**: The arch_team Flask service must be running on port 8000
   ```bash
   python -m arch_team.service
   ```

2. **Node.js**: Version 16+ required

## Installation

```bash
npm install
```

## Running the Frontend

### Development Mode

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

### Production Build

```bash
npm run build
npm run preview
```

## Architecture

### Components

**App.jsx** - Main application container
- Manages global state (requirements, KG data, logs)
- Handles file uploads and mining orchestration
- Coordinates communication with backend APIs

**Configuration.jsx** - Upload and settings panel
- File upload with drag & drop support
- Model selection (gpt-4o-mini, gpt-4o, gpt-4)
- Neighbor evidence toggle (±1 chunk context)
- Sample file loader for testing
- Advanced options (LLM-based KG expansion)

**KnowledgeGraph.jsx** - Graph visualization
- Cytoscape.js integration for interactive graphs
- Node types: Requirement, Tag, Actor, Entity, Action
- Fit view and PNG export functionality
- Stats display (nodes, edges, requirements, tags)

**Requirements.jsx** - Requirements list view
- Displays all extracted requirements
- Shows req_id, title, tag, and evidence
- Color-coded by requirement type

**AgentStatus.jsx** - Agent monitoring
- Real-time status of ChunkMiner and KG agents
- Visual indicators (waiting, active, completed, error)
- Pulsing animation for active agents

### API Integration

**POST /api/mining/upload**
- Accepts multipart file upload
- Optional params: `model`, `neighbor_refs`
- Returns: `{success, count, items: [DTO, ...]}`

**POST /api/kg/build**
- JSON payload: `{items, options: {persist, use_llm, llm_fallback}}`
- Returns: `{success, stats, nodes, edges}`

## Usage

1. **Load Sample File**: Click "Beispieldatei laden" to load the Moiré Mouse Tracking requirements
2. **Or Upload Your Own**: Select Markdown, PDF, or DOCX files
3. **Configure Options**:
   - Choose model (gpt-4o-mini recommended for speed)
   - Enable neighbor evidence for better context
   - Toggle LLM-based KG expansion (advanced)
4. **Start Mining**: Click "Mining starten"
5. **View Results**:
   - Requirements list at the bottom
   - Knowledge Graph in the center panel
   - File preview on the right

## Configuration

### Environment Variables

The app connects to the backend via proxy (configured in `vite.config.js`):
- `/api/*` → `http://localhost:8000`
- `/data/*` → `http://localhost:8000`

To change the backend URL, edit `vite.config.js`:

```javascript
proxy: {
  '/api': {
    target: 'http://your-backend:8000',
    changeOrigin: true
  }
}
```

### Styling

The app uses CSS custom properties for theming (see `src/App.css`):
- `--bg`: Background color (#0b0e14)
- `--fg`: Foreground/text color (#e6e6e6)
- `--accent`: Accent color (#4cc9f0)
- `--ok`: Success color (#22c55e)
- `--err`: Error color (#ef4444)

## Knowledge Graph

### Node Types
- **Requirement**: Extracted requirements (rounded rectangles, blue)
- **Tag**: Categories like functional, security, performance (hexagons, light blue)
- **Actor**: Users, systems (ellipses, purple)
- **Entity**: Entities mentioned in requirements (rectangles, orange)
- **Action**: Verbs/actions (diamonds, green)

### Edge Types
- **HAS_TAG**: Requirement → Tag
- **HAS_ACTOR**: Requirement → Actor
- **HAS_ACTION**: Requirement → Action
- **ON_ENTITY**: Action → Entity

### Interactions
- Click nodes to see details in console
- Use "Fit View" to center the graph
- Export PNG for documentation

## Testing with Sample Data

The sample file (`data/moire_mouse_tracking_requirements.md`) contains a comprehensive requirements document for a Moiré-based mouse tracking system. Use it to test:

1. **Requirements Extraction**: Should extract 30-50 requirements
2. **Knowledge Graph**: Should generate 80-150 nodes with various types
3. **Neighbor Evidence**: Compare results with/without neighbor evidence enabled

## Troubleshooting

**"Sample file could not be loaded"**
- Ensure `data/moire_mouse_tracking_requirements.md` exists
- Check that the backend service is serving static files

**"Mining failed" or network errors**
- Verify arch_team service is running on port 8000
- Check browser console for CORS issues
- Ensure OpenAI API key is configured in backend `.env`

**Knowledge Graph not rendering**
- Cytoscape.js loads from CDN - check internet connection
- Clear browser cache and reload

**No requirements extracted**
- Check backend logs for errors
- Verify file format is supported (MD, TXT, PDF, DOCX)
- Try with neighbor evidence enabled

## Performance

- **gpt-4o-mini**: ~5-10 seconds for 20KB document
- **gpt-4o**: ~15-30 seconds for 20KB document
- KG building: ~1-3 seconds for 50 requirements
- Neighbor evidence adds ~20% processing time but improves quality

## Dependencies

```json
{
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "vite": "^6.0.11",
  "@vitejs/plugin-react": "^4.3.4"
}
```

External CDN:
- Cytoscape.js 3.26.0 (loaded dynamically in KnowledgeGraph component)

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Development

### Project Structure

```
src/
├── App.jsx              # Main container
├── App.css              # Global styles
├── components/
│   ├── AgentStatus.jsx  # Agent monitoring
│   ├── Configuration.jsx # Upload & settings
│   ├── KnowledgeGraph.jsx # Graph visualization
│   └── Requirements.jsx  # Requirements list
├── index.css            # CSS reset
└── main.jsx             # React entry point
```

### Adding New Features

1. **New Agent**: Add to `agents` state in App.jsx
2. **New API Endpoint**: Add proxy rule in vite.config.js
3. **New Node Type**: Update KG styles in KnowledgeGraph.jsx

## License

Part of the arch_team requirements engineering system.
