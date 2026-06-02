/**
 * NexusAgent — Frontend Utility functions
 */

const Utils = {
    /**
     * Escape raw HTML to prevent injection issues.
     */
    escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    /**
     * Parse very simple Markdown bold, inline code, and blocks.
     */
    parseSimpleMarkdown(text) {
        if (!text) return "";
        let html = this.escapeHtml(text);

        // Code blocks: ```python ... ```
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre><code class="language-${lang || 'txt'}">${code.trim()}</code></pre>`;
        });

        // Inline code: `code`
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold: **bold**
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Newlines to line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    },

    /**
     * Format timestamp.
     */
    formatTime(date = new Date()) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
};
