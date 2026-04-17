"""
Training script for the LSTM Autoencoder anomaly detector.

Trains on normal operating metric windows,
then sets anomaly threshold from training reconstruction errors.
"""

import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from models.anomaly_detector import LSTMAutoencoder
from data.synthetic_generator import generate_dataset
from data.preprocessor import normalize_metrics, create_sliding_windows


class MetricWindowDataset(Dataset):
    """Dataset of metric time-series windows."""

    def __init__(self, windows):
        # windows: np.array [N, window_size, features]
        self.windows = torch.tensor(windows, dtype=torch.float32)

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        return self.windows[idx]


def train_autoencoder(model, dataloader, epochs, lr, device):
    """Train the LSTM Autoencoder to reconstruct normal metric windows."""
    model.train()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    print(f"\n{'='*60}")
    print(f"LSTM Autoencoder Training — {epochs} epochs")
    print(f"{'='*60}")

    best_loss = float("inf")

    for epoch in range(epochs):
        total_loss = 0

        for batch in dataloader:
            batch = batch.to(device)

            optimizer.zero_grad()
            reconstruction = model(batch)
            loss = criterion(reconstruction, batch)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(dataloader)

        if avg_loss < best_loss:
            best_loss = avg_loss

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}/{epochs} — Loss: {avg_loss:.6f} (best: {best_loss:.6f})")

    return model


def compute_threshold(model, dataloader, device):
    """
    Compute anomaly threshold from training data reconstruction errors.
    θ = μ + k·σ
    """
    model.eval()
    all_errors = []

    with torch.no_grad():
        for batch in dataloader:
            batch = batch.to(device)
            errors = model.compute_reconstruction_error(batch)
            all_errors.append(errors.cpu().numpy())

    all_errors = np.concatenate(all_errors)
    model.set_threshold(all_errors)

    return all_errors


def run_training():
    """Execute the full anomaly detector training pipeline."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training device: {device}")

    # ── Step 1: Generate normal operating data ────────────────────
    print("\n[1/4] Generating normal operating data...")
    ds_normal = generate_dataset(scenario_id=None, duration=600, seed=99)
    print(f"  Generated {ds_normal['duration_seconds']}s of data for {ds_normal['num_services']} services")

    # ── Step 2: Preprocess metrics ────────────────────────────────
    print("\n[2/4] Preprocessing metrics...")
    normalized, stats = normalize_metrics(ds_normal["metrics"])

    # Create sliding windows for all services
    all_windows = []
    for service, data in normalized.items():
        windows = create_sliding_windows(data, stride=5)  # stride=5 to reduce data size
        all_windows.append(windows)
        print(f"  {service}: {len(windows)} windows")

    all_windows = np.concatenate(all_windows, axis=0)
    print(f"  Total windows: {all_windows.shape}")

    # Shuffle
    np.random.shuffle(all_windows)

    # ── Step 3: Train autoencoder ─────────────────────────────────
    print("\n[3/4] Training autoencoder...")
    dataset = MetricWindowDataset(all_windows)
    dataloader = DataLoader(dataset, batch_size=config.ANOMALY_BATCH_SIZE, shuffle=True)

    model = LSTMAutoencoder().to(device)
    print(f"  Model parameters: {model.count_parameters():,}")

    model = train_autoencoder(model, dataloader, config.ANOMALY_EPOCHS, config.ANOMALY_LR, device)

    # ── Step 4: Compute threshold ─────────────────────────────────
    print("\n[4/4] Computing anomaly threshold...")
    errors = compute_threshold(model, dataloader, device)
    print(f"  Training error stats: mean={errors.mean():.6f}, std={errors.std():.6f}")
    print(f"  Threshold (mean+{config.ANOMALY_K}*std): {model.get_threshold():.6f}")

    # Save model and stats
    model_path = os.path.join(config.MODEL_DIR, "anomaly_detector.pt")
    torch.save({
        "model_state_dict": model.state_dict(),
        "threshold_mean": model.threshold_mean.item(),
        "threshold_std": model.threshold_std.item(),
        "normalization_stats": stats,
    }, model_path)
    print(f"\nModel saved to {model_path}")

    return model, stats


if __name__ == "__main__":
    run_training()
