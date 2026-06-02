/**
 * NexusAgent — Models Controller for loading/switching local models.
 */

const Models = {
    modalId: "model-loader-modal",

    /**
     * Show model switching modal and fetch discovered local models.
     */
    showModal() {
        const modal = document.getElementById(this.modalId);
        modal.classList.add("active");
        this.fetchModels();
    },

    /**
     * Hide model switching modal.
     */
    hideModal() {
        const modal = document.getElementById(this.modalId);
        modal.classList.remove("active");
    },

    /**
     * Fetch discovered GGUF and ONNX models from /api/models.
     */
    async fetchModels() {
        const listContainer = document.getElementById("discovered-models-list");
        listContainer.innerHTML = '<div class="loader-small"></div>';

        try {
            const res = await fetch("/api/models");
            const models = await res.json();

            if (!models || models.length === 0) {
                listContainer.innerHTML = `
                    <div style="text-align: center; padding: 20px; color: var(--text-muted);">
                        <p>No GGUF or ONNX models found.</p>
                        <p style="font-size: 0.8rem; margin-top: 8px;">Place model folders or GGUF files in your configured ~/models directory.</p>
                    </div>
                `;
                return;
            }

            listContainer.innerHTML = "";
            models.forEach(model => {
                const card = document.createElement("div");
                card.className = "model-grid-card";
                card.onclick = () => this.loadModel(model.path);

                const formatLabel = model.format === "onnx" ? "ONNX/NPU" : "GGUF/llama.cpp";
                const formatColor = model.format === "onnx" ? "var(--accent-green)" : "var(--accent-blue)";

                card.innerHTML = `
                    <div class="model-grid-details">
                        <h4>${Utils.escapeHtml(model.name)}</h4>
                        <div class="model-grid-meta">
                            <span style="color: ${formatColor}; font-weight: 600;">${formatLabel}</span>
                            <span>Quant: ${Utils.escapeHtml(model.quantization)}</span>
                            <span>Size: ${model.size_str}</span>
                        </div>
                    </div>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                `;
                listContainer.appendChild(card);
            });
        } catch (e) {
            console.error("Failed to load models: ", e);
            listContainer.innerHTML = `<p style="color: var(--accent-red); text-align: center;">Failed to discover local models: ${e.message}</p>`;
        }
    },

    /**
     * Load a model via POST /api/models/load.
     */
    async loadModel(modelPath) {
        this.hideModal();
        Chat.logActivity("system", `[SYSTEM] Preparing to load model at: ${modelPath}...`);
        
        // Show streaming bubble loading status
        Chat.appendMessage("system", `⚙️ Loading local model: ${modelPath.split(/[\\/]/).pop()}... Please wait.`);

        try {
            const res = await fetch("/api/models/load", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_path: modelPath })
            });
            const data = await res.json();

            if (data.success) {
                Chat.logActivity("success", `[SYSTEM] Loaded successfully!`);
                Chat.appendMessage("system", `✅ Model loaded successfully: **${data.model_name}**! You can now start coding offline.`);
                
                // Sync status elements
                App.syncStatus();
            } else {
                throw new Error(data.detail || "Unknown error");
            }
        } catch (e) {
            console.error("Failed to load model: ", e);
            Chat.logActivity("error", `[SYSTEM ERROR] Failed to load model: ${e.message}`);
            Chat.appendMessage("system", `❌ Model load failed: ${e.message}`);
            App.syncStatus();
        }
    }
};
