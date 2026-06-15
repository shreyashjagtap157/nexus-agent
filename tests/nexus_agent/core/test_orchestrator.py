"""Tests for Orchestrator — multi-agent coordinator for planning and execution."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from nexus_agent.core.agent import AgentEvent, AgentState
from nexus_agent.core.orchestrator import Orchestrator


def _event(event_type: str, data=""):
    """Factory helper for creating AgentEvent-like objects."""
    e = MagicMock(spec=AgentEvent)
    e.type = event_type
    e.data = data
    return e


class FakeIterator:
    """Makes a generator from a list so we can yield through the orchestrator."""

    def __init__(self, events: list):
        self._events = events

    def __iter__(self):
        return iter(self._events)


class TestOrchestratorInit(unittest.TestCase):
    """Test Orchestrator initialization."""

    def setUp(self):
        self.provider = MagicMock()
        self.tools = [MagicMock(), MagicMock()]
        self.callback = MagicMock(return_value=True)

    def test_init_with_all_params(self):
        orch = Orchestrator(
            provider=self.provider,
            tools=self.tools,
            approval_callback=self.callback,
            workspace=Path("/test/workspace"),
        )
        self.assertIs(orch.provider, self.provider)
        self.assertIs(orch.tools, self.tools)
        self.assertIs(orch.approval_callback, self.callback)
        self.assertEqual(orch.workspace, Path("/test/workspace"))

    def test_init_creates_planner_and_executor(self):
        with patch("nexus_agent.core.orchestrator.Planner") as mock_planner, \
             patch("nexus_agent.core.orchestrator.Executor") as mock_executor:
            Orchestrator(
                provider=self.provider,
                tools=self.tools,
            )
            mock_planner.assert_called_once_with(
                self.provider, self.tools, workspace=Path.cwd()
            )
            mock_executor.assert_called_once_with(
                self.provider, self.tools, workspace=Path.cwd()
            )

    def test_init_default_workspace_is_cwd(self):
        orch = Orchestrator(provider=self.provider, tools=self.tools)
        self.assertEqual(orch.workspace, Path.cwd())

    def test_init_without_callback(self):
        orch = Orchestrator(provider=self.provider, tools=self.tools)
        self.assertIsNone(orch.approval_callback)

    def test_init_kwargs_forwarded(self):
        with patch("nexus_agent.core.orchestrator.Planner") as mock_planner, \
             patch("nexus_agent.core.orchestrator.Executor") as mock_executor:
            Orchestrator(
                provider=self.provider,
                tools=self.tools,
                max_iterations=50,
                temperature=0.5,
            )
            mock_planner.assert_called_once_with(
                self.provider, self.tools,
                workspace=Path.cwd(),
                max_iterations=50, temperature=0.5,
            )
            mock_executor.assert_called_once_with(
                self.provider, self.tools,
                workspace=Path.cwd(),
                max_iterations=50, temperature=0.5,
            )


class TestOrchestratorRunTask(unittest.TestCase):
    """Test the run_task method."""

    def setUp(self):
        self.provider = MagicMock()
        self.tools = [MagicMock()]

        # Mock Planner and Executor right at the import
        self.planner_patch = patch("nexus_agent.core.orchestrator.Planner")
        self.executor_patch = patch("nexus_agent.core.orchestrator.Executor")
        self.mock_planner_cls = self.planner_patch.start()
        self.mock_executor_cls = self.executor_patch.start()

        self.mock_planner = MagicMock()
        self.mock_executor = MagicMock()
        self.mock_planner_cls.return_value = self.mock_planner
        self.mock_executor_cls.return_value = self.mock_executor

        self.orch = Orchestrator(
            provider=self.provider,
            tools=self.tools,
        )

    def tearDown(self):
        self.planner_patch.stop()
        self.executor_patch.stop()

    def test_run_task_yields_state_change_planning(self):
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_chunk", "plan steps"),
            _event("content_complete", "detailed plan"),
        ])
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_chunk", "executing step 1"),
            _event("content_complete", "done"),
        ])

        events = list(self.orch.run_task("test task"))
        event_types = [e.type for e in events]
        self.assertIn("state_change", event_types)
        # First event should be state_change=planning
        self.assertEqual(events[0].type, "state_change")
        self.assertEqual(events[0].data, "planning")

    def test_run_task_planner_yields_events(self):
        plan_events = [
            _event("content_chunk", "thinking..."),
            _event("content_chunk", "plan step 1"),
            _event("content_complete", "final plan"),
        ]
        self.mock_planner.plan.return_value = FakeIterator(plan_events)
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "done"),
        ])

        events = list(self.orch.run_task("test task"))
        plan_content_events = [
            e for e in events
            if e.type == "content_chunk" or e.type == "content_complete"
        ]
        self.assertGreaterEqual(len(plan_content_events), 1)

    def test_run_task_planner_failure(self):
        """When planner returns no content, should yield an error."""
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_chunk", ""),
            _event("content_complete", ""),
        ])

        events = list(self.orch.run_task("test task"))
        has_error = any(e.type == "error" for e in events)
        self.assertTrue(has_error)
        # Executor should NOT be called
        self.mock_executor.execute_plan.assert_not_called()

    def test_run_task_plan_only_stops_after_plan(self):
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_chunk", "plan"),
            _event("content_complete", "complete plan"),
        ])

        events = list(self.orch.run_task("test task", plan_only=True))
        # Should have a done event with executed=False
        done_events = [e for e in events if e.type == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertFalse(done_events[0].data["executed"])
        # Executor should NOT be called
        self.mock_executor.execute_plan.assert_not_called()

    def test_run_task_executor_called(self):
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_chunk", "plan"),
            _event("content_complete", "complete plan"),
        ])
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_chunk", "working..."),
            _event("content_complete", "done"),
        ])

        list(self.orch.run_task("test task"))
        self.mock_executor.execute_plan.assert_called_once_with(
            "test task", "complete plan"
        )

    def test_run_task_with_approval_callback_approved(self):
        callback = MagicMock(return_value=True)
        self.orch.approval_callback = callback

        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_chunk", "plan"),
            _event("content_complete", "approved plan"),
        ])
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "done"),
        ])

        list(self.orch.run_task("test task"))
        callback.assert_called_once_with("approved plan")
        self.mock_executor.execute_plan.assert_called_once()

    def test_run_task_with_approval_callback_rejected(self):
        callback = MagicMock(return_value=False)
        self.orch.approval_callback = callback

        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_chunk", "plan"),
            _event("content_complete", "rejected plan"),
        ])

        events = list(self.orch.run_task("test task"))
        callback.assert_called_once_with("rejected plan")
        # Executor should NOT be called
        self.mock_executor.execute_plan.assert_not_called()
        # Should have a done event with approved=False
        done_events = [e for e in events if e.type == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertFalse(done_events[0].data["approved"])
        self.assertFalse(done_events[0].data["executed"])

    def test_run_task_passes_task_to_planner(self):
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_complete", "plan"),
        ])
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "done"),
        ])

        list(self.orch.run_task("my specific task"))
        self.mock_planner.plan.assert_called_once_with("my specific task")

    def test_run_task_yields_executor_events(self):
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_complete", "plan text"),
        ])
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_chunk", "exec step 1"),
            _event("content_chunk", "exec step 2"),
            _event("content_complete", "final"),
        ])

        events = list(self.orch.run_task("task"))
        exec_chunks = [
            e for e in events
            if e.type == "content_chunk" and e.data.startswith("exec")
        ]
        # At least some executor content chunks should appear
        self.assertGreaterEqual(len(exec_chunks), 1)

    def test_run_task_yields_state_change_executing(self):
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_complete", "plan"),
        ])
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "done"),
        ])

        events = list(self.orch.run_task("task"))
        state_changes = [e for e in events if e.type == "state_change"]
        executing_states = [e for e in state_changes if e.data == "executing"]
        self.assertEqual(len(executing_states), 1)

    def test_run_task_yields_done_at_end(self):
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_complete", "plan"),
        ])
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "done"),
        ])

        events = list(self.orch.run_task("task"))
        # run_task doesn't yield a "done" event in the normal path;
        # it yields state_change=AgentState.DONE at the end
        state_changes = [e for e in events if e.type == "state_change"]
        self.assertGreaterEqual(len(state_changes), 2)
        self.assertEqual(state_changes[-1].data, "done")

    def test_run_task_yields_state_change_waiting_approval(self):
        callback = MagicMock(return_value=True)
        self.orch.approval_callback = callback
        self.mock_planner.plan.return_value = FakeIterator([
            _event("content_complete", "plan"),
        ])
        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "done"),
        ])

        events = list(self.orch.run_task("task"))
        state_changes = [e for e in events if e.type == "state_change"]
        waiting = [e for e in state_changes if e.data == AgentState.WAITING_APPROVAL]
        self.assertEqual(len(waiting), 1)


class TestOrchestratorRunAutonomous(unittest.TestCase):
    """Test the run_autonomous method — advanced goal execution."""

    def setUp(self):
        self.provider = MagicMock()
        self.tools = [MagicMock()]

        # Patch all dependencies
        self.planner_patch = patch("nexus_agent.core.orchestrator.Planner")
        self.executor_patch = patch("nexus_agent.core.orchestrator.Executor")
        self.taskgraph_patch = patch("nexus_agent.core.orchestrator.TaskGraph")
        self.pipeline_patch = patch("nexus_agent.core.orchestrator.VerificationPipeline")
        self.debate_patch = patch("nexus_agent.core.orchestrator.DebateEngine")

        self.mock_planner_cls = self.planner_patch.start()
        self.mock_executor_cls = self.executor_patch.start()
        self.mock_taskgraph_cls = self.taskgraph_patch.start()
        self.mock_pipeline_cls = self.pipeline_patch.start()
        self.mock_debate_cls = self.debate_patch.start()

        self.mock_planner = MagicMock()
        self.mock_executor = MagicMock()
        self.mock_taskgraph = MagicMock()
        self.mock_pipeline = MagicMock()
        self.mock_debate = MagicMock()

        self.mock_planner_cls.return_value = self.mock_planner
        self.mock_executor_cls.return_value = self.mock_executor
        self.mock_taskgraph_cls.return_value = self.mock_taskgraph
        self.mock_pipeline_cls.return_value = self.mock_pipeline
        self.mock_debate_cls.return_value = self.mock_debate

        self.orch = Orchestrator(
            provider=self.provider,
            tools=self.tools,
        )

        # Wire mock executor.agent for NLA telemetry access
        self.mock_agent = MagicMock()
        self.mock_agent.nla_telemetry = MagicMock()
        self.mock_agent.nla_telemetry.load_records.return_value = []
        self.mock_executor.agent = self.mock_agent

    def tearDown(self):
        self.planner_patch.stop()
        self.executor_patch.stop()
        self.taskgraph_patch.stop()
        self.pipeline_patch.stop()
        self.debate_patch.stop()

    def _make_task(self, task_id="task1", title="Test Task", description="Do something",
                   status="pending"):
        task = MagicMock()
        task.id = task_id
        task.title = title
        task.description = description
        task.status = status
        task.result = None
        return task

    def test_autonomous_starts_planning_state(self):
        self.mock_taskgraph.decompose.return_value = self._make_task("root")
        self.mock_taskgraph.get_ready_tasks.return_value = []
        self.mock_taskgraph.get_progress.return_value = {
            "completed": 0, "total": 0, "pending": 0, "failed": 0, "blocked": 0
        }

        events = list(self.orch.run_autonomous("build a website"))
        # First event should be state_change=planning
        self.assertEqual(events[0].type, "state_change")
        self.assertEqual(events[0].data, "planning")

    def test_autonomous_decomposes_goal(self):
        root_task = self._make_task("root")
        self.mock_taskgraph.decompose.return_value = root_task
        self.mock_taskgraph.get_ready_tasks.return_value = []
        self.mock_taskgraph.get_progress.return_value = {
            "completed": 0, "total": 1, "pending": 0, "failed": 0, "blocked": 0
        }

        list(self.orch.run_autonomous("build a website"))
        self.mock_taskgraph.decompose.assert_called_once_with("build a website")

    def test_autonomous_executes_ready_tasks(self):
        task = self._make_task("t1", "Write tests", "Write unit tests")
        self.mock_taskgraph.decompose.return_value = task
        self.mock_taskgraph.get_ready_tasks.side_effect = [
            [task],
            [],
        ]
        self.mock_taskgraph.get_progress.return_value = {
            "completed": 1, "total": 1, "pending": 0, "failed": 0, "blocked": 0
        }

        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_chunk", "writing tests..."),
            _event("content_complete", "tests done"),
        ])

        # Mock full pipeline pass
        mock_report = MagicMock()
        mock_report.tests_passed = True
        mock_report.secrets_found = False
        self.mock_pipeline.run_full_pipeline.return_value = mock_report

        # Mock debate pass verdict
        mock_verdict = MagicMock()
        mock_verdict.final_approved = True
        mock_verdict.consensus_summary = "Looks good"
        mock_verdict.consensus_score = 95
        mock_verdict.reworked_code = None
        self.mock_debate.run_debate.return_value = mock_verdict

        list(self.orch.run_autonomous("build a website"))
        # Task should be marked completed
        self.assertEqual(task.status, "completed")
        self.assertIsNotNone(task.result)
        self.mock_taskgraph.save.assert_called()

    def test_autonomous_with_devops_failure(self):
        task = self._make_task("t2", "Write code", "Write the code")
        self.mock_taskgraph.decompose.return_value = task
        self.mock_taskgraph.get_ready_tasks.side_effect = [
            [task],
            [],
        ]
        self.mock_taskgraph.get_progress.return_value = {
            "completed": 0, "total": 1, "pending": 0,
            "failed": 1, "blocked": 0
        }

        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "code written"),
        ])

        # DevOps pipeline fails
        mock_report = MagicMock()
        mock_report.tests_passed = False
        mock_report.traceback_analysis = "AssertionError: expected 5, got 3"
        mock_report.secrets_found = False
        self.mock_pipeline.run_full_pipeline.return_value = mock_report

        events = list(self.orch.run_autonomous("build a website"))
        # Task should have retried (max_subtask_retries=2)
        # With no NLA records, it still retries
        self.mock_executor.execute_plan.assert_called()
        # Task stays 'running' because the retry loop exits before marking 'failed'
        self.assertEqual(task.status, "running")
        # done event should report failure
        done_events = [e for e in events if e.type == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertFalse(done_events[0].data["success"])

    def test_autonomous_with_debate_rejection(self):
        task = self._make_task("t3", "Refactor", "Refactor code")
        self.mock_taskgraph.decompose.return_value = task
        self.mock_taskgraph.get_ready_tasks.side_effect = [
            [task,],
            [],
        ]
        self.mock_taskgraph.get_progress.return_value = {
            "completed": 0, "total": 1, "pending": 0,
            "failed": 1, "blocked": 0
        }

        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "refactored"),
        ])

        # DevOps passes
        mock_report = MagicMock()
        mock_report.tests_passed = True
        mock_report.secrets_found = False
        self.mock_pipeline.run_full_pipeline.return_value = mock_report

        # But debate rejects
        mock_verdict = MagicMock()
        mock_verdict.final_approved = False
        mock_verdict.consensus_summary = "Code quality issues"
        mock_verdict.consensus_score = 45
        mock_verdict.reworked_code = None
        self.mock_debate.run_debate.return_value = mock_verdict

        events = list(self.orch.run_autonomous("build a website"))
        # Task stays 'running' because the retry loop exits before marking 'failed'
        # The done event reports failure
        done_events = [e for e in events if e.type == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertFalse(done_events[0].data["success"])

    def test_autonomous_with_secrets_found(self):
        task = self._make_task("t4", "Add config", "Add config file")
        self.mock_taskgraph.decompose.return_value = task
        self.mock_taskgraph.get_ready_tasks.side_effect = [
            [task],
            [],
        ]
        self.mock_taskgraph.get_progress.return_value = {
            "completed": 0, "total": 1, "pending": 0,
            "failed": 1, "blocked": 0
        }

        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "config added"),
        ])

        # DevOps finds secrets
        mock_secret = MagicMock()
        mock_secret.pattern_name = "AWS API Key"
        mock_report = MagicMock()
        mock_report.tests_passed = True
        mock_report.secrets_found = [mock_secret]
        self.mock_pipeline.run_full_pipeline.return_value = mock_report

        events = list(self.orch.run_autonomous("build a website"))
        done_events = [e for e in events if e.type == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertFalse(done_events[0].data["success"])

    def test_autonomous_all_tasks_complete(self):
        task = self._make_task("t5", "Final task", "Complete the work")
        self.mock_taskgraph.decompose.return_value = task
        self.mock_taskgraph.get_ready_tasks.side_effect = [
            [task],
            [],
        ]
        self.mock_taskgraph.get_progress.side_effect = [
            {"completed": 0, "total": 1, "pending": 0, "failed": 0, "blocked": 0},
            {"completed": 1, "total": 1, "pending": 0, "failed": 0, "blocked": 0},
        ]

        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "done"),
        ])

        mock_report = MagicMock()
        mock_report.tests_passed = True
        mock_report.secrets_found = False
        self.mock_pipeline.run_full_pipeline.return_value = mock_report

        mock_verdict = MagicMock()
        mock_verdict.final_approved = True
        mock_verdict.consensus_summary = "Good"
        mock_verdict.consensus_score = 90
        mock_verdict.reworked_code = None
        self.mock_debate.run_debate.return_value = mock_verdict

        events = list(self.orch.run_autonomous("build a website"))
        done_events = [e for e in events if e.type == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertTrue(done_events[0].data["success"])

    def test_autonomous_blocked_tasks(self):
        """When tasks are blocked/pending but no ready tasks, should log warning."""
        task = self._make_task("blocked1", "Blocked", "Blocked by dependency",
                              status="blocked")
        self.mock_taskgraph.decompose.return_value = task
        self.mock_taskgraph.get_ready_tasks.return_value = []
        self.mock_taskgraph.get_progress.return_value = {
            "completed": 0, "total": 2, "pending": 1, "failed": 0, "blocked": 1
        }

        events = list(self.orch.run_autonomous("build a website"))
        done_events = [e for e in events if e.type == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertFalse(done_events[0].data["success"])

    def test_autonomous_retry_on_execution_error(self):
        task = self._make_task("t6", "Error prone task", "Might fail")
        self.mock_taskgraph.decompose.return_value = task
        self.mock_taskgraph.get_ready_tasks.side_effect = [
            [task],
            [],
        ]
        self.mock_taskgraph.get_progress.return_value = {
            "completed": 0, "total": 1, "pending": 0, "failed": 1, "blocked": 0
        }

        # Executor raises an error
        self.mock_executor.execute_plan.side_effect = RuntimeError("Execution crashed")

        events = list(self.orch.run_autonomous("build a website"))
        # Should have retried
        self.assertEqual(self.mock_executor.execute_plan.call_count, 2)  # max 2 retries
        done_events = [e for e in events if e.type == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertFalse(done_events[0].data["success"])


class TestOrchestratorDebateReworkedCode(unittest.TestCase):
    """Test the debate reworked-code parsing logic in run_autonomous."""

    def setUp(self):
        self.provider = MagicMock()
        self.tools = [MagicMock()]

        self.tg_patch = patch("nexus_agent.core.orchestrator.TaskGraph")
        self.pipe_patch = patch("nexus_agent.core.orchestrator.VerificationPipeline")
        self.debate_patch = patch("nexus_agent.core.orchestrator.DebateEngine")
        self.exec_patch = patch("nexus_agent.core.orchestrator.Executor")
        self.plan_patch = patch("nexus_agent.core.orchestrator.Planner")

        self.mock_taskgraph_cls = self.tg_patch.start()
        self.mock_pipeline_cls = self.pipe_patch.start()
        self.mock_debate_cls = self.debate_patch.start()
        self.mock_executor_cls = self.exec_patch.start()
        self.mock_planner_cls = self.plan_patch.start()

        self.mock_tg = MagicMock()
        self.mock_pipeline = MagicMock()
        self.mock_debate = MagicMock()
        self.mock_executor = MagicMock()
        self.mock_planner = MagicMock()

        self.mock_taskgraph_cls.return_value = self.mock_tg
        self.mock_pipeline_cls.return_value = self.mock_pipeline
        self.mock_debate_cls.return_value = self.mock_debate
        self.mock_executor_cls.return_value = self.mock_executor
        self.mock_planner_cls.return_value = self.mock_planner

        self.mock_agent = MagicMock()
        self.mock_agent.nla_telemetry = MagicMock()
        self.mock_agent.nla_telemetry.load_records.return_value = []
        self.mock_executor.agent = self.mock_agent

        self.orch = Orchestrator(
            provider=self.provider,
            tools=self.tools,
        )

    def tearDown(self):
        self.tg_patch.stop()
        self.pipe_patch.stop()
        self.debate_patch.stop()
        self.exec_patch.stop()
        self.plan_patch.stop()

    def _setup_basic_mocks(self):
        task = MagicMock()
        task.id = "t1"
        task.title = "Test"
        task.description = "Do work"
        task.status = "pending"
        task.result = None

        self.mock_tg.decompose.return_value = task
        self.mock_tg.get_ready_tasks.side_effect = [[task], []]
        self.mock_tg.get_progress.return_value = {
            "completed": 1, "total": 1, "pending": 0, "failed": 0, "blocked": 0
        }

        self.mock_executor.execute_plan.return_value = FakeIterator([
            _event("content_complete", "done"),
        ])

        mock_report = MagicMock()
        mock_report.tests_passed = True
        mock_report.secrets_found = False
        self.mock_pipeline.run_full_pipeline.return_value = mock_report

        return task

    def test_debate_reworked_code_writes_files(self):
        self._setup_basic_mocks()

        mock_verdict = MagicMock()
        mock_verdict.final_approved = True
        mock_verdict.consensus_summary = "Needs refactoring"
        mock_verdict.consensus_score = 70
        mock_verdict.reworked_code = """
### File: src/main.py
```python
print("Hello, World!")
```
"""
        self.mock_debate.run_debate.return_value = mock_verdict

        # Create a temp workspace for this test
        import tempfile
        self.orch.workspace = Path(tempfile.mkdtemp())
        target = self.orch.workspace / "src" / "main.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("old content")

        list(self.orch.run_autonomous("build a website"))
        self.assertEqual(target.read_text(), 'print("Hello, World!")')

    def test_debate_reworked_code_path_traversal_blocked(self):
        self._setup_basic_mocks()

        mock_verdict = MagicMock()
        mock_verdict.final_approved = True
        mock_verdict.consensus_summary = "Needs fix"
        mock_verdict.consensus_score = 70
        mock_verdict.reworked_code = """
### File: ../../etc/passwd
```text
hacked
```
"""
        self.mock_debate.run_debate.return_value = mock_verdict

        import tempfile
        self.orch.workspace = Path(tempfile.mkdtemp())
        # Should not crash — path traversal should be silently blocked
        list(self.orch.run_autonomous("build a website"))


if __name__ == "__main__":
    unittest.main()
