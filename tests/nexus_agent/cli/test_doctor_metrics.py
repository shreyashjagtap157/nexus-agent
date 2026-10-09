from nexus_agent.cli.doctor import HealthMetric


def test_health_metric_defaults_to_not_applicable():
    metric = HealthMetric(name="Custom check", value="unknown")
    assert metric.ok is None


def test_health_metric_success_factory_sets_instance_status():
    metric = HealthMetric.success("Python", "3.12")
    assert metric.status == "ok"
    assert metric.ok is True
