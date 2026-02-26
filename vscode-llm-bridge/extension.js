const vscode = require('vscode');
const http = require('http');

let server = null;
let statusBarItem = null;

/**
 * VS Code LLM Bridge Extension
 * Creates a local OpenAI-compatible HTTP server that forwards
 * requests to VS Code's built-in Copilot GPT-4o model.
 */

function activate(context) {
    console.log('LLM Bridge: Extension activating...');

    // Status bar indicator
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'vscode-llm-bridge.status';
    context.subscriptions.push(statusBarItem);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('vscode-llm-bridge.start', () => startServer(context)),
        vscode.commands.registerCommand('vscode-llm-bridge.stop', stopServer),
        vscode.commands.registerCommand('vscode-llm-bridge.status', showStatus)
    );

    // Auto-start if configured
    const config = vscode.workspace.getConfiguration('vscode-llm-bridge');
    if (config.get('autoStart', true)) {
        startServer(context);
    }
}

async function startServer(context) {
    if (server) {
        vscode.window.showInformationMessage('LLM Bridge server is already running.');
        return;
    }

    const config = vscode.workspace.getConfiguration('vscode-llm-bridge');
    const port = config.get('port', 5678);

    server = http.createServer(async (req, res) => {
        // CORS headers
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

        if (req.method === 'OPTIONS') {
            res.writeHead(200);
            res.end();
            return;
        }

        // Health check
        if (req.method === 'GET' && req.url === '/') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ok', service: 'vscode-llm-bridge' }));
            return;
        }

        // Models endpoint
        if (req.method === 'GET' && req.url === '/v1/models') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
                object: 'list',
                data: [
                    { id: 'gpt-4o', object: 'model', owned_by: 'vscode-copilot' },
                    { id: 'gpt-4o-mini', object: 'model', owned_by: 'vscode-copilot' }
                ]
            }));
            return;
        }

        // Chat completions endpoint
        if (req.method === 'POST' && req.url === '/v1/chat/completions') {
            let body = '';
            req.on('data', chunk => { body += chunk; });
            req.on('end', async () => {
                try {
                    const request = JSON.parse(body);
                    const stream = request.stream || false;

                    if (stream) {
                        await handleStreamingRequest(request, res);
                    } else {
                        await handleNonStreamingRequest(request, res);
                    }
                } catch (err) {
                    console.error('LLM Bridge error:', err);
                    res.writeHead(500, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({
                        error: {
                            message: err.message || 'Internal server error',
                            type: 'server_error',
                            code: 'internal_error'
                        }
                    }));
                }
            });
            return;
        }

        // 404 for unknown routes
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: { message: 'Not found' } }));
    });

    server.listen(port, '127.0.0.1', () => {
        const msg = `LLM Bridge server running on http://127.0.0.1:${port}`;
        console.log(msg);
        vscode.window.showInformationMessage(msg);
        updateStatusBar(port);
    });

    server.on('error', (err) => {
        console.error('LLM Bridge server error:', err);
        if (err.code === 'EADDRINUSE') {
            vscode.window.showErrorMessage(`Port ${port} is already in use. Change the port in settings.`);
        } else {
            vscode.window.showErrorMessage(`LLM Bridge server error: ${err.message}`);
        }
        server = null;
        updateStatusBar(null);
    });
}

async function handleNonStreamingRequest(request, res) {
    const messages = request.messages || [];
    const responseFormat = request.response_format || null;

    // Select GPT-4o model from VS Code Copilot
    let models;
    try {
        models = await vscode.lm.selectChatModels({ vendor: 'copilot', family: 'gpt-4o' });
    } catch (e) {
        // Fallback: try any copilot model
        models = await vscode.lm.selectChatModels({ vendor: 'copilot' });
    }

    if (!models || models.length === 0) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
            error: {
                message: 'No Copilot model available. Make sure GitHub Copilot is active in VS Code.',
                type: 'service_unavailable',
                code: 'model_not_found'
            }
        }));
        return;
    }

    const model = models[0];

    // Convert OpenAI messages to VS Code LM messages
    const vsMessages = messages.map(msg => {
        if (msg.role === 'system') {
            return vscode.LanguageModelChatMessage.User(`[System Instruction]: ${msg.content}`);
        } else if (msg.role === 'assistant') {
            return vscode.LanguageModelChatMessage.Assistant(msg.content);
        } else {
            return vscode.LanguageModelChatMessage.User(msg.content);
        }
    });

    // If JSON response is requested, add instruction
    if (responseFormat && responseFormat.type === 'json_object') {
        vsMessages.push(
            vscode.LanguageModelChatMessage.User(
                '[Important: Your response MUST be valid JSON only. No markdown, no code blocks, no explanation — just raw JSON.]'
            )
        );
    }

    // Send request to VS Code LM
    const cancellationTokenSource = new vscode.CancellationTokenSource();
    const response = await model.sendRequest(vsMessages, {}, cancellationTokenSource.token);

    // Collect the full response
    let fullText = '';
    for await (const chunk of response.text) {
        fullText += chunk;
    }

    // Build OpenAI-compatible response
    const completionResponse = {
        id: `chatcmpl-${Date.now()}`,
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: model.id || 'gpt-4o',
        choices: [{
            index: 0,
            message: {
                role: 'assistant',
                content: fullText
            },
            finish_reason: 'stop'
        }],
        usage: {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0
        }
    };

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(completionResponse));
}

async function handleStreamingRequest(request, res) {
    const messages = request.messages || [];

    let models;
    try {
        models = await vscode.lm.selectChatModels({ vendor: 'copilot', family: 'gpt-4o' });
    } catch (e) {
        models = await vscode.lm.selectChatModels({ vendor: 'copilot' });
    }

    if (!models || models.length === 0) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
            error: { message: 'No Copilot model available', type: 'service_unavailable' }
        }));
        return;
    }

    const model = models[0];
    const vsMessages = messages.map(msg => {
        if (msg.role === 'system') {
            return vscode.LanguageModelChatMessage.User(`[System Instruction]: ${msg.content}`);
        } else if (msg.role === 'assistant') {
            return vscode.LanguageModelChatMessage.Assistant(msg.content);
        } else {
            return vscode.LanguageModelChatMessage.User(msg.content);
        }
    });

    res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    });

    const cancellationTokenSource = new vscode.CancellationTokenSource();
    const response = await model.sendRequest(vsMessages, {}, cancellationTokenSource.token);

    const streamId = `chatcmpl-${Date.now()}`;

    for await (const chunk of response.text) {
        const data = {
            id: streamId,
            object: 'chat.completion.chunk',
            created: Math.floor(Date.now() / 1000),
            model: model.id || 'gpt-4o',
            choices: [{
                index: 0,
                delta: { content: chunk },
                finish_reason: null
            }]
        };
        res.write(`data: ${JSON.stringify(data)}\n\n`);
    }

    // Send final chunk
    const finalData = {
        id: streamId,
        object: 'chat.completion.chunk',
        created: Math.floor(Date.now() / 1000),
        model: model.id || 'gpt-4o',
        choices: [{
            index: 0,
            delta: {},
            finish_reason: 'stop'
        }]
    };
    res.write(`data: ${JSON.stringify(finalData)}\n\n`);
    res.write('data: [DONE]\n\n');
    res.end();
}

function stopServer() {
    if (server) {
        server.close(() => {
            vscode.window.showInformationMessage('LLM Bridge server stopped.');
        });
        server = null;
        updateStatusBar(null);
    } else {
        vscode.window.showInformationMessage('LLM Bridge server is not running.');
    }
}

function showStatus() {
    if (server) {
        const config = vscode.workspace.getConfiguration('vscode-llm-bridge');
        const port = config.get('port', 5678);
        vscode.window.showInformationMessage(`LLM Bridge: Running on http://127.0.0.1:${port}`);
    } else {
        vscode.window.showInformationMessage('LLM Bridge: Server is stopped.');
    }
}

function updateStatusBar(port) {
    if (port) {
        statusBarItem.text = `$(radio-tower) LLM Bridge :${port}`;
        statusBarItem.tooltip = `LLM Bridge running on port ${port}`;
        statusBarItem.backgroundColor = undefined;
        statusBarItem.show();
    } else {
        statusBarItem.text = '$(radio-tower) LLM Bridge: OFF';
        statusBarItem.tooltip = 'Click to check LLM Bridge status';
        statusBarItem.show();
    }
}

function deactivate() {
    if (server) {
        server.close();
        server = null;
    }
}

module.exports = { activate, deactivate };
