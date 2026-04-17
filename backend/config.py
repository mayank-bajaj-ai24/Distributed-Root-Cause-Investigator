"""
System configuration for Distributed Root Cause Investigator (Chef).
All hyperparameters, paths, and constants defined here.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "generated_data")
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")

# ── Microservice Topology ──────────────────────────────────────────
SERVICES = [
    "api-gateway",
    "auth-service",
    "user-db",
    "order-service",
    "inventory-service",
    "inventory-db",
    "payment-service",
    "payment-gateway",
    "notification-service",
    "search-service",
    "cache-redis",
]

DEPENDENCIES = {
    "api-gateway": ["auth-service", "order-service", "search-service"],
    "auth-service": ["user-db"],
    "order-service": ["inventory-service", "payment-service", "notification-service"],
    "inventory-service": ["inventory-db"],
    "payment-service": ["payment-gateway"],
    "search-service": ["cache-redis"],
}

# ── Synthetic Data Generation ──────────────────────────────────────
SYNTHETIC_DURATION_SECONDS = 600       # 10 minutes of simulated data
METRIC_INTERVAL_SECONDS = 1            # 1-second granularity
NUM_LOG_TEMPLATES = 50                 # Templates per service

# ── Tokenizer Config ──────────────────────────────────────────────
VOCAB_SIZE = 2000
MAX_SEQ_LENGTH = 128
SPECIAL_TOKENS = {"[PAD]": 0, "[UNK]": 1, "[CLS]": 2, "[SEP]": 3}

# ── Log Embedding Transformer ────────────────────────────────────
EMBED_DIM = 128          # d_model
NUM_HEADS = 8            # attention heads
NUM_ENCODER_LAYERS = 4   # transformer blocks
FFN_DIM = 512            # feed-forward hidden dim
DROPOUT = 0.1
NUM_LOG_CLASSES = 4      # normal, warning, error, anomaly
MASK_RATIO = 0.15        # MLM masking ratio

# ── LSTM Autoencoder ──────────────────────────────────────────────
METRIC_FEATURES = 5              # CPU, memory, latency, error_rate, connections
METRIC_WINDOW_SIZE = 60          # 60-second sliding window
LSTM_HIDDEN_1 = 64
LSTM_HIDDEN_2 = 32
ANOMALY_K = 3                    # μ + kσ threshold

# ── Graph Analyzer ────────────────────────────────────────────────
PAGERANK_DAMPING = 0.85
RCA_ALPHA = 0.35                 # PageRank weight
RCA_BETA = 0.35                  # Upstream ratio weight
RCA_GAMMA = 0.30                 # Temporal priority weight

# ── Root Cause Engine ─────────────────────────────────────────────
FUSION_WEIGHT_LOG = 0.3
FUSION_WEIGHT_METRIC = 0.4
FUSION_WEIGHT_GRAPH = 0.3

# ── Training ──────────────────────────────────────────────────
EMBEDDER_LR = 3e-4
EMBEDDER_EPOCHS_MLM = 5         # reduced from 30 for fast CPU training
EMBEDDER_EPOCHS_CLS = 5         # reduced from 20 for fast CPU training
EMBEDDER_BATCH_SIZE = 128        # larger batches = fewer steps

ANOMALY_LR = 1e-3
ANOMALY_EPOCHS = 10              # reduced from 50 for fast CPU training
ANOMALY_BATCH_SIZE = 64          # larger batches = fewer steps

# ── Flask API ─────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 5000
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]

# ── Causal Inference Engine ──────────────────────────────────
CAUSAL_DEPENDENCY_PRIOR_WEIGHT = 0.3   # weight for dependency graph prior
CAUSAL_MIN_CORRELATION = 0.3           # minimum cross-correlation threshold
CAUSAL_MAX_LAG = 60                    # maximum lag in seconds to test

# ── Predictive Failure Engine ────────────────────────────────
PREDICTION_TREND_WINDOW = 120          # seconds of history for trend analysis
PREDICTION_HORIZON = 300               # predict up to 5 minutes ahead
PREDICTION_MIN_SLOPE = 0.01            # minimum slope to consider a trend

# ── Failure Pattern Memory ───────────────────────────────────
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "knowledge_base")
PATTERN_MATCH_THRESHOLD = 0.25        # minimum similarity to report a match

# ── Confidence & Impact Scoring ──────────────────────────────
CONFIDENCE_W_SIGNAL = 0.30             # signal agreement weight
CONFIDENCE_W_CAUSAL = 0.25             # causal confirmation weight
CONFIDENCE_W_EVIDENCE = 0.25           # evidence depth weight
CONFIDENCE_W_PATTERN = 0.20            # pattern match weight

# ── Ensure directories exist ──────────────────────────────────────
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
