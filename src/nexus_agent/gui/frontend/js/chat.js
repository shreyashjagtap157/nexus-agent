/**
 * NexusAgent — Chat Controller & WebSocket Streamer
 */

const Chat = {
    socket: null,
    activeAssistantBubble: null,
    accumulatedResponse: "",

    /**
     * Connect to the backend WebSocket server.
     */
    connect(sessionId) {
        if (this.socket) {
            this.socket.close();
        }

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/api/ws/${sessionId}`;
        
        console.log(`Connecting WebSocket: ${wsUrl}`);
        this.socket = new WebSocket(wsUrl);

        const wsStatus = document.getElementById("ws-status");

        this.socket.onopen = () => {
            console.log("WebSocket connected!");
            wsStatus.className = "connection-status connected";
            wsStatus.title = "Connected to local Agent Core";
            document.getElementById("btn-send-prompt").disabled = false;
        };

        this.socket.onclose = () => {
            console.warn("WebSocket disconnected.");
            wsStatus.className = "connection-status";
            wsStatus.title = "Disconnected. Reconnecting...";
            document.getElementById("btn-send-prompt").disabled = true;
            // Attempt auto-reconnect after 3 seconds
            setTimeout(() => this.connect(sessionId), 3000);
        };

        this.socket.onerror = (err) => {
            console.error("WebSocket error: ", err);
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
    },

    /**
     * Send user input over WebSocket.
     */
    sendMessage(prompt, mode = "auto") {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            console.error("WebSocket is not connected.");
            return;
        }

        // Add user bubble
        this.appendMessage("user", prompt);
        
        // Disable text area during execution
        document.getElementById("prompt-textarea").disabled = true;
        document.getElementById("btn-send-prompt").disabled = true;

        // Reset response accumulator
        this.accumulatedResponse = "";
        this.activeAssistantBubble = null;

        // Dispatch prompt over WebSocket
        this.socket.send(JSON.stringify({ prompt, mode }));
    },

    /**
     * Handle incoming streaming messages.
     */
    handleWebSocketMessage(data) {
        const logPanel = document.getElementById("agent-activity-log");
        const activeModelDisplay = document.getElementById("active-model-display");

        switch (data.type) {
            case "thinking":
                this.logActivity("thinking", `[THINKING] ${data.content}`);
                break;

            case "chunk":
                this.accumulatedResponse += data.content;
                this.streamAssistantMessage(this.accumulatedResponse);
                break;

            case "tool_call":
                this.logActivity("tool", `[TOOL CALL] Invoking: ${data.name}`);
                this.appendToolCallBlock(data.name, data.arguments);
                break;

            case "tool_result":
                const statusSymbol = data.success ? "success" : "error";
                this.logActivity(statusSymbol, `[TOOL RESULT] ${data.name}: ${data.success ? 'OK' : 'FAILED'}`);
                this.updateToolCallResult(data.name, data.success, data.output);
                break;

            case "error":
                this.logActivity("error", `[ERROR] ${data.content}`);
                this.appendMessage("system", `⚠️ Core Error: ${data.content}`);
                break;

            case "done":
                this.logActivity("success", `[COMPLETED] Reason: Stop. Total iterations: ${data.iterations}`);
                
                // Re-enable text inputs
                const textInput = document.getElementById("prompt-textarea");
                textInput.disabled = false;
                textInput.value = "";
                textInput.focus();
                document.getElementById("btn-send-prompt").disabled = false;
                
                // Sync status stats
                App.syncStatus();
                break;
        }
    },

    /**
     * Append a message bubble to the messages panel.
     */
    appendMessage(role, content) {
        const container = document.getElementById("chat-messages-container");
        
        // Remove welcome card if visible
        const welcomeCard = container.querySelector(".welcome-card-container");
        if (welcomeCard) {
            welcomeCard.remove();
        }

        const bubble = document.createElement("div");
        bubble.className = `msg-bubble ${role}`;
        
        // Use custom simple markdown parsing for readability
        bubble.innerHTML = Utils.parseSimpleMarkdown(content);
        
        container.appendChild(bubble);
        container.scrollTop = container.scrollHeight;
        
        return bubble;
    },

    /**
     * Stream chunk data into assistant response bubble.
     */
    streamAssistantMessage(content) {
        if (!this.activeAssistantBubble) {
            this.activeAssistantBubble = this.appendMessage("assistant", "");
        }
        this.activeAssistantBubble.innerHTML = Utils.parseSimpleMarkdown(content);
        
        const container = document.getElementById("chat-messages-container");
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Add tool call metadata block into conversation.
     */
    appendToolCallBlock(name, args) {
        const container = document.getElementById("chat-messages-container");
        const block = document.createElement("div");
        block.className = "tool-call-block";
        block.id = `tool-call-${name}`;
        
        block.innerHTML = `
            <div class="tool-header">
                <span>🔧 Executing: ${name}</span>
                <span class="loader-small" style="width: 12px; height: 12px; margin: 0; display: inline-block;"></span>
            </div>
            <div class="tool-args">${Utils.escapeHtml(JSON.stringify(args, null, 2))}</div>
        `;
        
        container.appendChild(block);
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Update active tool call card with result values.
     */
    updateToolCallResult(name, success, output) {
        const block = document.getElementById(`tool-call-${name}`);
        if (!block) return;

        const loader = block.querySelector(".loader-small");
        if (loader) loader.remove();

        const header = block.querySelector(".tool-header");
        header.innerHTML = `
            <span style="color: ${success ? 'var(--accent-green)' : 'var(--accent-red)'}">
                ${success ? '✅ Success' : '❌ Failed'}: ${name}
            </span>
        `;

        const resultDiv = document.createElement("div");
        resultDiv.className = "tool-args";
        resultDiv.style.marginTop = "6px";
        resultDiv.style.borderTop = "1px solid var(--border-light)";
        resultDiv.style.paddingTop = "6px";
        resultDiv.style.maxHeight = "150px";
        resultDiv.style.overflowY = "auto";
        resultDiv.innerHTML = Utils.escapeHtml(output);

        block.appendChild(resultDiv);
    },

    /**
     * Log runtime activities to the right-side logger.
     */
    logActivity(type, text) {
        const logPanel = document.getElementById("agent-activity-log");
        const entry = document.createElement("div");
        entry.className = `log-entry ${type}`;
        entry.textContent = `[${Utils.formatTime()}] ${text}`;
        
        logPanel.appendChild(entry);
        logPanel.scrollTop = logPanel.scrollHeight;
    }
};
