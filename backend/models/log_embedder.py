"""
Custom Transformer Encoder for log embeddings — built entirely from scratch in PyTorch.

Architecture:
    Token Embedding + Sinusoidal Positional Encoding
    → N × (Multi-Head Self-Attention + FFN with LayerNorm)
    → [CLS] pooling → Classification Head

No pretrained weights. All components implemented manually.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


# ── Sinusoidal Positional Encoding ────────────────────────────────

class SinusoidalPositionalEncoding(nn.Module):
    """
    PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
    """

    def __init__(self, d_model, max_len=512, dropout=0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # [1, max_len, d_model]

        self.register_buffer("pe", pe)

    def forward(self, x):
        """x: [batch, seq_len, d_model]"""
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


# ── Scaled Dot-Product Attention ──────────────────────────────────

class ScaledDotProductAttention(nn.Module):
    """
    Attention(Q, K, V) = softmax(QK^T / √d_k) · V
    """

    def __init__(self, d_k):
        super().__init__()
        self.scale = math.sqrt(d_k)

    def forward(self, Q, K, V, mask=None):
        """
        Q: [batch, heads, seq_len, d_k]
        K: [batch, heads, seq_len, d_k]
        V: [batch, heads, seq_len, d_v]
        mask: [batch, 1, 1, seq_len] — padding mask
        """
        # Compute attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale  # [B, H, S, S]

        # Apply mask (set padded positions to -inf)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)

        # Softmax to get attention weights
        weights = F.softmax(scores, dim=-1)

        # Weighted sum of values
        output = torch.matmul(weights, V)  # [B, H, S, d_v]
        return output, weights


# ── Multi-Head Self-Attention ─────────────────────────────────────

class MultiHeadSelfAttention(nn.Module):
    """
    MultiHead(Q, K, V) = Concat(head_1, ..., head_h) · W_O
    where head_i = Attention(X · W_Q_i, X · W_K_i, X · W_V_i)
    """

    def __init__(self, d_model, num_heads):
        super().__init__()
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        # Linear projections for Q, K, V
        self.W_Q = nn.Linear(d_model, d_model)
        self.W_K = nn.Linear(d_model, d_model)
        self.W_V = nn.Linear(d_model, d_model)

        # Output projection
        self.W_O = nn.Linear(d_model, d_model)

        self.attention = ScaledDotProductAttention(self.d_k)

    def forward(self, x, mask=None):
        """
        x: [batch, seq_len, d_model]
        mask: [batch, seq_len] — attention mask (1=attend, 0=ignore)
        """
        batch_size, seq_len, _ = x.shape

        # Project to Q, K, V and reshape for multi-head
        Q = self.W_Q(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        K = self.W_K(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        V = self.W_V(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)

        # Reshape mask for broadcasting: [B, 1, 1, S]
        if mask is not None:
            mask = mask.unsqueeze(1).unsqueeze(2)

        # Apply attention
        attn_output, attn_weights = self.attention(Q, K, V, mask)

        # Concatenate heads and project
        attn_output = attn_output.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        output = self.W_O(attn_output)

        return output


# ── Feed-Forward Network ─────────────────────────────────────────

class FeedForwardNetwork(nn.Module):
    """
    FFN(x) = GELU(x · W_1 + b_1) · W_2 + b_2
    """

    def __init__(self, d_model, d_ff, dropout=0.1):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff)
        self.linear2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        return self.linear2(self.dropout(F.gelu(self.linear1(x))))


# ── Transformer Encoder Block ────────────────────────────────────

class TransformerEncoderBlock(nn.Module):
    """
    Single transformer encoder block:
        x → MultiHeadAttention → Add & LayerNorm → FFN → Add & LayerNorm
    """

    def __init__(self, d_model, num_heads, d_ff, dropout=0.1):
        super().__init__()
        self.attention = MultiHeadSelfAttention(d_model, num_heads)
        self.norm1 = nn.LayerNorm(d_model)
        self.ffn = FeedForwardNetwork(d_model, d_ff, dropout)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        # Self-attention + residual + norm
        attn_out = self.attention(x, mask)
        x = self.norm1(x + self.dropout1(attn_out))

        # FFN + residual + norm
        ffn_out = self.ffn(x)
        x = self.norm2(x + self.dropout2(ffn_out))

        return x


# ── Log Embedding Transformer ────────────────────────────────────

class LogEmbeddingTransformer(nn.Module):
    """
    Complete custom Transformer Encoder for log embeddings.

    Input:  Token IDs [batch, seq_len]
    Output: Log embeddings [batch, d_model] via [CLS] pooling
            OR classification logits [batch, num_classes]
    """

    def __init__(self, vocab_size=None, d_model=None, num_heads=None,
                 num_layers=None, d_ff=None, max_seq_len=None,
                 num_classes=None, dropout=None):
        super().__init__()

        self.vocab_size = vocab_size or config.VOCAB_SIZE
        self.d_model = d_model or config.EMBED_DIM
        self.num_heads = num_heads or config.NUM_HEADS
        self.num_layers = num_layers or config.NUM_ENCODER_LAYERS
        self.d_ff = d_ff or config.FFN_DIM
        self.max_seq_len = max_seq_len or config.MAX_SEQ_LENGTH
        self.num_classes = num_classes or config.NUM_LOG_CLASSES

        # Token embedding
        self.token_embedding = nn.Embedding(self.vocab_size, self.d_model, padding_idx=0)

        # Positional encoding
        self.pos_encoding = SinusoidalPositionalEncoding(self.d_model, self.max_seq_len, dropout or config.DROPOUT)

        # Transformer encoder blocks
        self.encoder_blocks = nn.ModuleList([
            TransformerEncoderBlock(self.d_model, self.num_heads, self.d_ff, dropout or config.DROPOUT)
            for _ in range(self.num_layers)
        ])

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(self.d_model, self.d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout or config.DROPOUT),
            nn.Linear(self.d_model // 2, self.num_classes),
        )

        # MLM head (for masked language modeling pretraining)
        self.mlm_head = nn.Linear(self.d_model, self.vocab_size)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Xavier uniform initialization for all linear layers."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0, std=0.02)
                if module.padding_idx is not None:
                    nn.init.zeros_(module.weight[module.padding_idx])

    def forward(self, input_ids, attention_mask=None, output_embeddings=False):
        """
        Args:
            input_ids: [batch, seq_len] — token IDs
            attention_mask: [batch, seq_len] — 1 for real tokens, 0 for padding
            output_embeddings: if True, return [CLS] embeddings instead of class logits

        Returns:
            If output_embeddings: [batch, d_model] — log embeddings
            Else: [batch, num_classes] — classification logits
        """
        # Token embeddings
        x = self.token_embedding(input_ids)  # [B, S, d_model]

        # Add positional encoding
        x = self.pos_encoding(x)

        # Pass through encoder blocks
        for block in self.encoder_blocks:
            x = block(x, attention_mask)

        if output_embeddings:
            # [CLS] token pooling (first token)
            return x[:, 0, :]  # [B, d_model]

        # Classification: pool [CLS] token then classify
        cls_output = x[:, 0, :]  # [B, d_model]
        logits = self.classifier(cls_output)  # [B, num_classes]
        return logits

    def forward_mlm(self, input_ids, attention_mask=None):
        """
        Forward pass for Masked Language Modeling.

        Returns:
            mlm_logits: [batch, seq_len, vocab_size]
        """
        x = self.token_embedding(input_ids)
        x = self.pos_encoding(x)

        for block in self.encoder_blocks:
            x = block(x, attention_mask)

        mlm_logits = self.mlm_head(x)  # [B, S, vocab_size]
        return mlm_logits

    def get_embedding(self, input_ids, attention_mask=None):
        """Get [CLS] embeddings for log messages."""
        return self.forward(input_ids, attention_mask, output_embeddings=True)

    def count_parameters(self):
        """Count total trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
