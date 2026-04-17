"""
Entry point for the Distributed Root Cause Investigator.

Usage:
    python run.py --mode generate    # Generate synthetic data
    python run.py --mode train       # Train all models
    python run.py --mode serve       # Start API server
    python run.py --mode demo        # Generate + Train + Serve (full pipeline)
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config


def generate_data(scenario="memory_leak"):
    """Generate synthetic dataset."""
    from data.synthetic_generator import generate_dataset, save_dataset

    print("=" * 60)
    print("  Generating Synthetic Data")
    print("=" * 60)

    dataset = generate_dataset(scenario_id=scenario, duration=config.SYNTHETIC_DURATION_SECONDS)
    save_dataset(dataset)
    return dataset


def train_models():
    """Train all ML models."""
    print("=" * 60)
    print("  Training Models")
    print("=" * 60)

    start = time.time()

    # Train log embedder
    print("\n[1/2] Training Log Embedding Transformer...")
    from training.train_embedder import run_training as train_embedder
    embedder, tokenizer = train_embedder()

    # Train anomaly detector
    print("\n[2/2] Training LSTM Autoencoder...")
    from training.train_anomaly import run_training as train_anomaly
    detector, stats = train_anomaly()

    elapsed = time.time() - start
    print(f"\nAll models trained in {elapsed:.1f}s")
    print(f"Saved to: {config.MODEL_DIR}")


def serve():
    """Start the Flask API server."""
    print("=" * 60)
    print("  Starting API Server")
    print("=" * 60)

    from api.server import create_app
    app = create_app()

    print(f"\n  API:       http://localhost:{config.API_PORT}")
    print(f"  Dashboard: http://localhost:5173")
    print(f"  Models:    {'Loaded' if app.state['models_loaded'] else 'Not trained (run --mode train first)'}")
    print()

    app.run(host=config.API_HOST, port=config.API_PORT, debug=False)


def demo():
    """Full demo pipeline: generate → train → serve."""
    print("=" * 60)
    print("  Distributed Root Cause Investigator — Full Demo")
    print("=" * 60)
    print()

    # Step 1: Generate Data
    generate_data()

    # Step 2: Train Models
    train_models()

    # Step 3: Start Server
    serve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Distributed Root Cause Investigator (Chef)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run.py --mode generate                   # Generate synthetic data
    python run.py --mode train                      # Train all models
    python run.py --mode serve                      # Start API server only
    python run.py --mode demo                       # Full pipeline
    python run.py --mode generate --scenario cpu_spike  # Generate specific scenario
        """
    )
    parser.add_argument("--mode", type=str, default="demo",
                        choices=["generate", "train", "serve", "demo"],
                        help="Execution mode")
    parser.add_argument("--scenario", type=str, default="memory_leak",
                        choices=["memory_leak", "db_connection_exhaustion", "network_partition", "cpu_spike"],
                        help="Failure scenario for data generation")

    args = parser.parse_args()

    if args.mode == "generate":
        generate_data(args.scenario)
    elif args.mode == "train":
        train_models()
    elif args.mode == "serve":
        serve()
    elif args.mode == "demo":
        demo()
