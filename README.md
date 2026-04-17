# 🔍 Distributed Root Cause Investigator

**AI-Powered Real-Time Root Cause Analysis for Microservice Architectures**

An intelligent observability platform that combines deep learning, causal inference, and graph-based analysis to automatically detect anomalies, trace failure propagation, and pinpoint root causes across distributed systems — reducing Mean Time To Resolution (MTTR) from hours to seconds.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c?logo=pytorch&logoColor=white)
![React](https://img.shields.io/badge/React-18+-61dafb?logo=react&logoColor=black)
![Flask](https://img.shields.io/badge/Flask-3.0+-000?logo=flask&logoColor=white)
![D3.js](https://img.shields.io/badge/D3.js-7+-f9a03c?logo=d3.js&logoColor=white)

---

## 🧠 What It Does

Traditional monitoring tools alert you *that* something is wrong. This system tells you **why** — automatically.

Given an 11-node microservice topology (API Gateway, Auth, Payments, Orders, Search, etc.), the platform:

1. **Detects anomalies** in real-time using an LSTM Autoencoder trained on normal operating patterns
2. **Classifies log severity** using a custom Transformer encoder with multi-head self-attention
3. **Traces failure chains** through the dependency graph using PageRank-weighted propagation analysis
4. **Infers causal relationships** via cross-correlation lag analysis between service metrics
5. **Predicts upcoming failures** using linear regression trend extrapolation on metric trajectories
6. **Matches known patterns** from a failure knowledge base using TF-IDF similarity scoring
7. **Scores confidence & business impact** of every root cause hypothesis with a multi-signal fusion engine

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React + D3.js Frontend                │
│   Service Topology · Anomaly Timeline · Metric Charts    │
│   Root Cause Panel · Causal Graph · Predictive Engine    │
├─────────────────────────────────────────────────────────┤
│                     Flask REST API                       │
├──────────┬──────────┬──────────┬────────────────────────┤
│ Transformer│  LSTM    │  Graph   │   Intelligence        │
│ Log        │ Anomaly  │ Analyzer │   Engine              │
│ Embedder   │ Detector │ (PageRank│ • Causal Inference    │
│ (4-layer,  │ (Encoder-│  + BFS)  │ • Predictive Failure  │
│  8-head)   │ Decoder) │          │ • Pattern Memory      │
│            │          │          │ • Confidence Scoring   │
├──────────┴──────────┴──────────┴────────────────────────┤
│           Synthetic Telemetry Data Generator              │
│     4 Failure Scenarios · 11 Services · 600s Windows     │
└─────────────────────────────────────────────────────────┘
```

---

## 🤖 AI/ML Models (Built From Scratch in PyTorch)

| Model | Architecture | Purpose |
|-------|-------------|---------|
| **Log Embedder** | 4-layer Transformer Encoder, 8 attention heads, 128-dim embeddings | Pre-trained with Masked Language Modeling (MLM), fine-tuned for log severity classification |
| **Anomaly Detector** | 2-layer LSTM Autoencoder (64→32 bottleneck) | Learns normal metric patterns; flags high reconstruction error as anomalous (μ + 3σ threshold) |
| **Statistical Ensemble** | Z-Score + EWMA + IQR (weighted fusion) | Complements the LSTM with classical statistical methods for robust detection |
| **Causal Inference** | Cross-correlation with lag analysis | Determines temporal causal relationships between service metric time-series |
| **Predictive Engine** | Linear trend extrapolation with threshold projection | Forecasts when metrics will breach critical thresholds (5-minute horizon) |
| **Pattern Memory** | TF-IDF vectorization + cosine similarity | Matches current failure signatures against a curated knowledge base of known incidents |
| **Confidence Scorer** | Multi-signal weighted fusion (signal + causal + evidence + pattern) | Produces calibrated confidence scores and business impact assessments for root cause hypotheses |

---

## 🔥 Failure Scenarios

The system includes 4 pre-built chaos engineering scenarios:

| Scenario | Root Cause | Propagation Chain |
|----------|-----------|-------------------|
| **Memory Leak** | inventory-service | → inventory-db → order-service → notification-service → api-gateway |
| **DB Connection Exhaustion** | user-db | → auth-service → api-gateway |
| **Network Partition** | payment-gateway | → payment-service → order-service |
| **CPU Spike** | search-service | → cache-redis → api-gateway |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend Setup
```bash
cd backend
pip install -r requirements.txt

# Option 1: Full pipeline (generate data → train models → start server)
python run.py --mode demo

# Option 2: Start server only (if models are already trained)
python run.py --mode serve
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Access
- **Dashboard**: http://localhost:5173
- **API**: http://localhost:5000

---

## 📊 Dashboard Features

- **System Overview** — Real-time health status of all 11 microservices with CPU, memory, latency, and error rate metrics
- **Service Topology** — Interactive D3.js force-directed graph showing service dependencies and failure propagation
- **Anomaly Timeline** — Temporal heatmap showing anomaly intensity across all services
- **Root Cause Panel** — AI-generated failure chain with confidence scores and remediation suggestions
- **Causal Inference Graph** — Visual representation of statistically inferred causal relationships
- **Predictive Failure Engine** — Early warnings for services trending toward critical thresholds
- **Pattern Match Panel** — Historical incident matching from the knowledge base
- **Metric Charts** — Zoomable time-series charts for individual service metrics
- **Log Stream** — Real-time filtered log viewer with severity highlighting
- **Light/Dark Mode** — Full theme toggle support

---

## 🗂️ Project Structure

```
├── backend/
│   ├── api/server.py              # Flask REST API (14 endpoints)
│   ├── models/
│   │   ├── log_embedder.py        # Transformer encoder (from scratch)
│   │   ├── anomaly_detector.py    # LSTM Autoencoder (from scratch)
│   │   ├── causal_inference.py    # Cross-correlation causal engine
│   │   ├── predictive_engine.py   # Trend-based failure predictor
│   │   ├── pattern_memory.py      # TF-IDF pattern matcher
│   │   └── confidence_scorer.py   # Multi-signal confidence fusion
│   ├── data/
│   │   ├── synthetic_generator.py # Telemetry data generator
│   │   └── scenarios.py           # Failure scenario definitions
│   ├── graph/analyzer.py          # NetworkX graph analysis (PageRank, BFS)
│   ├── config.py                  # All hyperparameters
│   └── run.py                     # CLI entry point
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Main dashboard layout
│   │   └── components/            # React components (10+)
│   └── index.html                 # Tailwind CSS configuration
└── knowledge_base/                # Curated failure pattern library
```

---

## 💡 Key Technical Highlights

- **Zero external ML dependencies** — All neural networks (Transformer, LSTM) built from scratch using raw PyTorch `nn.Module`
- **Custom tokenizer** — BPE-style tokenizer trained on log corpora, no HuggingFace dependency
- **Multi-signal fusion** — Root cause scoring combines log analysis, metric anomalies, graph centrality, causal inference, and pattern matching
- **Real-time simulation** — Inject failures on-the-fly and watch the AI trace the propagation chain in seconds
- **Production-grade UI** — Glassmorphism dark mode dashboard with smooth animations, D3.js visualizations, and responsive design

---

## 📄 License

MIT

---

<p align="center">
  <b>Built for Hackathon 2026</b><br>
  <i>Transforming observability from reactive alerting to proactive intelligence.</i>
</p>
