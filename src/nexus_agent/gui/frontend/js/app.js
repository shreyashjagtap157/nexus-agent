/**
 * NexusAgent — Main Frontend Application Orchestrator
 */

const App = {
    activeSessionId: null,
    activeMode: "auto",

    /**
     * Start the application and setup event listeners.
     */
    async bootstrap() {
        console.log("Bootstrapping NexusAgent Web Workspace...");
        
        // Initialize default preferences
        Settings.loadSettings();

        // Bind all UI event listeners
        this.bindEvents();

        // Sync local stats and check preloaded models
        await this.syncStatus();

        // Load sessions list
        await this.loadSessions();

        // Create or resume chat
        this.initializeSession();
    },

    /**
     * Bind click events and tab keys.
     */
    bindEvents() {
        // Model modal actions
        document.getElementById("btn-change-model").onclick = () => Models.showModal();
        const loadFirstBtn = document.getElementById("btn-load-first-model");
        if (loadFirstBtn) {
            loadFirstBtn.onclick = () => Models.showModal();
        }
        document.getElementById("btn-close-model-modal").onclick = () => Models.hideModal();

        // Settings modal actions
        document.getElementById("btn-settings-trigger").onclick = () => Settings.showModal();
        document.getElementById("btn-close-settings-modal").onclick = () => Settings.hideModal();

        // New session action
        document.getElementById("btn-new-session").onclick = () => this.createNewSession();

        // Mode selectors
        const modeTabs = document.querySelectorAll(".mode-tab");
        modeTabs.forEach(tab => {
            tab.onclick = (e) => {
                modeTabs.forEach(t => t.classList.remove("active"));
                e.target.classList.add("active");
                this.activeMode = e.target.dataset.mode;
                Chat.logActivity("system", `[SYSTEM] Switched agent execution mode to: ${this.activeMode.toUpperCase()}`);
            };
        });

        // Prompt input submissions
        const promptInput = document.getElementById("prompt-textarea");
        const sendBtn = document.getElementById("btn-send-prompt");

        // Submit prompt on Enter (Shift+Enter for newline)
        promptInput.onkeydown = (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                const text = promptInput.value.trim();
                if (text && !promptInput.disabled) {
                    Chat.sendMessage(text, this.activeMode);
                }
            }
        };

        sendBtn.onclick = () => {
            const text = promptInput.value.trim();
            if (text && !promptInput.disabled) {
                Chat.sendMessage(text, this.activeMode);
            }
        };
    },

    /**
     * Fetch status from server and update system info.
     */
    async syncStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();

            // Active model tag
            const activeModel = document.getElementById("active-model-display");
            const textSpan = activeModel.querySelector(".model-text");
            const indicator = activeModel.querySelector(".indicator");

            if (data.model_loaded) {
                textSpan.textContent = data.model_name;
                const isOnnx = data.model_name.toLowerCase().includes("onnx") || data.runtime.toLowerCase().includes("onnx");
                indicator.className = isOnnx ? "indicator green-glow" : "indicator blue-glow";
            } else {
                textSpan.textContent = "No local LLM loaded";
                indicator.className = "indicator red-glow";
            }

            // Workspace path
            document.getElementById("workspace-path-display").textContent = data.workspace;

            // Update specs
            const hw = data.hardware;
            document.getElementById("hw-platform").textContent = hw.platform || "-";
            document.getElementById("hw-cpu").textContent = hw.cpu || "-";
            document.getElementById("hw-ram").textContent = `${hw.ram_available || '-'} / ${hw.ram_total || '-'}`;
            document.getElementById("hw-gpu").textContent = hw.gpu || "Not detected";
            document.getElementById("hw-npu").textContent = hw.npu || "None detected";
            
            // Format labels for layer offloads
            const offloads = document.getElementById("active-gpu-layers");
            if (data.model_loaded) {
                offloads.textContent = data.gpu_backend !== "cpu" ? "Accelerated GPU" : "CPU fallback";
            } else {
                offloads.textContent = "-";
            }

        } catch (e) {
            console.error("Failed to sync status: ", e);
        }
    },

    /**
     * Load list of sessions.
     */
    async loadSessions() {
        const sessionContainer = document.getElementById("session-history-list");
        sessionContainer.innerHTML = "";

        try {
            const res = await fetch("/api/sessions");
            const sessions = await res.json();

            if (!sessions || sessions.length === 0) {
                sessionContainer.innerHTML = '<li class="session-item" style="color: var(--text-muted); pointer-events: none;">No sessions yet</li>';
                return;
            }

            sessions.forEach(s => {
                const li = document.createElement("li");
                li.className = `session-item ${s.id === this.activeSessionId ? 'active' : ''}`;
                li.onclick = () => this.resumeSession(s.id);

                li.innerHTML = `
                    <div class="session-title">${Utils.escapeHtml(s.title || 'Conversation')}</div>
                    <div class="session-meta">${s.message_count} msgs</div>
                `;
                sessionContainer.appendChild(li);
            });
        } catch (e) {
            console.error("Failed to load sessions: ", e);
        }
    },

    /**
     * Initialize Websocket chat session.
     */
    async initializeSession() {
        try {
            const res = await fetch("/api/sessions");
            const sessions = await res.json();

            if (sessions && sessions.length > 0) {
                // Resume latest session
                this.resumeSession(sessions[0].id);
            } else {
                // Create new
                this.createNewSession();
            }
        } catch (e) {
            this.createNewSession();
        }
    },

    /**
     * Resume a conversation session.
     */
    async resumeSession(sessionId) {
        this.activeSessionId = sessionId;
        console.log(`Resuming session: ${sessionId}`);
        
        // Update session list focus
        const listItems = document.querySelectorAll(".session-item");
        listItems.forEach(item => item.classList.remove("active"));
        
        // Connect WS
        Chat.connect(sessionId);

        // Fetch history
        const msgContainer = document.getElementById("chat-messages-container");
        msgContainer.innerHTML = '<div class="loader-small"></div>';

        try {
            const res = await fetch(`/api/sessions/${sessionId}`);
            const data = await res.json();

            msgContainer.innerHTML = "";
            const messages = data.messages || [];

            if (messages.length === 0) {
                msgContainer.innerHTML = `
                    <div class="welcome-card-container">
                        <div class="welcome-card glassmorphism">
                            <h2>NexusAgent Ready</h2>
                            <p class="tagline">Load a local model and input code changes or queries below.</p>
                        </div>
                    </div>
                `;
            } else {
                messages.forEach(msg => {
                    // Skip system prompts to keep the dashboard clean
                    if (msg.role !== "system") {
                        Chat.appendMessage(msg.role, msg.content);
                    }
                });
            }
            this.loadSessions();
        } catch (e) {
            console.error("Failed to fetch session history: ", e);
            msgContainer.innerHTML = `<p style="color: var(--accent-red); text-align: center;">Failed to load session history</p>`;
        }
    },

    /**
     * Create a new session via POST.
     */
    async createNewSession() {
        try {
            const res = await fetch("/api/sessions/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: "New Conversation" })
            });
            const data = await res.json();
            
            this.resumeSession(data.session_id);
        } catch (e) {
            console.error("Failed to create session: ", e);
        }
    }
};

// Bootstrap the app on load
window.onload = () => App.bootstrap();
