"""
Custom word-level tokenizer for log messages.
Built from scratch — no HuggingFace or external tokenizer libraries.
Handles log-specific patterns (IPs, timestamps, UUIDs, hex, numbers).
"""

import re
import json
import os
from collections import Counter

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


# ── Pattern Normalizers ───────────────────────────────────────────
# Replace common log patterns with special tokens before tokenization

PATTERN_REPLACEMENTS = [
    # IP addresses: 192.168.1.1 → [IP]
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP]"),
    # ISO timestamps: 2025-06-15T10:00:00 → [TIME]
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"), "[TIME]"),
    # UUIDs: 550e8400-e29b-... → [UUID]
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "[UUID]"),
    # Hex addresses/hashes: 0x7fff5fbff8c0 → [HEX]
    (re.compile(r"0x[0-9a-fA-F]{6,}"), "[HEX]"),
    # Short hex IDs: abc12def → [HEXID]
    (re.compile(r"\b[0-9a-f]{8,}\b"), "[HEXID]"),
    # Floating point numbers: 45.23 → [NUM]
    (re.compile(r"\b\d+\.\d+\b"), "[NUM]"),
    # Integer numbers: 12345 → [NUM]
    (re.compile(r"\b\d{2,}\b"), "[NUM]"),
    # Paths: /api/orders → [PATH]
    (re.compile(r"/[a-zA-Z0-9_/\-.]+"), "[PATH]"),
    # Email addresses
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
]


class LogTokenizer:
    """
    Custom word-level tokenizer for microservice log messages.

    Features:
    - Pattern normalization (IPs, times, UUIDs, etc.)
    - Word-level tokenization with configurable vocab size
    - Special tokens: [PAD], [UNK], [CLS], [SEP], [MASK]
    - Vocabulary built from corpus
    """

    def __init__(self, vocab_size=None, max_seq_length=None):
        self.vocab_size = vocab_size or config.VOCAB_SIZE
        self.max_seq_length = max_seq_length or config.MAX_SEQ_LENGTH

        # Special tokens
        self.special_tokens = {
            "[PAD]": 0,
            "[UNK]": 1,
            "[CLS]": 2,
            "[SEP]": 3,
            "[MASK]": 4,
            "[IP]": 5,
            "[TIME]": 6,
            "[UUID]": 7,
            "[HEX]": 8,
            "[HEXID]": 9,
            "[NUM]": 10,
            "[PATH]": 11,
            "[EMAIL]": 12,
        }

        self.word2idx = dict(self.special_tokens)
        self.idx2word = {v: k for k, v in self.word2idx.items()}
        self._fitted = False

    def _normalize(self, text):
        """Apply pattern replacements to normalize log text."""
        for pattern, replacement in PATTERN_REPLACEMENTS:
            text = pattern.sub(replacement, text)
        return text.lower().strip()

    def _tokenize_text(self, text):
        """Split normalized text into word tokens."""
        normalized = self._normalize(text)
        # Split on whitespace and punctuation (keep special tokens intact)
        tokens = re.findall(r"\[(?:PAD|UNK|CLS|SEP|MASK|IP|TIME|UUID|HEX|HEXID|NUM|PATH|EMAIL)\]|[a-z_]+|[^\s\w]", normalized)
        return tokens

    def fit(self, texts):
        """
        Build vocabulary from a corpus of log messages.

        Args:
            texts: list of log message strings
        """
        counter = Counter()
        for text in texts:
            tokens = self._tokenize_text(text)
            for token in tokens:
                if token not in self.special_tokens:
                    counter[token] += 1

        # Keep top vocab_size - num_special tokens
        num_special = len(self.special_tokens)
        most_common = counter.most_common(self.vocab_size - num_special)

        idx = num_special
        for word, count in most_common:
            if word not in self.word2idx:
                self.word2idx[word] = idx
                self.idx2word[idx] = word
                idx += 1

        self._fitted = True
        print(f"Tokenizer fitted: {len(self.word2idx)} tokens in vocabulary")

    def encode(self, text, add_special_tokens=True):
        """
        Encode a log message into token IDs.

        Args:
            text: log message string
            add_special_tokens: if True, prepend [CLS] and append [SEP]

        Returns:
            list of token IDs, padded/truncated to max_seq_length
        """
        tokens = self._tokenize_text(text)

        # Convert to IDs
        ids = []
        if add_special_tokens:
            ids.append(self.special_tokens["[CLS]"])

        for token in tokens:
            if token in self.word2idx:
                ids.append(self.word2idx[token])
            elif token in self.special_tokens:
                ids.append(self.special_tokens[token])
            else:
                ids.append(self.special_tokens["[UNK]"])

        if add_special_tokens:
            ids.append(self.special_tokens["[SEP]"])

        # Truncate
        if len(ids) > self.max_seq_length:
            ids = ids[:self.max_seq_length - 1] + [self.special_tokens["[SEP]"]]

        # Pad
        attention_mask = [1] * len(ids) + [0] * (self.max_seq_length - len(ids))
        ids = ids + [self.special_tokens["[PAD]"]] * (self.max_seq_length - len(ids))

        return ids, attention_mask[:self.max_seq_length]

    def decode(self, ids):
        """Decode token IDs back to text."""
        tokens = []
        for idx in ids:
            if idx in self.idx2word:
                word = self.idx2word[idx]
                if word not in ("[PAD]", "[CLS]", "[SEP]"):
                    tokens.append(word)
        return " ".join(tokens)

    def batch_encode(self, texts, add_special_tokens=True):
        """Encode a batch of texts."""
        all_ids = []
        all_masks = []
        for text in texts:
            ids, mask = self.encode(text, add_special_tokens)
            all_ids.append(ids)
            all_masks.append(mask)
        return all_ids, all_masks

    @property
    def vocab_count(self):
        return len(self.word2idx)

    def save(self, path):
        """Save tokenizer vocabulary to JSON."""
        data = {
            "vocab_size": self.vocab_size,
            "max_seq_length": self.max_seq_length,
            "word2idx": self.word2idx,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Tokenizer saved to {path}")

    def load(self, path):
        """Load tokenizer vocabulary from JSON."""
        with open(path, "r") as f:
            data = json.load(f)
        self.vocab_size = data["vocab_size"]
        self.max_seq_length = data["max_seq_length"]
        self.word2idx = data["word2idx"]
        # Convert string keys back to int for idx2word
        self.idx2word = {int(v) if isinstance(v, int) else v: k for k, v in self.word2idx.items()}
        self._fitted = True
        print(f"Tokenizer loaded: {len(self.word2idx)} tokens")
