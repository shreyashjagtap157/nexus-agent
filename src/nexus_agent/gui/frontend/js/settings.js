/**
 * NexusAgent — Settings controller for sandboxing and worktree features.
 */

const Settings = {
    modalId: "settings-modal",

    /**
     * Show settings modal.
     */
    showModal() {
        const modal = document.getElementById(this.modalId);
        modal.classList.add("active");
        this.loadSettings();
    },

    /**
     * Hide settings modal.
     */
    hideModal() {
        const modal = document.getElementById(this.modalId);
        modal.classList.remove("active");
        this.saveSettings();
    },

    /**
     * Load settings from localStorage.
     */
    loadSettings() {
        const worktreeMode = localStorage.getItem("setting-worktree-mode") === "true";
        const autoSandbox = localStorage.getItem("setting-auto-sandbox") !== "false"; // Default to true

        document.getElementById("setting-worktree-mode").checked = worktreeMode;
        document.getElementById("setting-auto-sandbox").checked = autoSandbox;
    },

    /**
     * Save settings to localStorage.
     */
    saveSettings() {
        const worktreeMode = document.getElementById("setting-worktree-mode").checked;
        const autoSandbox = document.getElementById("setting-auto-sandbox").checked;

        localStorage.setItem("setting-worktree-mode", worktreeMode);
        localStorage.setItem("setting-auto-sandbox", autoSandbox);

        Chat.logActivity("system", `[SETTINGS] Saved preferences. Worktree mode: ${worktreeMode ? 'ON' : 'OFF'}, Shell Sandbox checks: ${autoSandbox ? 'ON' : 'OFF'}`);
    }
};
