import asyncio
import json
import os
import sys
import threading
import time
import queue
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Tuple, Optional
import base64
import urllib.parse
import uuid

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Load .env for environment variables
try:
    import dotenv
    # Find .env in project root (4 levels up from agent.py)
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '.env')
    dotenv.load_dotenv(dotenv_path=env_path)
except Exception:
    pass

# Autogen / MCP imports - Society of Mind pattern
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import McpWorkbench
from autogen_ext.tools.mcp import StdioServerParams, create_mcp_server_session, mcp_server_tools
from autogen_agentchat.agents import AssistantAgent, SocietyOfMindAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_core.tools import ImageResultContent
from autogen_core.tools import FunctionTool
from pydantic import BaseModel

# Event broadcasting for live GUI updates
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from model_init import init_model_client as shared_init_model_client

# Optional: rich console for nicer logs
try:
    from rich.console import Console
    from rich.traceback import install
    install()
    console = Console()
except Exception:
    console = None

# ========== File helpers ==========
BASE_DIR = os.path.dirname(__file__)
SERVERS_DIR = os.path.dirname(BASE_DIR)  # .../servers
PLUGINS_DIR = os.path.dirname(SERVERS_DIR)  # .../MCP PLUGINS
MODELS_DIR = os.path.join(PLUGINS_DIR, "models")

SYSTEM_PROMPT_PATH = os.path.join(BASE_DIR, "system_prompt.txt")
TASK_PROMPT_PATH = os.path.join(BASE_DIR, "task_prompt.txt")
SERVERS_CONFIG_PATH = os.path.join(SERVERS_DIR, "servers.json")
SECRETS_PATH = os.path.join(SERVERS_DIR, "secrets.json")
MODEL_CONFIG_PATH = os.path.join(MODELS_DIR, "model.json")

# ========== Constants ==========

DEFAULT_UI_HOST = "127.0.0.1"
DEFAULT_UI_PORT = int(os.getenv("MCP_UI_PORT", "8788"))  # Different port than Playwright

DEFAULT_SYSTEM_PROMPT = """You are an AutoGen Assistant with GitHub MCP server integration.
You have access to GitHub repository operations, issue management, pull requests, code search, and more.

Follow the tool usage contract strictly:
- Use github_* tools for repository operations
- Always handle errors gracefully
- Provide clear status updates on operations
- Respect rate limits and authentication

Dynamic event hint: {MCP_EVENT}.
"""

DEFAULT_TASK_PROMPT = """Use the available GitHub tools to accomplish the goal.
Be explicit about which repository you're working with.
Provide progress updates and handle authentication properly.
"""

# ========== Default Prompts (used if modules don't exist or fail to load) ==========

DEFAULT_GITHUB_OPERATOR_PROMPT = """ROLE: GitHub Operator
GOAL: Complete GitHub-related tasks using the available GitHub MCP tools.
TOOLS: Use ONLY the available GitHub MCP tools (github_create_issue, github_list_issues, github_create_pull_request, github_search_repositories, github_get_file_contents, etc.).

GUIDELINES:
- Always specify the repository owner and name clearly (e.g., "owner/repo")
- Handle authentication errors gracefully - report if credentials are missing
- For search operations, use appropriate filters and limits
- For file operations, respect repository permissions
- For issue/PR creation, provide clear titles and descriptions
- Log each step briefly (bullet points)
- Extract only relevant information (concise, structured)
- Do NOT expose sensitive data (tokens, secrets)

WORKFLOW:
1. Understand the task requirements
2. Select appropriate GitHub tool(s)
3. Execute operations with proper error handling
4. Gather results and format clearly
5. When task is complete, provide a compact summary and signal: "READY_FOR_VALIDATION"

OUTPUT FORMAT:
- Brief step log (what was done)
- Results (links, IDs, relevant data)
- Completion signal: "READY_FOR_VALIDATION"
"""

DEFAULT_QA_VALIDATOR_PROMPT = """ROLE: QA Validator
GOAL: Verify that the GitHub task is completely and correctly fulfilled.

VALIDATION CHECKLIST:
- Was the correct repository/organization targeted?
- Were the requested operations completed successfully?
- Are the results accurate and complete?
- Are there any errors or incomplete steps?
- Is sensitive data properly protected?

RESPONSE FORMAT:
- If everything is correct and complete:
  → Respond with "APPROVE" followed by 1-2 bullet points confirming success

- If something is wrong or incomplete:
  → List 1-2 specific issues (what's missing or incorrect)
  → DO NOT approve until issues are resolved
"""

DEFAULT_USER_CLARIFICATION_PROMPT = """ROLE: User Clarification Agent

You are a specialized agent responsible for gathering missing information from the user when the GitHubOperator cannot proceed with a task.

# YOUR TOOL:
You have access to the `ask_user` tool that allows you to ask the user clarification questions.

# RESPONSIBILITIES:
1. Detect when GitHubOperator signals that information is missing
2. Use the ask_user tool to ask the user a clear, specific question
3. The user's answer will come back through the conversation flow
4. Relay the answer back to GitHubOperator

# HOW TO USE THE ask_user TOOL:
When you need clarification, call the tool like this:
ask_user(question="Your clear, concise question here", suggested_answers=["option1", "option2"])

# RULES:
- ALWAYS use the ask_user tool when clarification is needed
- Keep questions SHORT and SPECIFIC
- Use German language for questions (user preference)
- Wait for user's answer to come through the conversation
- Clearly relay the answer back to GitHubOperator
- If multiple pieces of information are missing, ask ONE question at a time
- Never make up or assume answers
"""

# ========== Event Server Components (adapted from Playwright) ==========

class _EventServer(ThreadingHTTPServer):
    """Threaded HTTP server with event broadcasting for GitHub agent."""
    
    daemon_threads = True
    
    def __init__(self, server_address: Tuple[str, int], RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.clients: List[queue.Queue] = []
        self._seq: int = 0
        self._buffer: List[str] = []
        self._buffer_limit: int = 500
    
    def next_seq(self) -> int:
        self._seq += 1
        return self._seq
    
    def broadcast(self, kind: str, payload: Dict[str, Any]):
        """Broadcast an event to all SSE clients and store it in buffer."""
        try:
            channel = payload.pop("channel", "default") or "default"
        except Exception:
            channel = "default"
        seq = self.next_seq()
        # Create event object compatible with MCPSessionViewer format (needs 'value' field)
        msg_obj: Dict[str, Any] = {"type": kind, "seq": seq, "channel": channel, "value": payload}
        try:
            msg = json.dumps(msg_obj, ensure_ascii=False)
        except Exception:
            msg = json.dumps({"type": kind, "seq": seq, "channel": channel, "value": {"message": str(payload)}})
        # Buffer for polling fallback
        self._buffer.append(msg)
        if len(self._buffer) > self._buffer_limit:
            self._buffer = self._buffer[-self._buffer_limit:]
        # Fan out to clients
        for q in list(self.clients):
            try:
                q.put_nowait(msg)
            except Exception:
                pass
    
    def get_events_since(self, since: int) -> Tuple[List[str], int]:
        """Return buffered events with seq > since and the latest seq seen."""
        items: List[str] = []
        last = since
        for s in self._buffer:
            try:
                obj = json.loads(s)
                seq = int(obj.get("seq") or 0)
                if seq > since:
                    items.append(s)
                    if seq > last:
                        last = seq
            except Exception:
                continue
        return items, last


class _UIHandler(BaseHTTPRequestHandler):
    """Minimal UI handler for GitHub agent live viewer."""
    
    INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>GitHub MCP Live Viewer</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background:#0b0f12; color:#e6edf3; }
    header { padding: 12px 16px; background:#11181f; border-bottom:1px solid #26313a; }
    .row { display:flex; gap:12px; padding:12px; }
    .col { flex:1; background:#0f1419; border:1px solid #26313a; border-radius:8px; overflow:auto; min-height: 60vh; }
    .col h3 { margin: 0; padding:10px 12px; border-bottom:1px solid #26313a; background:#0b1116; position:sticky; top:0; }
    pre { white-space: pre-wrap; word-wrap: break-word; margin: 0; padding:10px 12px; }
    .foot { padding:8px 12px; color:#9fb3c8; font-size:12px; border-top:1px solid #26313a; }
    .ok { color:#5bd6a3; } .err { color:#ff7b72; } .tool { color:#91a7ff; }
    .badge { display:inline-block; margin-left:10px; padding:2px 8px; font-size:12px; border-radius:999px; border:1px solid #26313a; background:#0b1116; color:#9fb3c8; }
    .badge-ok { color:#0fd88f; border-color:#155e42; background:#0b1512; }
  </style>
</head>
<body>
  <header>
    <strong>GitHub MCP Live Viewer</strong>
    <span style="margin-left:10px; color:#9fb3c8">Server: GitHub</span>
    <span id="connstatus" class="badge">Connecting…</span>
  </header>
  <div class="row">
    <div class="col" id="stream">
      <h3>Agent Stream</h3>
      <pre id="streamlog"></pre>
    </div>
    <div class="col" id="events">
      <h3>Events</h3>
      <pre id="eventlog"></pre>
    </div>
  </div>
  <div class="foot">Live updates via SSE</div>
  <script>
    const streamEl = document.getElementById('streamlog');
    const eventEl = document.getElementById('eventlog');
    const statusEl = document.getElementById('connstatus');
    
    function append(el, text, cls){
      const span = document.createElement('span');
      if (cls) span.className = cls;
      span.textContent = '[' + new Date().toLocaleTimeString() + '] ' + String(text || '');
      el.appendChild(span);
      el.appendChild(document.createTextNode('\n'));
      el.scrollTop = el.scrollHeight;
    }
    
    function connect(){
      const es = new EventSource('/events');
      es.onopen = () => { statusEl.textContent = 'Connected'; statusEl.className = 'badge badge-ok'; };
      es.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          const t = msg.type || 'status';
          const txt = JSON.stringify(msg);
          if (t === 'agent.message') append(streamEl, txt, 'ok');
          else if (t === 'tool.call') append(eventEl, txt, 'tool');
          else append(eventEl, txt, '');
        } catch(err) { append(eventEl, e.data, ''); }
      };
      es.onerror = () => { statusEl.textContent = 'Reconnecting…'; setTimeout(()=>{ es.close(); connect(); }, 1500); };
    }
    connect();
  </script>
</body>
</html>
"""
    
    def log_message(self, fmt: str, *args) -> None:
        pass
    
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self.INDEX_HTML.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(self.INDEX_HTML.encode("utf-8"))
            return
        
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        
        if self.path.startswith("/events.json"):
            try:
                qs = urllib.parse.urlparse(self.path).query
                qd = urllib.parse.parse_qs(qs)
                since = int((qd.get("since", ["0"]) or ["0"])[0])
            except Exception:
                since = 0
            try:
                items, last = self.server.get_events_since(since)
                body = json.dumps({"since": last, "items": items}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"{}")
            return
        
        if self.path == "/events":
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                q: queue.Queue = queue.Queue()
                self.server.clients.append(q)
                try:
                    self.wfile.write(b":connected\n\n")
                    self.wfile.flush()
                except Exception:
                    return
                while True:
                    try:
                        msg = q.get(timeout=15)
                        payload = ("data: " + str(msg) + "\n\n").encode("utf-8")
                        self.wfile.write(payload)
                        self.wfile.flush()
                    except queue.Empty:
                        try:
                            self.wfile.write(b":keepalive\n\n")
                            self.wfile.flush()
                        except Exception:
                            break
                    except Exception:
                        break
            finally:
                try:
                    self.server.clients.remove(q)
                except Exception:
                    pass
            return
        
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Not Found")


def start_ui_server(
    server_class,
    host: str = DEFAULT_UI_HOST,
    port: int = DEFAULT_UI_PORT
) -> Tuple[ThreadingHTTPServer, threading.Thread, str, int]:
    """Start the UI server in a thread and return (server, thread, bound_host, bound_port)."""
    httpd = server_class
    bound_host, bound_port = httpd.server_address[0], httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, name="github-ui", daemon=True)
    t.start()
    return httpd, t, bound_host, bound_port


def _read_text_file(path: str, default: str = "") -> str:
    """Read content from a text file."""
    try:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return default
    except Exception:
        return default


def load_prompt_from_module(module_name: str, default: str) -> str:
    """Load prompt from a Python module's PROMPT variable."""
    try:
        import importlib.util
        module_path = os.path.join(BASE_DIR, f"{module_name}.py")
        
        if os.path.exists(module_path):
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'PROMPT'):
                    return module.PROMPT
        return default
    except Exception as e:
        if console:
            console.print(f"[yellow]Warning: Failed to load prompt from {module_name}: {e}[/yellow]")
        return default


def create_ask_user_tool(event_server, correlation_id: str = None) -> FunctionTool:
    """Create the ask_user tool for UserClarificationAgent."""
    
    class AskUserArgs(BaseModel):
        question: str
        suggested_answers: Optional[List[str]] = None
    
    async def ask_user_impl(question: str, suggested_answers: Optional[List[str]] = None) -> str:
        """Ask the user a clarification question via GUI."""
        # Generate unique question ID
        question_id = str(uuid.uuid4())
        
        # Broadcast question to GUI with correct event name
        if event_server:
            try:
                event_server.broadcast("user.clarification.request", {
                    "question_id": question_id,
                    "question": question,
                    "suggested_answers": suggested_answers or [],
                    "correlation_id": correlation_id,
                    "ts": time.time()
                })
            except Exception as e:
                if console:
                    console.print(f"[red]Error broadcasting question: {e}[/red]")
        
        # Print to console for visibility
        print(f"\n{'='*60}")
        print(f"❓ USER QUESTION (ID: {question_id}):")
        print(f"   {question}")
        if suggested_answers:
            print(f"   Suggestions: {suggested_answers}")
        print(f"{'='*60}\n")
        
        # Wait for user response by polling the response file
        try:
            # Determine response file path
            import pathlib
            base_dir = pathlib.Path(__file__).resolve().parents[3]  # Navigate up to project root
            tmp_dir = base_dir / "data" / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            
            # Use correlation_id for file name, fallback to question_id
            file_id = correlation_id if correlation_id else question_id
            response_file = tmp_dir / f"clarification_{file_id}.txt"
            
            # Poll for response file (timeout after 5 minutes)
            max_wait = 300  # 5 minutes
            poll_interval = 1  # 1 second
            elapsed = 0
            
            print(f"⏳ Waiting for user response (polling {response_file})...")
            
            while elapsed < max_wait:
                if response_file.exists():
                    # Read and delete the response file
                    try:
                        answer = response_file.read_text(encoding='utf-8').strip()
                        response_file.unlink()  # Delete file after reading
                        
                        print(f"✅ User answered: {answer}")
                        return f"User provided: {answer}"
                    except Exception as e:
                        print(f"⚠️  Error reading response file: {e}")
                        return "Error: Could not read user response"
                
                # Wait before next poll
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
            
            # Timeout reached
            print(f"⏰ Timeout waiting for user response")
            return "Error: User did not respond within timeout (5 minutes)"
            
        except Exception as e:
            print(f"❌ Error in polling mechanism: {e}")
            return f"Error: Polling failed - {e}"
    
    return FunctionTool(
        ask_user_impl,
        description="Ask the user a clarification question when critical information is missing"
    )


# ========== GitHub Agent ==========

def _write_text_file(path: str, content: str) -> None:
    """Write content to a text file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception:
        pass


def get_system_prompt() -> str:
    """Get system prompt for GitHub agent."""
    prompt = _read_text_file(SYSTEM_PROMPT_PATH, DEFAULT_SYSTEM_PROMPT)
    if not os.path.isfile(SYSTEM_PROMPT_PATH):
        _write_text_file(SYSTEM_PROMPT_PATH, DEFAULT_SYSTEM_PROMPT)
    return prompt


def get_task_prompt() -> str:
    """Get task prompt for GitHub operations."""
    prompt = _read_text_file(TASK_PROMPT_PATH, DEFAULT_TASK_PROMPT)
    if not os.path.isfile(TASK_PROMPT_PATH):
        _write_text_file(TASK_PROMPT_PATH, DEFAULT_TASK_PROMPT)
    return prompt


def load_model_config() -> Dict[str, Any]:
    """Load model configuration from models/model.json."""
    if not os.path.isfile(MODEL_CONFIG_PATH):
        return {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
            "api_key_env": "OPENAI_API_KEY"
        }
    try:
        with open(MODEL_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            "model": "gpt-4o-mini",
            "base_url": None,
            "api_key_env": "OPENAI_API_KEY"
        }


def load_servers_config() -> List[Dict[str, Any]]:
    """Load servers configuration from servers.json."""
    if not os.path.isfile(SERVERS_CONFIG_PATH):
        return []
    try:
        with open(SERVERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('servers', [])
    except Exception:
        return []


def load_secrets() -> Dict[str, Any]:
    """Load secrets from secrets.json."""
    if not os.path.isfile(SECRETS_PATH):
        return {}
    try:
        with open(SECRETS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def init_model_client(task: str = "") -> OpenAIChatCompletionClient:
    """Initialize OpenAI chat completion client with intelligent routing.

    Args:
        task: Task description (optional, used for model selection)

    Returns:
        OpenAIChatCompletionClient configured with appropriate model
    """
    # Use shared model initialization utility
    return shared_init_model_client("github", task)


class GitHubAgent:
    """AutoGen agent for GitHub MCP server operations."""

    def __init__(self, model_client: Optional[OpenAIChatCompletionClient] = None):
        self.model_client = model_client or init_model_client()
        self.workbench: Optional[McpWorkbench] = None
        self.assistant: Optional[AssistantAgent] = None
        self._initialized = False
        # New EventServer integration
        self.event_server: Optional[_EventServer] = None
        self.event_http_server = None
        self.event_port: Optional[int] = None

    async def initialize(self) -> None:
        """Initialize the GitHub MCP workbench and agent."""
        if self._initialized:
            return

        # Load server configuration
        servers = load_servers_config()
        github_config = None
        for srv in servers:
            if srv.get("name") == "github" and srv.get("active"):
                github_config = srv
                break

        if not github_config:
            raise ValueError("GitHub MCP server not found or not active in servers.json")

        # Load secrets
        secrets = load_secrets()
        github_secrets = secrets.get("github", {})

        # Prepare environment variables
        env = os.environ.copy()

        # Priority: .env file > secrets.json
        # First check if GITHUB_PERSONAL_ACCESS_TOKEN is in environment
        github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        if github_token:
            env["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
        else:
            # Fallback to secrets.json
            for key, val in github_secrets.items():
                if val:  # Only set if value is not empty
                    env[key] = val

        # Then, override with configured env_vars if present
        env_vars = github_config.get("env_vars", {})
        for key, val in env_vars.items():
            if isinstance(val, str) and val.startswith("env:"):
                env_key = val[4:]
                env_val = os.getenv(env_key)
                if env_val:
                    env[key] = env_val

        # Create MCP server session
        server_params = StdioServerParams(
            command=github_config["command"],
            args=github_config["args"],
            env=env
        )

        # Store server params for context manager usage
        self.server_params = server_params

        # Initialize event server for live GUI updates using new _EventServer
        # Create simple wrapper object for broadcast
        class SimpleEventServer:
            def __init__(self, httpd):
                self._httpd = httpd
            def broadcast(self, kind: str, payload: Dict[str, Any]):
                self._httpd.broadcast(kind, payload)
        
        # Start UI server with dynamic port assignment
        ui_host = DEFAULT_UI_HOST
        ui_port = 0  # Dynamic port assignment
        httpd, thread, bound_host, bound_port = start_ui_server(
            _EventServer((ui_host, 0), _UIHandler), 
            host=ui_host, 
            port=ui_port
        )
        
        self.event_server = SimpleEventServer(httpd)
        self.event_http_server = httpd
        self.event_port = bound_port

        # Announce UI URL
        preview_url = f"http://{bound_host}:{bound_port}/"
        
        # Write event port to file for GUI backend discovery
        try:
            port_file = os.path.join(BASE_DIR, ".event_port")
            with open(port_file, 'w') as f:
                f.write(str(bound_port))
            if console:
                console.print(f"[blue]Event port written to {port_file}: {bound_port}[/blue]")
        except Exception as e:
            if console:
                console.print(f"[yellow]Warning: Failed to write event port file: {e}[/yellow]")
        
        # Broadcast session initialization
        try:
            self.event_server.broadcast("session.initialized", {
                "ui_url": preview_url,
                "host": bound_host,
                "port": bound_port,
                "ts": time.time(),
            })
        except Exception:
            pass
        
        # Print announcement
        print(f"\n{'='*60}")
        print(f"🌐 GitHub MCP Live Viewer: {preview_url}")
        print(f"{'='*60}\n")

        self._initialized = True
        if console:
            console.print(f"[green]GitHub Agent initialized with Society of Mind[/green]")
            console.print(f"[blue]Live Viewer: {preview_url}[/blue]")

    async def run_task(self, task: str, correlation_id: str = None) -> Dict[str, Any]:
        """Execute a GitHub task and return results."""
        if not self._initialized:
            await self.initialize()

        # Reinitialize model client with task-aware model selection
        # This allows intelligent routing based on task complexity
        task_aware_client = init_model_client(task)

        task_prompt = get_task_prompt()
        full_prompt = f"{task_prompt}\n\nTask: {task}"

        try:
            # Use context manager for MCP workbench
            async with McpWorkbench(self.server_params) as mcp:
                # Load Society of Mind prompts
                operator_prompt = load_prompt_from_module("github_operator_prompt", DEFAULT_GITHUB_OPERATOR_PROMPT)
                qa_prompt = load_prompt_from_module("qa_validator_prompt", DEFAULT_QA_VALIDATOR_PROMPT)
                clarification_prompt = load_prompt_from_module("user_clarification_prompt", DEFAULT_USER_CLARIFICATION_PROMPT)

                # Create GitHub Operator agent (with workbench)
                # Use task-aware model client for intelligent routing
                github_operator = AssistantAgent(
                    "GitHubOperator",
                    model_client=task_aware_client,
                    workbench=mcp,
                    system_message=operator_prompt
                )

                # Create ask_user tool for UserClarificationAgent
                ask_user_tool = create_ask_user_tool(
                    event_server=self.event_server,
                    correlation_id=correlation_id
                )

                # Create User Clarification agent WITH ask_user tool
                user_clarification_agent = AssistantAgent(
                    "UserClarificationAgent",
                    model_client=task_aware_client,
                    tools=[ask_user_tool],
                    system_message=clarification_prompt
                )

                # Create QA Validator agent (no tools, pure validation)
                qa_validator = AssistantAgent(
                    "QAValidator",
                    model_client=task_aware_client,
                    system_message=qa_prompt
                )

                # Inner team termination: wait for "APPROVE" from QA Validator
                inner_termination = TextMentionTermination("APPROVE")
                inner_team = RoundRobinGroupChat(
                    [github_operator, user_clarification_agent, qa_validator],
                    termination_condition=inner_termination,
                    max_turns=50  # Increased for user interaction
                )

                # Society of Mind wrapper
                som_agent = SocietyOfMindAgent(
                    "github_society_of_mind",
                    team=inner_team,
                    model_client=task_aware_client
                )

                # Outer team (just the SoM agent)
                team = RoundRobinGroupChat([som_agent], max_turns=1)

                # Run the agent and stream messages
                print(f"\n{'='*60}")
                print(f"🎭 Society of Mind: GitHub Operator + User Clarification + QA Validator")
                print(f"{'='*60}\n")

                # Broadcast session start
                if self.event_server:
                    self.event_server.broadcast("session.status", {
                        "status": "started",
                        "tool": "github",
                        "task": task,
                        "correlation_id": correlation_id
                    })

                messages = []
                async for message in team.run_stream(task=full_prompt):
                    messages.append(message)

                    # Extract and print agent messages for live viewing
                    if hasattr(message, 'source') and hasattr(message, 'content'):
                        source = message.source
                        content = str(message.content)

                        # Pretty print agent dialogue
                        if source == "GitHubOperator":
                            print(f"\n🔧 GitHubOperator:")
                            print(f"   {content[:500]}{'...' if len(content) > 500 else ''}")
                            # Broadcast to GUI
                            if self.event_server:
                                self.event_server.broadcast("agent.message", {
                                    "agent": "GitHubOperator",
                                    "role": "operator",
                                    "content": content,
                                    "icon": "🔧"
                                })
                            
                        elif source == "UserClarificationAgent":
                            print(f"\n❓ UserClarificationAgent:")
                            print(f"   {content[:500]}{'...' if len(content) > 500 else ''}")
                            # Broadcast to GUI
                            if self.event_server:
                                self.event_server.broadcast("agent.message", {
                                    "agent": "UserClarificationAgent",
                                    "role": "clarification",
                                    "content": content,
                                    "icon": "❓"
                                })
                            
                        elif source == "QAValidator":
                            print(f"\n✓ QAValidator:")
                            print(f"   {content[:500]}{'...' if len(content) > 500 else ''}")
                            # Broadcast to GUI
                            if self.event_server:
                                self.event_server.broadcast("agent.message", {
                                    "agent": "QAValidator",
                                    "role": "validator",
                                    "content": content,
                                    "icon": "✓"
                                })

                        # Check for tool calls
                        if hasattr(message, 'content') and isinstance(message.content, list):
                            for item in message.content:
                                if hasattr(item, 'name'):  # Tool call
                                    print(f"   🛠️  Tool: {item.name}")
                                    # Broadcast to GUI
                                    if self.event_server:
                                        self.event_server.broadcast("tool.call", {
                                            "tool": item.name,
                                            "icon": "🛠️"
                                        })

                print(f"\n{'='*60}")
                print(f"✅ Task completed")
                print(f"{'='*60}\n")

                # Broadcast session completion
                if self.event_server:
                    self.event_server.broadcast("session.status", {
                        "status": "completed",
                        "message_count": len(messages)
                    })

                # Extract outputs
                result_text = "\n".join([str(m) for m in messages[-3:]])  # Last few messages
                outputs = {
                    "status": "completed",
                    "result": result_text,
                    "correlation_id": correlation_id,
                    "message_count": len(messages)
                }

                return outputs
        except Exception as e:
            # Broadcast error
            if self.event_server:
                self.event_server.broadcast("session.status", {
                    "status": "error",
                    "error": str(e)
                })
            return {
                "status": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

    async def shutdown(self) -> None:
        """Shutdown the workbench and cleanup."""
        # Shutdown event server
        if self.event_http_server:
            self.event_http_server.shutdown()
            self.event_http_server = None
        # No cleanup needed for workbench - context manager handles it
        self._initialized = False


# ========== Main Entry Point ==========
async def main():
    """Example usage of GitHub agent."""
    agent = GitHubAgent()
    await agent.initialize()

    # Example task
    task = "List the latest issues in the microsoft/vscode repository"
    result = await agent.run_task(task)

    print(json.dumps(result, indent=2))

    await agent.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GitHub MCP Agent with Society of Mind")
    parser.add_argument("--task", help="Task for the agent to execute")
    parser.add_argument("--session-id", dest="session_id", help="Session identifier")
    args = parser.parse_args()

    # If task is provided via CLI, run it
    if args.task:
        async def run_cli():
            agent = GitHubAgent()
            await agent.initialize()
            print(f"Society of Mind: GitHub Operator + QA Validator")
            print(f"Starting task: {args.task}")
            result = await agent.run_task(args.task, correlation_id=args.session_id)
            print(json.dumps(result, indent=2))
            await agent.shutdown()
        asyncio.run(run_cli())
    else:
        # Fallback to example
        asyncio.run(main())