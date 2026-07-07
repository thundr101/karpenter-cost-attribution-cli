import os
import tempfile
from karpenter_cost_attribution.report import render_chart


def test_render_chart_creates_file():
    rows = [
        {"namespace": "team-a", "hourly_cost": 0.1, "monthly_estimate": 73.0},
        {"namespace": "team-b", "hourly_cost": 0.2, "monthly_estimate": 146.0},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        chart_path = os.path.join(tmpdir, "chart.png")
        assert not os.path.exists(chart_path)

        render_chart(rows, chart_path)

        assert os.path.exists(chart_path)
        assert os.path.getsize(chart_path) > 0


def test_render_chart_empty_rows_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        chart_path = os.path.join(tmpdir, "empty_chart.png")
        assert not os.path.exists(chart_path)

        render_chart([], chart_path)

        assert os.path.exists(chart_path)
        assert os.path.getsize(chart_path) > 0
