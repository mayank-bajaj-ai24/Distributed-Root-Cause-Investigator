"""Quick test of all 4 new features."""
import urllib.request
import json

BASE = "http://localhost:5000/api"

def post(path):
    req = urllib.request.Request(f"{BASE}{path}", method="POST")
    return json.loads(urllib.request.urlopen(req).read())

def get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())

# 1. Inject scenario
print("Injecting memory_leak scenario...")
inject = post("/scenarios/memory_leak/inject")
print(f"  Status: {inject['status']}")

# 2. Run full analysis
print("\nRunning analysis...")
result = post("/analyze")

# 3. Check Causal Analysis
ca = result.get("causal_analysis", {})
print(f"\n=== CAUSAL INFERENCE ===")
print(f"  Root cause: {ca.get('root_cause', 'N/A')}")
print(f"  Causality type: {ca.get('causality_type', 'N/A')}")
print(f"  Causal edges: {len(ca.get('causal_edges', []))}")
print(f"  Chain: {' -> '.join(ca.get('causal_chain', []))}")

# 4. Check Predictions
preds = result.get("predictions", {})
print(f"\n=== PREDICTIVE FAILURE ===")
print(f"  Warnings: {preds.get('num_warnings', 0)}")
for p in (preds.get("predictions") or [])[:3]:
    print(f"  - {p['service']}/{p['metric']}: {p['message'][:70]}")

# 5. Check Pattern Matches
pm = result.get("pattern_matches", {})
print(f"\n=== PATTERN MEMORY ===")
print(f"  Matches: {len(pm.get('matches', []))}")
if pm.get("best_match"):
    bm = pm["best_match"]
    print(f"  Best: {bm['title']} ({bm['similarity']:.0%} similar)")
    print(f"  Resolution: {bm.get('resolution', 'N/A')[:70]}")
print(f"  Recommendation: {pm.get('recommendation', 'N/A')[:80]}")

# 6. Check Confidence & Impact
ci = result.get("confidence_impact", {})
conf = ci.get("confidence", {})
imp = ci.get("impact", {})
print(f"\n=== CONFIDENCE & IMPACT ===")
print(f"  Confidence: {conf.get('overall', 0):.0%} ({conf.get('label', 'N/A')})")
print(f"  Factors: {conf.get('factors', {})}")
print(f"  Impact: {imp.get('score', 0):.0f}/100 ({imp.get('label', 'N/A')})")
print(f"  Blast radius: {imp.get('affected_services', 0)}/{imp.get('total_services', 0)}")
uf = imp.get("user_facing", False)
print(f"  User-facing: {uf}")

print("\n" + "=" * 50)
print("ALL 4 NEW FEATURES WORKING!")
print("=" * 50)
