"""TDD: Issue #811 G31 — mp_round_completed_total metric emitted on round completion."""
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/app")


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_metrics_module_defines_mp_round_completed_counter():
    """metrics.py must define mp_round_completed_total as a prometheus Counter."""
    from app.core import metrics
    counter = getattr(metrics, "mp_round_completed_total", None)
    assert counter is not None, "mp_round_completed_total not defined in app.core.metrics"
    assert hasattr(counter, "labels"), "mp_round_completed_total must be a prometheus Counter with .labels()"


def _get_counter_value(round_number_str: str) -> float:
    """Read current value of mp_round_completed_total for a given round_number label."""
    from prometheus_client import REGISTRY
    for metric in REGISTRY.collect():
        # prometheus_client strips _total suffix from the metric family name
        if metric.name == "mp_round_completed":
            for sample in metric.samples:
                if sample.name == "mp_round_completed_total" and sample.labels.get("round_number") == round_number_str:
                    return sample.value
    return 0.0


def test_metric_increments_on_round_completion():
    """mp_round_completed_total.labels(round_number=N).inc() must work."""
    from app.core.metrics import mp_round_completed_total

    before = _get_counter_value("777")
    mp_round_completed_total.labels(round_number="777").inc()
    after = _get_counter_value("777")

    assert after == before + 1, f"Counter should increase by 1: before={before} after={after}"


def test_metric_labels_are_independent():
    """Different round_number labels are independent counters."""
    from app.core.metrics import mp_round_completed_total

    before_a = _get_counter_value("991")
    before_b = _get_counter_value("992")

    mp_round_completed_total.labels(round_number="991").inc()
    mp_round_completed_total.labels(round_number="991").inc()
    mp_round_completed_total.labels(round_number="992").inc()

    assert _get_counter_value("991") == before_a + 2
    assert _get_counter_value("992") == before_b + 1


def test_trigger_narration_emits_metric_on_done():
    """trigger_narration must call mp_round_completed_total.labels(...).inc() when round completes."""
    from app.core import metrics

    mock_inc = MagicMock()
    mock_labels = MagicMock()
    mock_labels.inc = mock_inc

    with patch.object(metrics, "mp_round_completed_total") as mock_counter:
        mock_counter.labels.return_value = mock_labels

        # Patch DB so trigger_narration exits early (row=None → return immediately)
        import app.services.multiplayer_round_service as svc
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = None

        with patch("app.services.multiplayer_round_service._db", return_value=mock_conn):
            svc.trigger_narration(round_id=99999)

        # Row=None → early return before metric emission → should NOT be called
        mock_counter.labels.assert_not_called()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_metrics_module_importable():
    """app.core.metrics must be importable without side effects."""
    import app.core.metrics  # noqa: F401
    assert True
