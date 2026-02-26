# LLM Bridge — OpenAI-Compatible Proxy for VS Code Copilot

The **LLM Bridge** turns your VS Code Copilot subscription (GPT-4o) into a local, OpenAI-compatible API server that the AI Short Video Engine can call — **completely free**, no extra API keys needed.

---

## How It Works

```
┌──────────────┐     HTTP/JSON      ┌──────────────────┐     VS Code LM API     ┌──────────────┐
│  Video Engine │ ───────────────►  │  LLM Bridge       │ ────────────────────►  │ VS Code      │
│  (app.py)     │  localhost:5199   │  (FastAPI thread)  │                        │ Copilot GPT-4o│
└──────────────┘                    └──────────────────┘                         └──────────────┘
```

There are **two bridge modes**:

| Mode                  | How                                                             | When to Use                 |
| --------------------- | --------------------------------------------------------------- | --------------------------- |
| **Built-in Bridge**   | Auto-starts as a daemon thread inside `app.py` on port **5199** | Quick start, no extra setup |
| **VS Code Extension** | A `.vsix` extension that runs inside VS Code on port **5678**   | Full Copilot GPT-4o access  |

---

## Quick Start (Built-in Bridge)

The built-in bridge starts automatically when you run `python app.py`. No extra setup required.

### 1. Configure `config.toml`

```toml
[llm]
llm_source = "vscode"

[llm.vscode]
api_key = "vscode-bridge"
base_url = "http://127.0.0.1:5199/v1"
model = "copilot-chat"
```

### 2. Set Upstream (Required)

The built-in bridge is a **proxy** — it needs an upstream LLM to forward requests to.
Set these environment variables before running `app.py`:

**Windows (PowerShell):**

```powershell
$env:VSCODE_LLM_UPSTREAM_URL = "https://api.openai.com"
$env:VSCODE_LLM_UPSTREAM_KEY = "sk-your-openai-key"
python app.py
```

**Windows (CMD):**

```cmd
set VSCODE_LLM_UPSTREAM_URL=https://api.openai.com
set VSCODE_LLM_UPSTREAM_KEY=sk-your-openai-key
python app.py
```

**Linux / macOS:**

```bash
export VSCODE_LLM_UPSTREAM_URL="https://api.openai.com"
export VSCODE_LLM_UPSTREAM_KEY="sk-your-openai-key"
python app.py
```

You can point the upstream to **any** OpenAI-compatible API:

| Provider             | VSCODE_LLM_UPSTREAM_URL                                   | Key Required     |
| -------------------- | --------------------------------------------------------- | ---------------- |
| OpenAI               | `https://api.openai.com`                                  | Yes              |
| Gemini (OpenAI mode) | `https://generativelanguage.googleapis.com/v1beta/openai` | Yes (Gemini key) |
| DeepSeek             | `https://api.deepseek.com`                                | Yes              |
| Local (Ollama)       | `http://localhost:11434`                                  | No               |
| LM Studio            | `http://localhost:1234`                                   | No               |

### 3. Run

```bash
python app.py
# Log shows: "LLM bridge started on 127.0.0.1:5199"
```

### 4. Verify

```bash
# Health check
curl http://127.0.0.1:5199/health

# List models
curl http://127.0.0.1:5199/v1/models

# Test completion
curl http://127.0.0.1:5199/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"copilot-chat","messages":[{"role":"user","content":"Hello"}]}'
```

---

## VS Code Extension (Full Copilot Access)

This mode runs **inside VS Code** and uses the real Copilot GPT-4o model directly — no upstream key needed.

### Installation

1. Open VS Code
2. Go to **Extensions** panel (`Ctrl+Shift+X`)
3. Click `...` menu → **Install from VSIX...**
4. Select: `vscode-llm-bridge/vscode-llm-bridge-1.0.0.vsix`
5. Reload VS Code

### Configuration

The extension auto-starts on VS Code launch. Default port: **5678**.

Update `config.toml` to point to the extension:

```toml
[llm]
llm_source = "vscode"

[llm.vscode]
api_key = "vscode-bridge"
base_url = "http://127.0.0.1:5678/v1"
model = "gpt-4o"
```

### Extension Commands

Open Command Palette (`Ctrl+Shift+P`):

| Command                     | Description                |
| --------------------------- | -------------------------- |
| `LLM Bridge: Start Server`  | Start the bridge server    |
| `LLM Bridge: Stop Server`   | Stop the bridge server     |
| `LLM Bridge: Server Status` | Check if bridge is running |

### Extension Settings

In VS Code Settings (`Ctrl+,`):

| Setting                       | Default | Description                      |
| ----------------------------- | ------- | -------------------------------- |
| `vscode-llm-bridge.port`      | `5678`  | Server port                      |
| `vscode-llm-bridge.autoStart` | `true`  | Start automatically with VS Code |

### Requirements

- **VS Code** 1.90.0 or higher
- **GitHub Copilot** extension installed and active
- Active Copilot subscription (free or paid)

---

## API Endpoints

Both bridge modes expose these OpenAI-compatible endpoints:

| Method | Endpoint               | Description                                  |
| ------ | ---------------------- | -------------------------------------------- |
| GET    | `/v1/models`           | List available models                        |
| POST   | `/v1/chat/completions` | Chat completions (streaming & non-streaming) |
| GET    | `/health`              | Health check (built-in bridge only)          |

### Request Format

Standard OpenAI chat completions format:

```json
{
  "model": "copilot-chat",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Explain quantum computing in 50 words." }
  ],
  "response_format": { "type": "json_object" },
  "stream": false
}
```

### Response Format

```json
{
  "id": "chatcmpl-1234567890",
  "object": "chat.completion",
  "model": "gpt-4o",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Quantum computing uses..."
      },
      "finish_reason": "stop"
    }
  ]
}
```

---

## Troubleshooting

### "LLM Bridge is running but no upstream LLM is configured"

**Cause:** Built-in bridge has no upstream. Set `VSCODE_LLM_UPSTREAM_URL` env var, or switch to a direct provider:

```toml
[llm]
llm_source = "gemini"   # or "deepseek", "openai"
```

### "No Copilot model available" (VS Code Extension)

**Cause:** GitHub Copilot is not active.
**Fix:** Ensure the Copilot extension is installed, signed in, and has an active subscription.

### "404 page not found"

**Cause:** The bridge port doesn't match `config.toml`.

- Built-in bridge: port **5199** → `base_url = "http://127.0.0.1:5199/v1"`
- VS Code extension: port **5678** → `base_url = "http://127.0.0.1:5678/v1"`

### Port conflict

If port 5199 or 5678 is already in use:

- Built-in: Edit `BRIDGE_PORT` in `services/llm_bridge.py`
- Extension: Change `vscode-llm-bridge.port` in VS Code Settings

---

## Architecture

```
services/llm_bridge.py     → Built-in FastAPI bridge (port 5199, daemon thread)
vscode-llm-bridge/
├── extension.js            → VS Code extension (port 5678)
├── package.json            → Extension manifest
└── vscode-llm-bridge-1.0.0.vsix  → Pre-built VSIX package
```

### Built-in Bridge Flow

1. `app.py` calls `start_bridge_server()` on startup
2. A daemon thread launches a FastAPI server on `127.0.0.1:5199`
3. Incoming requests are proxied to the upstream URL (env var)
4. If no upstream is set, returns an error message
5. Thread stops automatically when `app.py` exits

### VS Code Extension Flow

1. Extension activates on VS Code startup
2. Creates an HTTP server on `127.0.0.1:5678`
3. Incoming requests call `vscode.lm.selectChatModels()` for Copilot GPT-4o
4. Streams or collects the response and returns OpenAI-compatible JSON
5. Supports both streaming and non-streaming modes

---

## Alternative: Skip the Bridge

If you don't need VS Code Copilot, use a direct LLM provider instead:

```toml
# Option 1: Gemini (free tier available)
[llm]
llm_source = "gemini"
[llm.gemini]
api_key = "your-gemini-key"
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
model = "gemini-2.0-flash"

# Option 2: DeepSeek
[llm]
llm_source = "deepseek"
api_key = "your-deepseek-key"
base_url = "https://api.deepseek.com"
model = "deepseek-chat"

# Option 3: OpenAI
[llm]
llm_source = "openai"
[llm.openai]
api_key = "your-openai-key"
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
```

Select the provider in the web UI sidebar under **"Select LLM Source"**.
