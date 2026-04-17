"""
LSTM Autoencoder for time-series metric anomaly detection — built from scratch in PyTorch.

Architecture:
    Encoder: LSTM(5→64) → LSTM(64→32) → bottleneck (32-dim)
    Decoder: Repeat → LSTM(32→64) → LSTM(64→5) → Linear → reconstruction

Anomaly score = MSE(input, reconstruction)
Threshold = μ + kσ of training reconstruction errors

Also includes statistical ensemble methods: Z-Score, EWMA, IQR.
"""

import math
import numpy as np
import torch
import torch.nn as nn

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


# ── LSTM Autoencoder ──────────────────────────────────────────────

class LSTMEncoder(nn.Module):
    """
    Encoder: Two-layer LSTM that compresses a time-series window
    into a fixed-size bottleneck representation.
    """

    def __init__(self, input_dim, hidden1, hidden2):
        super().__init__()
        self.lstm1 = nn.LSTM(input_dim, hidden1, batch_first=True)
        self.lstm2 = nn.LSTM(hidden1, hidden2, batch_first=True)

    def forward(self, x):
        """
        x: [batch, seq_len, input_dim]
        Returns: bottleneck [batch, hidden2]
        """
        # First LSTM layer
        out1, (h1, c1) = self.lstm1(x)
        # Second LSTM layer
        out2, (h2, c2) = self.lstm2(out1)
        # Use last hidden state as bottleneck
        bottleneck = h2.squeeze(0)  # [batch, hidden2]
        return bottleneck


class LSTMDecoder(nn.Module):
    """
    Decoder: Expands bottleneck back to original sequence dimensions.
    RepeatVector → LSTM → LSTM → Linear
    """

    def __init__(self, bottleneck_dim, hidden1, output_dim, seq_len):
        super().__init__()
        self.seq_len = seq_len
        self.lstm1 = nn.LSTM(bottleneck_dim, hidden1, batch_first=True)
        self.lstm2 = nn.LSTM(hidden1, hidden1, batch_first=True)
        self.output_layer = nn.Linear(hidden1, output_dim)

    def forward(self, bottleneck):
        """
        bottleneck: [batch, bottleneck_dim]
        Returns: reconstruction [batch, seq_len, output_dim]
        """
        # Repeat vector across time dimension
        x = bottleneck.unsqueeze(1).repeat(1, self.seq_len, 1)  # [B, S, bottleneck]

        # Decode through LSTMs
        out1, _ = self.lstm1(x)
        out2, _ = self.lstm2(out1)

        # Project to output dimension
        output = self.output_layer(out2)  # [B, S, output_dim]
        return output


class LSTMAutoencoder(nn.Module):
    """
    Complete LSTM Autoencoder for time-series anomaly detection.

    Training: Learn to reconstruct normal operating metric windows.
    Inference: High reconstruction error → anomaly.

    Mathematical Framework:
        Anomaly Score = (1/TF) Σ_t Σ_f (x_{t,f} - x̂_{t,f})²
        Threshold θ = μ_train + k·σ_train
    """

    def __init__(self, input_dim=None, hidden1=None, hidden2=None, seq_len=None):
        super().__init__()

        self.input_dim = input_dim or config.METRIC_FEATURES
        self.hidden1 = hidden1 or config.LSTM_HIDDEN_1
        self.hidden2 = hidden2 or config.LSTM_HIDDEN_2
        self.seq_len = seq_len or config.METRIC_WINDOW_SIZE

        self.encoder = LSTMEncoder(self.input_dim, self.hidden1, self.hidden2)
        self.decoder = LSTMDecoder(self.hidden2, self.hidden1, self.input_dim, self.seq_len)

        # Threshold parameters (set during training)
        self.register_buffer("threshold_mean", torch.tensor(0.0))
        self.register_buffer("threshold_std", torch.tensor(1.0))
        self.threshold_k = config.ANOMALY_K

        self._init_weights()

    def _init_weights(self):
        """Initialize LSTM weights with Xavier uniform."""
        for name, param in self.named_parameters():
            if "weight_ih" in name:
                nn.init.xavier_uniform_(param)
            elif "weight_hh" in name:
                nn.init.orthogonal_(param)
            elif "bias" in name:
                nn.init.zeros_(param)

    def forward(self, x):
        """
        x: [batch, seq_len, input_dim]
        Returns: reconstruction [batch, seq_len, input_dim]
        """
        bottleneck = self.encoder(x)
        reconstruction = self.decoder(bottleneck)
        return reconstruction

    def compute_reconstruction_error(self, x):
        """
        Compute per-sample reconstruction error (MSE).

        x: [batch, seq_len, input_dim]
        Returns: errors [batch] — average MSE per sample
        """
        with torch.no_grad():
            reconstruction = self.forward(x)
            # MSE per sample: mean over time and features
            errors = ((x - reconstruction) ** 2).mean(dim=(1, 2))
        return errors

    def set_threshold(self, training_errors):
        """
        Set anomaly threshold from training reconstruction errors.
        θ = μ + k·σ
        """
        if isinstance(training_errors, np.ndarray):
            training_errors = torch.tensor(training_errors, dtype=torch.float32)

        self.threshold_mean = training_errors.mean()
        self.threshold_std = training_errors.std()
        threshold = self.threshold_mean + self.threshold_k * self.threshold_std
        print(f"Anomaly threshold set: mean={self.threshold_mean:.6f}, "
              f"std={self.threshold_std:.6f}, threshold={threshold:.6f}")

    def get_threshold(self):
        """Get the current anomaly threshold."""
        return (self.threshold_mean + self.threshold_k * self.threshold_std).item()

    def detect_anomalies(self, x):
        """
        Detect anomalies in metric windows.

        x: [batch, seq_len, input_dim]
        Returns: dict with anomaly_scores, is_anomaly, threshold
        """
        errors = self.compute_reconstruction_error(x)
        threshold = self.get_threshold()

        return {
            "anomaly_scores": errors.numpy(),
            "is_anomaly": (errors > threshold).numpy(),
            "threshold": threshold,
        }

    def count_parameters(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ── Statistical Anomaly Detection (Ensemble) ─────────────────────

class StatisticalAnomalyDetector:
    """
    Ensemble of statistical methods for anomaly detection.
    Does not require training — uses streaming statistics.

    Methods:
    1. Z-Score: (x - μ) / σ
    2. EWMA: Exponential Weighted Moving Average deviation
    3. IQR: Inter-Quartile Range method
    """

    def __init__(self, z_threshold=3.0, ewma_alpha=0.3, iqr_multiplier=1.5):
        self.z_threshold = z_threshold
        self.ewma_alpha = ewma_alpha
        self.iqr_multiplier = iqr_multiplier

    def z_score_detect(self, data):
        """
        Z-Score anomaly detection.
        data: np.array [T, features]
        Returns: anomaly_scores [T]
        """
        mean = data.mean(axis=0)
        std = data.std(axis=0)
        std[std < 1e-8] = 1.0
        z_scores = np.abs((data - mean) / std)
        # Max z-score across features for each timestep
        return z_scores.max(axis=1)

    def ewma_detect(self, data):
        """
        EWMA deviation detection.
        data: np.array [T, features]
        Returns: anomaly_scores [T]
        """
        T, F = data.shape
        ewma = np.zeros_like(data)
        ewma[0] = data[0]

        for t in range(1, T):
            ewma[t] = self.ewma_alpha * data[t] + (1 - self.ewma_alpha) * ewma[t - 1]

        deviations = np.abs(data - ewma)
        return deviations.max(axis=1)

    def iqr_detect(self, data):
        """
        Inter-Quartile Range anomaly detection.
        data: np.array [T, features]
        Returns: anomaly_scores [T]
        """
        Q1 = np.percentile(data, 25, axis=0)
        Q3 = np.percentile(data, 75, axis=0)
        IQR = Q3 - Q1
        IQR[IQR < 1e-8] = 1.0

        lower = Q1 - self.iqr_multiplier * IQR
        upper = Q3 + self.iqr_multiplier * IQR

        # Distance from bounds (0 if within, positive if outside)
        below = np.maximum(0, lower - data)
        above = np.maximum(0, data - upper)
        distances = np.maximum(below, above) / IQR
        return distances.max(axis=1)

    def ensemble_detect(self, data, weights=(0.4, 0.3, 0.3)):
        """
        Combined anomaly score from all methods.
        data: np.array [T, features]
        Returns: combined_scores [T], individual_scores dict
        """
        z_scores = self.z_score_detect(data)
        ewma_scores = self.ewma_detect(data)
        iqr_scores = self.iqr_detect(data)

        # Normalize each to [0, 1] range
        def _normalize(s):
            s_min, s_max = s.min(), s.max()
            if s_max - s_min < 1e-8:
                return np.zeros_like(s)
            return (s - s_min) / (s_max - s_min)

        z_norm = _normalize(z_scores)
        ewma_norm = _normalize(ewma_scores)
        iqr_norm = _normalize(iqr_scores)

        combined = (weights[0] * z_norm +
                    weights[1] * ewma_norm +
                    weights[2] * iqr_norm)

        return combined, {
            "z_score": z_scores,
            "ewma": ewma_scores,
            "iqr": iqr_scores,
        }
