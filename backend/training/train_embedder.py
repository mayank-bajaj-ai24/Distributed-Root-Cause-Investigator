"""
Training script for the Log Embedding Transformer.

Phase 1: Masked Language Modeling (self-supervised)
Phase 2: Log Classification (supervised)
"""

import os
import sys
import json
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from models.tokenizer import LogTokenizer
from models.log_embedder import LogEmbeddingTransformer
from data.synthetic_generator import generate_dataset
from data.preprocessor import label_logs_for_training


# ── Datasets ──────────────────────────────────────────────────────

class LogMLMDataset(Dataset):
    """Dataset for Masked Language Modeling pretraining."""

    def __init__(self, token_ids, attention_masks, mask_ratio=0.15, vocab_size=2000):
        self.token_ids = torch.tensor(token_ids, dtype=torch.long)
        self.attention_masks = torch.tensor(attention_masks, dtype=torch.long)
        self.mask_ratio = mask_ratio
        self.vocab_size = vocab_size
        self.mask_token_id = 4  # [MASK]
        self.pad_token_id = 0   # [PAD]

    def __len__(self):
        return len(self.token_ids)

    def __getitem__(self, idx):
        input_ids = self.token_ids[idx].clone()
        labels = self.token_ids[idx].clone()
        mask = self.attention_masks[idx]

        # Create MLM masks: 15% of non-special tokens
        mlm_mask = torch.zeros_like(input_ids, dtype=torch.bool)

        for i in range(len(input_ids)):
            if mask[i] == 1 and input_ids[i] > 4:  # skip special tokens
                if random.random() < self.mask_ratio:
                    mlm_mask[i] = True
                    r = random.random()
                    if r < 0.8:
                        input_ids[i] = self.mask_token_id  # 80% → [MASK]
                    elif r < 0.9:
                        input_ids[i] = random.randint(5, self.vocab_size - 1)  # 10% → random
                    # 10% → keep original

        # Labels: -100 for non-masked positions (ignored in loss)
        labels[~mlm_mask] = -100

        return input_ids, mask, labels


class LogClassificationDataset(Dataset):
    """Dataset for supervised log classification."""

    def __init__(self, token_ids, attention_masks, labels):
        self.token_ids = torch.tensor(token_ids, dtype=torch.long)
        self.attention_masks = torch.tensor(attention_masks, dtype=torch.long)
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.token_ids)

    def __getitem__(self, idx):
        return self.token_ids[idx], self.attention_masks[idx], self.labels[idx]


# ── Training Functions ────────────────────────────────────────────

def train_mlm(model, dataloader, epochs, lr, device):
    """
    Phase 1: Masked Language Modeling.
    Self-supervised pretraining to learn contextual log representations.
    """
    model.train()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)

    # Warmup scheduler
    total_steps = len(dataloader) * epochs
    warmup_steps = total_steps // 10

    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(warmup_steps, 1)
        return max(0.1, 1.0 - (step - warmup_steps) / (total_steps - warmup_steps))

    scheduler = optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    criterion = nn.CrossEntropyLoss(ignore_index=-100)

    print(f"\n{'='*60}")
    print(f"Phase 1: Masked Language Modeling — {epochs} epochs")
    print(f"{'='*60}")

    for epoch in range(epochs):
        total_loss = 0
        correct = 0
        total_masked = 0

        for batch_idx, (input_ids, attention_mask, labels) in enumerate(dataloader):
            input_ids = input_ids.to(device)
            attention_mask = attention_mask.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()

            # Forward pass through MLM head
            logits = model.forward_mlm(input_ids, attention_mask)
            logits = logits.view(-1, logits.size(-1))
            labels_flat = labels.view(-1)

            loss = criterion(logits, labels_flat)
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()
            scheduler.step()

            total_loss += loss.item()

            # Accuracy on masked tokens
            mask_positions = labels_flat != -100
            if mask_positions.any():
                predictions = logits[mask_positions].argmax(dim=-1)
                correct += (predictions == labels_flat[mask_positions]).sum().item()
                total_masked += mask_positions.sum().item()

        avg_loss = total_loss / len(dataloader)
        accuracy = correct / max(total_masked, 1)
        print(f"  Epoch {epoch+1:3d}/{epochs} — Loss: {avg_loss:.4f} — MLM Accuracy: {accuracy:.2%}")

    return model


def train_classifier(model, dataloader, epochs, lr, device):
    """
    Phase 2: Supervised log classification.
    Fine-tune on labeled log categories: normal, warning, error, anomaly.
    """
    model.train()
    optimizer = optim.AdamW(model.parameters(), lr=lr * 0.1, weight_decay=0.01)  # lower lr for fine-tuning
    criterion = nn.CrossEntropyLoss()

    print(f"\n{'='*60}")
    print(f"Phase 2: Log Classification — {epochs} epochs")
    print(f"{'='*60}")

    for epoch in range(epochs):
        total_loss = 0
        correct = 0
        total = 0

        for input_ids, attention_mask, labels in dataloader:
            input_ids = input_ids.to(device)
            attention_mask = attention_mask.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()

            logits = model(input_ids, attention_mask)
            loss = criterion(logits, labels)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()

            total_loss += loss.item()
            predictions = logits.argmax(dim=-1)
            correct += (predictions == labels).sum().item()
            total += labels.size(0)

        avg_loss = total_loss / len(dataloader)
        accuracy = correct / max(total, 1)
        print(f"  Epoch {epoch+1:3d}/{epochs} — Loss: {avg_loss:.4f} — Accuracy: {accuracy:.2%}")

    return model


# ── Main Training Pipeline ───────────────────────────────────────

def run_training():
    """Execute the full embedding model training pipeline."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training device: {device}")

    # ── Step 1: Generate training data ────────────────────────────
    print("\n[1/5] Generating synthetic training data...")

    # Generate data with different scenarios for diversity
    all_logs = []
    all_scenario_infos = []
    for scenario_id in ["memory_leak", "db_connection_exhaustion", "network_partition", "cpu_spike"]:
        ds = generate_dataset(scenario_id=scenario_id, duration=300, seed=hash(scenario_id) % 10000)
        all_logs.extend(ds["logs"])
        all_scenario_infos.append(ds.get("scenario_info"))

    # Also generate normal data
    ds_normal = generate_dataset(scenario_id=None, duration=100, seed=99)
    all_logs.extend(ds_normal["logs"])

    print(f"  Total logs: {len(all_logs)}")

    # ── Step 2: Build tokenizer ───────────────────────────────────
    print("\n[2/5] Building tokenizer...")
    tokenizer = LogTokenizer()
    texts = [log["message"] for log in all_logs]
    tokenizer.fit(texts)

    tokenizer_path = os.path.join(config.MODEL_DIR, "tokenizer.json")
    tokenizer.save(tokenizer_path)

    # ── Step 3: Tokenize all logs ─────────────────────────────────
    print("\n[3/5] Tokenizing logs...")
    token_ids, attention_masks = tokenizer.batch_encode(texts)
    print(f"  Tokenized {len(token_ids)} log messages")

    # ── Step 4: Phase 1 — MLM Pretraining ─────────────────────────
    print("\n[4/5] Phase 1: Masked Language Modeling...")

    mlm_dataset = LogMLMDataset(
        token_ids, attention_masks,
        mask_ratio=config.MASK_RATIO,
        vocab_size=tokenizer.vocab_count,
    )
    mlm_loader = DataLoader(mlm_dataset, batch_size=config.EMBEDDER_BATCH_SIZE, shuffle=True)

    model = LogEmbeddingTransformer(vocab_size=tokenizer.vocab_count).to(device)
    print(f"  Model parameters: {model.count_parameters():,}")

    model = train_mlm(model, mlm_loader, config.EMBEDDER_EPOCHS_MLM, config.EMBEDDER_LR, device)

    # ── Step 5: Phase 2 — Classification Fine-tuning ──────────────
    print("\n[5/5] Phase 2: Classification fine-tuning...")

    # Label logs
    labeled = label_logs_for_training(all_logs)
    labels = [l["label"] for l in labeled]

    cls_dataset = LogClassificationDataset(token_ids, attention_masks, labels)
    cls_loader = DataLoader(cls_dataset, batch_size=config.EMBEDDER_BATCH_SIZE, shuffle=True)

    model = train_classifier(model, cls_loader, config.EMBEDDER_EPOCHS_CLS, config.EMBEDDER_LR, device)

    # Save model
    model_path = os.path.join(config.MODEL_DIR, "log_embedder.pt")
    torch.save(model.state_dict(), model_path)
    print(f"\nModel saved to {model_path}")

    # Label distribution
    from collections import Counter
    dist = Counter(labels)
    class_names = ["normal", "warning", "error", "anomaly"]
    print("\nLabel distribution:")
    for cls_id, name in enumerate(class_names):
        print(f"  {name}: {dist.get(cls_id, 0)}")

    return model, tokenizer


if __name__ == "__main__":
    run_training()
