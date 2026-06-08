//! Streaming Render Pipeline — Stage 1: Block Detector.
//!
//! Accumulates tokens into semantic content blocks. Each block is classified
//! by type (prose, code, tool_call, tool_result, thinking, warning, error)
//! for distinct visual treatment in the compositor.

use std::time::Instant;

// ── Content Block Types ────────────────────────────────────────────────

/// Classified content type for visual treatment.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BlockType {
    /// Plain prose / natural language response.
    Prose,
    /// Code block with optional language tag.
    Code { language: Option<String> },
    /// Inline code (single backtick) — rendered inline, not a separate block.
    InlineCode,
    /// Tool call invocation.
    ToolCall,
    /// Tool execution result.
    ToolResult,
    /// Agent's internal thinking/reasoning.
    Thinking,
    /// Model/context switch notification.
    ModelSwitch,
    /// Warning message.
    Warning,
    /// Error message.
    Error,
    /// File write event with diff content.
    FileDiff,
    /// Memory access event.
    MemoryAccess,
    /// Plan step progress.
    PlanStep,
    /// Generic system message.
    System,
}

/// A parsed content block with metadata.
#[derive(Debug, Clone)]
pub struct ContentBlock {
    /// Classification.
    pub block_type: BlockType,
    /// Raw text content.
    pub content: String,
    /// Optional language tag (for code blocks).
    pub language: Option<String>,
    /// When this block started accumulating.
    pub started_at: Instant,
    /// Whether this block has been fully accumulated.
    pub complete: bool,
    /// Number of lines in the block.
    pub line_count: usize,
}

impl ContentBlock {
    pub fn new(block_type: BlockType) -> Self {
        Self {
            block_type,
            content: String::new(),
            language: None,
            started_at: Instant::now(),
            complete: false,
            line_count: 0,
        }
    }

    /// Push a character into this block.
    pub fn push(&mut self, ch: char) {
        if ch == '\n' {
            self.line_count += 1;
        }
        self.content.push(ch);
    }

    /// Push a string slice into this block.
    pub fn push_str(&mut self, s: &str) {
        self.line_count += s.chars().filter(|&c| c == '\n').count();
        self.content.push_str(s);
    }
}

// ── Block Detector ─────────────────────────────────────────────────────

/// Streaming block detector — accumulates token characters and classifies
/// them into semantic content blocks.
///
/// State machine that tracks:
/// - Whether we're inside a code fence (```)
/// - Whether we're inside inline code (`)
/// - Current block type being accumulated
pub struct BlockDetector {
    /// Completed blocks ready for rendering.
    pub blocks: Vec<ContentBlock>,
    /// Current block being accumulated.
    current: ContentBlock,
    /// Buffer for state machine pattern matching.
    buf: String,
    /// Are we inside a triple-backtick code fence?
    in_code_fence: bool,
    /// Language tag captured after opening fence.
    fence_language: Option<String>,
    /// Are we inside single backtick inline code?
    in_inline_code: bool,
    /// Fence delimiter length (3 or more backticks).
    fence_delim_len: usize,
}

impl BlockDetector {
    pub fn new() -> Self {
        Self {
            blocks: Vec::new(),
            current: ContentBlock::new(BlockType::Prose),
            buf: String::with_capacity(256),
            in_code_fence: false,
            fence_language: None,
            in_inline_code: false,
            fence_delim_len: 0,
        }
    }

    /// Feed a character into the detector. Returns true if a block was completed.
    pub fn feed(&mut self, ch: char) -> bool {
        // Track the raw buffer for pattern matching (last 4 chars of current block)
        self.buf.push(ch);
        if self.buf.len() > 8 {
            self.buf.remove(0);
        }

        if self.in_code_fence {
            // Inside a code block — check for closing fence
            let buf_str = &self.buf;
            let backtick_run = buf_str.chars().rev().take_while(|&c| c == '`').count();
            if backtick_run >= self.fence_delim_len && backtick_run >= 3 && ch == '\n' {
                // Closing fence found (backtick run at end of line)
                // Strip the closing fence from content
                let total = self.current.content.len();
                let strip = backtick_run.min(self.fence_delim_len) + 1;
                if total >= strip {
                    self.current.content.truncate(total - strip);
                    self.current.content = self.current.content.trim_end().to_string();
                }
                self.in_code_fence = false;
                self.current.complete = true;
                self.blocks.push(std::mem::replace(
                    &mut self.current,
                    ContentBlock::new(BlockType::Prose),
                ));
                self.buf.clear();
                return true;
            }
            self.current.push(ch);
            return false;
        }

        // Check for opening code fence: ``` at start of line
        if ch == '`' && !self.in_inline_code {
            let backtick_count = self.buf.chars().filter(|&c| c == '`').count();
            if backtick_count >= 3 && self.current.content.trim().is_empty() || self.current.content.ends_with('\n') {
                // Only trigger at line start (after newline or empty)
                if self.current.content.is_empty() || self.current.content.ends_with('\n') {
                    // Start code fence
                    self.fence_delim_len = backtick_count.min(6);
                    self.in_code_fence = true;

                    // Complete the current prose block
                    if !self.current.content.trim().is_empty() {
                        self.current.complete = true;
                        self.blocks.push(std::mem::replace(
                            &mut self.current,
                            ContentBlock::new(BlockType::Prose),
                        ));
                    }

                    // Capture language tag: read ahead from buf
                    let full_so_far = &self.buf;
                    let lang = full_so_far
                        .trim_start_matches(['`', '\n'])
                        .trim()
                        .to_string();
                    let lang = if lang.is_empty() || lang.contains('`') { None } else { Some(lang) };

                    // Start a new code block
                    self.current = ContentBlock::new(BlockType::Code { language: lang.clone() });
                    self.current.language = lang;
                    self.fence_language = None;
                    self.buf.clear();
                    return false;
                }
            }
        }

        // Check for inline code: single backtick
        if ch == '`' && !self.in_code_fence {
            self.in_inline_code = !self.in_inline_code;
            self.current.push(ch);
            return false;
        }

        self.current.push(ch);
        false
    }

    /// Flush the current block (mark as complete and add to blocks list).
    pub fn flush(&mut self) {
        if !self.current.content.is_empty() {
            self.current.complete = true;
            let content = std::mem::take(&mut self.current.content);
            let mut block = ContentBlock::new(BlockType::Prose);
            block.content = content;
            block.complete = true;
            self.blocks.push(block);
        }
    }

    /// Classify a complete message string into a single block.
    /// Used for non-streaming rendering (batch mode).
    pub fn classify(message: &str) -> ContentBlock {
        let trimmed = message.trim();
        if trimmed.starts_with("⚙") || trimmed.starts_with("[tool]") {
            ContentBlock::new(BlockType::ToolCall)
        } else if trimmed.starts_with("◦") || trimmed.starts_with("[thinking]") {
            ContentBlock::new(BlockType::Thinking)
        } else if trimmed.starts_with("✗") || trimmed.starts_with("[error]") {
            ContentBlock::new(BlockType::Error)
        } else if trimmed.starts_with("⚠") || trimmed.starts_with("[warning]") {
            ContentBlock::new(BlockType::Warning)
        } else if trimmed.starts_with("✓") || trimmed.starts_with("[result]") {
            ContentBlock::new(BlockType::ToolResult)
        } else if trimmed.contains("```") {
            ContentBlock::new(BlockType::Code { language: None })
        } else {
            ContentBlock::new(BlockType::Prose)
        }
    }

    /// Get all completed blocks and reset.
    pub fn drain_blocks(&mut self) -> Vec<ContentBlock> {
        let mut result = Vec::new();
        std::mem::swap(&mut result, &mut self.blocks);
        result
    }
}

impl Default for BlockDetector {
    fn default() -> Self { Self::new() }
}
