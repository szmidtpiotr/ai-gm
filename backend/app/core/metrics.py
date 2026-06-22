"""Domain Prometheus metrics for AI-GM.

Import this module to register metrics; use labels() to emit.
The default prometheus_client REGISTRY is shared with prometheus_fastapi_instrumentator.
"""
from prometheus_client import Counter

# G31 #811 — round-to-round retention: how many campaigns complete each round.
# Emit once per round completion in multiplayer_round_service.trigger_narration.
# Query pattern: rate(mp_round_completed_total{round_number="5"}[7d]) / rate(mp_round_completed_total{round_number="1"}[7d])
mp_round_completed_total = Counter(
    "mp_round_completed_total",
    "Total MP rounds completed, labelled by round number",
    ["round_number"],
)
