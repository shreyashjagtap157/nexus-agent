"""Recurrent-Depth Transformer (RDT) with dynamic confidence halting.

Implements a transformer with recurrent depth blocks that can dynamically
halt computation at each layer using Adaptive Computation Time (ACT).
"""

from __future__ import annotations

import math
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F


class RecurrentBlock(nn.Module):
    """Single recurrent transformer block with multi-head attention.

    Args:
        d_model: Model dimension.
        n_heads: Number of attention heads.
        d_ff: Feed-forward dimension (default 4 * d_model).
        dropout: Dropout rate.
        max_recurrent_steps: Maximum number of recurrent iterations.
    """

    def __init__(
        self,
        d_model: int = 768,
        n_heads: int = 12,
        d_ff: int | None = None,
        dropout: float = 0.1,
        max_recurrent_steps: int = 8,
    ):
        super().__init__()
        d_ff = d_ff or 4 * d_model
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.max_recurrent_steps = max_recurrent_steps

        # Multi-head attention
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)

        # Feed-forward
        self.ff_up = nn.Linear(d_model, d_ff)
        self.ff_down = nn.Linear(d_ff, d_model)

        # Layer norms
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # Dropout
        self.dropout = nn.Dropout(dropout)

        # Halting mechanism
        self.halt_gate = nn.Linear(d_model, 1)

    def forward(
        self,
        x: torch.Tensor,
        mask: torch.Tensor | None = None,
        return_attention: bool = False,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Forward pass with optional attention output.

        Args:
            x: Input tensor [batch, seq_len, d_model].
            mask: Attention mask [batch, seq_len].
            return_attention: Whether to return attention weights.

        Returns:
            Tuple of (output tensor, info dict with halt probabilities and attention).
        """
        batch, seq_len, _ = x.shape
        info: dict[str, Any] = {}

        # Multi-head attention
        residual = x
        x = self.norm1(x)

        q = self.q_proj(x).view(batch, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(batch, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(batch, seq_len, self.n_heads, self.head_dim).transpose(1, 2)

        attn = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        if mask is not None:
            mask_expanded = mask.unsqueeze(1).unsqueeze(2)
            attn = attn.masked_fill(~mask_expanded, float("-inf"))

        attn_weights = F.softmax(attn, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_out = torch.matmul(attn_weights, v)
        attn_out = attn_out.transpose(1, 2).contiguous().view(batch, seq_len, self.d_model)
        attn_out = self.out_proj(attn_out)
        x = residual + self.dropout(attn_out)

        # Feed-forward
        residual = x
        x = self.norm2(x)
        x = self.ff_up(x)
        x = F.gelu(x)
        x = self.ff_down(x)
        x = residual + self.dropout(x)

        # Compute halt probability
        halt_prob = torch.sigmoid(self.halt_gate(x.mean(dim=1)))

        info["halt_prob"] = halt_prob
        if return_attention:
            info["attention"] = attn_weights

        return x, info


class RecurrentDepthTransformer(nn.Module):
    """Recurrent-Depth Transformer with dynamic confidence halting.

    Uses ACT (Adaptive Computation Time) to dynamically halt computation
    at each layer based on confidence.

    Args:
        vocab_size: Vocabulary size.
        d_model: Model dimension.
        n_heads: Number of attention heads.
        n_layers: Number of recurrent blocks.
        d_ff: Feed-forward dimension.
        max_seq_length: Maximum sequence length.
        dropout: Dropout rate.
        max_recurrent_steps: Maximum recurrent iterations per block.
        halt_threshold: Confidence threshold for halting.
    """

    def __init__(
        self,
        vocab_size: int = 32000,
        d_model: int = 768,
        n_heads: int = 12,
        n_layers: int = 6,
        d_ff: int | None = None,
        max_seq_length: int = 2048,
        dropout: float = 0.1,
        max_recurrent_steps: int = 8,
        halt_threshold: float = 0.95,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.n_layers = n_layers
        self.max_recurrent_steps = max_recurrent_steps
        self.halt_threshold = halt_threshold

        # Token embedding
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        self.position_embedding = nn.Embedding(max_seq_length, d_model)
        self.embedding_dropout = nn.Dropout(dropout)

        # Recurrent blocks (shared weights for depth recurrence)
        self.recurrent_block = RecurrentBlock(
            d_model=d_model,
            n_heads=n_heads,
            d_ff=d_ff,
            dropout=dropout,
            max_recurrent_steps=max_recurrent_steps,
        )

        # Layer norm
        self.final_norm = nn.LayerNorm(d_model)

        # Output head
        self.output_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying
        self.output_head.weight = self.token_embedding.weight

        # Initialize weights
        self._init_weights()

    def _init_weights(self) -> None:
        """Initialize weights with scaled normal distribution."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
            elif isinstance(module, nn.LayerNorm):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        return_hidden_states: bool = False,
    ) -> dict[str, Any]:
        """Forward pass with dynamic halting.

        Args:
            input_ids: Token IDs [batch, seq_len].
            attention_mask: Attention mask [batch, seq_len].
            return_hidden_states: Whether to return intermediate hidden states.

        Returns:
            Dict with logits, loss (if targets provided), hidden states, and halt info.
        """
        batch, seq_len = input_ids.shape
        device = input_ids.device

        # Clamp input_ids to vocab size
        input_ids = input_ids.clamp(0, self.vocab_size - 1)

        # Embeddings
        positions = torch.arange(seq_len, device=device).unsqueeze(0).expand(batch, -1)
        x = self.token_embedding(input_ids) + self.position_embedding(positions)
        x = self.embedding_dropout(x)

        # Track halting across recurrent steps
        cumulative_halt = torch.zeros(batch, 1, device=device)
        hidden_states = [] if return_hidden_states else None
        all_halt_probs = []
        final_output = x

        # Recurrent depth with ACT halting
        for step in range(self.max_recurrent_steps):
            # Check if all sequences have halted
            if cumulative_halt.min() > self.halt_threshold:
                break

            # Forward through recurrent block
            block_output, info = self.recurrent_block(x, mask=attention_mask)

            # Get halt probability for this step
            halt_prob = info["halt_prob"]  # [batch, 1]
            all_halt_probs.append(halt_prob)

            # ACT halting: compute remainders
            remainders = 1.0 - cumulative_halt
            should_halt = halt_prob * remainders
            cumulative_halt = cumulative_halt + should_halt

            # Weighted accumulation
            x = x + should_halt.unsqueeze(1) * (block_output - x)

            if return_hidden_states:
                hidden_states.append(x.detach())

            final_output = x

        # Final norm and output
        final_output = self.final_norm(final_output)
        logits = self.output_head(final_output)

        result: dict[str, Any] = {
            "logits": logits,
            "hidden_states": hidden_states,
            "halt_probs": all_halt_probs,
            "cumulative_halt": cumulative_halt,
            "num_steps": len(all_halt_probs),
        }

        return result

    def get_embeddings(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Get embeddings without output head (for SAE)."""
        result = self.forward(input_ids, attention_mask, return_hidden_states=True)
        # Return last hidden state
        return result["hidden_states"][-1] if result["hidden_states"] else result["logits"]
