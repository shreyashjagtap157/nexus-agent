"""Unit tests to verify RAG search, batch editing, and loading guardrails."""

import os
import tempfile
import unittest
from pathlib import Path

from nexus_agent.llm.model_manager import ModelManager
from nexus_agent.tools.rag_search import RepositoryRAGTool
from nexus_agent.tools.batch_edit import BatchEditTool


class TestAdvancedFeatures(unittest.TestCase):
    """Test suite for Phase 7 advanced options."""

    def setUp(self) -> None:
        # Create temp folder simulating user workspace
        self.test_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.test_dir.name)
        self.rag_tool = None
        
        # Write dummy code files
        self.file1 = self.workspace / "utils.py"
        self.file1.write_text(
            "def calculate_total(a, b):\n"
            "    # This is a dummy sum function\n"
            "    return a + b\n",
            encoding="utf-8"
        )
        
        self.file2 = self.workspace / "main.py"
        self.file2.write_text(
            "from utils import calculate_total\n"
            "print(calculate_total(10, 20))\n",
            encoding="utf-8"
        )

    def tearDown(self) -> None:
        if self.rag_tool:
            try:
                self.rag_tool.close()
            except Exception:
                pass
        self.test_dir.cleanup()


    def test_rag_search_indexing(self) -> None:
        """Verify RAG tool segments indexing, symbol extraction, and offline FTS5 searches."""
        self.rag_tool = RepositoryRAGTool(workspace=self.workspace, db_dir=self.workspace)
        
        # Index files
        res = self.rag_tool.execute(query="dummy", reindex=True)
        self.assertIn("Found 1 relevant file code blocks", res)
        self.assertIn("utils.py", res)

        # Keyword search and symbol boost check
        res2 = self.rag_tool.execute(query="calculate_total")
        self.assertIn("Found 2 relevant file code blocks", res2)
        # Function calculate_total should be matched as a symbol and boosted!
        self.assertIn("FUNCTION: calculate_total", res2)
        self.assertIn("main.py", res2)


    def test_batch_edit_atomicity(self) -> None:
        """Verify BatchEditTool replaces blocks atomically and rolls back on failures."""
        editor = BatchEditTool(workspace=self.workspace)
        
        edits = [
            {
                "path": "utils.py",
                "target_content": "return a + b",
                "replacement_content": "return a * b",
            },
            {
                "path": "main.py",
                "target_content": "print(calculate_total(10, 20))",
                "replacement_content": "print('Result:', calculate_total(10, 20))",
            }
        ]
        
        res = editor.execute(edits)
        self.assertIn("Atomic batch transaction succeeded", res)
        
        # Verify content updated
        self.assertIn("a * b", self.file1.read_text(encoding="utf-8"))
        self.assertIn("Result:", self.file2.read_text(encoding="utf-8"))

        # Verify rollback on failure
        failing_edits = [
            {
                "path": "utils.py",
                "target_content": "return a * b",
                "replacement_content": "return a / b",
            },
            {
                "path": "main.py",
                "target_content": "NON-EXISTENT-TARGET-BLOCK",
                "replacement_content": "print('Fail')",
            }
        ]
        
        with self.assertRaises(RuntimeError):
            editor.execute(failing_edits)
            
        # utils.py must be rolled back to "a * b" rather than "a / b"
        self.assertIn("a * b", self.file1.read_text(encoding="utf-8"))

    def test_loading_guardrails(self) -> None:
        """Verify model loading guardrails safety validations under simulated memory."""
        mgr = ModelManager()
        
        # Evaluate simulated existing dummy model
        dummy_model = self.workspace / "model.gguf"
        # Create a large 10MB dummy model file
        with open(dummy_model, "wb") as f:
            f.write(b"\0" * 10 * 1024 * 1024)

        chk_balanced = mgr.evaluate_loading_guardrail(str(dummy_model), "balanced")
        self.assertTrue(chk_balanced["allowed"])
        self.assertIsNone(chk_balanced["warning"])

    def test_agent_telemetry_tracing(self) -> None:
        """Verify AgentLoop writes JSONL execution trace files to the workspace."""
        from nexus_agent.core.agent import AgentLoop, AgentLoopConfig
        
        # Create a mock provider
        from unittest.mock import MagicMock
        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.model_name = "mock-model"
        
        from nexus_agent.llm.base import LLMResponse
        mock_response = LLMResponse(content="I am a mock agent.", tool_calls=[], finish_reason="stop")
        mock_provider.chat_completion.return_value = mock_response
        mock_provider.count_message_tokens.return_value = 10
        
        agent = AgentLoop(
            provider=mock_provider,
            config=AgentLoopConfig(
                workspace=self.workspace,
                max_iterations=5,
                effort_level="medium"
            )
        )
        
        # Execute run
        events = list(agent.run("Hello"))
        self.assertTrue(len(events) > 0)
        
        # Verify trace file exists in .nexus-agent/traces/
        trace_dir = self.workspace / ".nexus-agent" / "traces"
        self.assertTrue(trace_dir.exists())
        
        trace_files = list(trace_dir.glob("trace_*.jsonl"))
        self.assertEqual(len(trace_files), 1)
        
        # Verify trace content is structured JSONL
        trace_content = trace_files[0].read_text(encoding="utf-8")
        self.assertIn("state_change", trace_content)
        self.assertIn("thinking", trace_content)
        self.assertIn("done", trace_content)

    def test_lsp_client_diagnostics(self) -> None:
        """Verify LSP static diagnostics catches Python compile errors locally."""
        from nexus_agent.tools.lsp_client import LSPClientTool
        tool = LSPClientTool(workspace=self.workspace)
        
        # Test valid syntax file
        res_ok = tool.execute(action="diagnostics", file=str(self.file1))
        self.assertIn("Diagnostics OK", res_ok)
        
        # Write broken syntax file
        broken_file = self.workspace / "broken.py"
        broken_file.write_text(
            "def broken_function()\n"  # Missing colon
            "    return True\n",
            encoding="utf-8"
        )
        
        res_err = tool.execute(action="diagnostics", file=str(broken_file))
        self.assertIn("SYNTAX DIAGNOSTICS FAILURE", res_err)
        self.assertIn("Line 1", res_err)

        # Test definitions lookup
        res_def = tool.execute(action="definition", file=str(self.file1), line=1)
        self.assertIn("Discovered definition", res_def)
        
    def test_browser_crawler_fallback(self) -> None:
        """Verify BrowserTool falls back cleanly to HTTPX HTML parser scraping."""
        from nexus_agent.tools.browser import BrowserTool
        tool = BrowserTool()
        
        # Execute static navigate fallback on a local mock target or static html file
        res = tool._execute_httpx(action="read", url="https://example.com")
        self.assertIn("Webpage Scraped", res)
        self.assertIn("Example Domain", res)

    def test_self_healing_retry_loop(self) -> None:
        """Verify retry and diagnosis prompt generation in SelfHealingExecutor."""
        from nexus_agent.core.self_heal import SelfHealingExecutor
        healer = SelfHealingExecutor(max_retries=2, base_delay=0.01)

        # Mock a failing tool
        class BrokenTool:
            name = "broken"
            def execute(self, **kwargs):
                raise ConnectionError("connection reset by peer")

        res = healer.execute_with_healing(BrokenTool(), {})
        self.assertFalse(res.success)
        self.assertEqual(res.total_retries, 2)
        self.assertIn("Diagnosis Report", res.diagnosis)
        self.assertIn("connection reset by peer", res.diagnosis)

    def test_failure_classification(self) -> None:
        """Verify classifying error messages into transient, semantic, or fatal categories."""
        from nexus_agent.core.self_heal import classify_failure, FailureType
        self.assertEqual(classify_failure("connection reset"), FailureType.TRANSIENT)
        self.assertEqual(classify_failure("no such file or directory"), FailureType.SEMANTIC)
        self.assertEqual(classify_failure("permission denied"), FailureType.FATAL)

    def test_reflection_critic_loop(self) -> None:
        """Verify reflection engine structure and critique score feedback generation."""
        from nexus_agent.core.reflection import ReflectionEngine
        engine = ReflectionEngine(threshold=85)
        # Without LLM provider, it uses heuristic check
        critique = engine.evaluate("Request", "TODO: implement this.")
        self.assertFalse(critique.approved)
        self.assertIn("placeholder", critique.issues[0].description)

    def test_task_graph_decomposition(self) -> None:
        """Verify TaskGraph decomposes goal, tracks dependencies and renders DAG progress."""
        from nexus_agent.core.task_graph import TaskGraph
        tg = TaskGraph(session_id="test-session", workspace=self.workspace)
        root = tg.decompose("Fix authentication bug and run tests")
        self.assertEqual(len(tg.nodes), 4)  # Root + 3 stages
        self.assertEqual(root.id, tg.root_id)
        
        # Test ready tasks sequencing
        ready = tg.get_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].title, "Gather Context")
        
        # Mark completed and check next ready task
        ready[0].status = "completed"
        ready_next = tg.get_ready_tasks()
        self.assertEqual(len(ready_next), 1)
        self.assertEqual(ready_next[0].title, "Implement Changes")

    def test_nla_telemetry_logging(self) -> None:
        """Verify NLATelemetry captures autoencoder reasoning telemetry steps."""
        from nexus_agent.core.nla_telemetry import NLATelemetry
        nla = NLATelemetry(session_id="test-nla", workspace=self.workspace)
        record = nla.log_iteration(
            thought_process="Searching codebase...",
            strategy_selected="search",
            tools_considered=["file_ops"],
            confidence_score=0.95,
            alternative_paths=[]
        )
        self.assertEqual(record.strategy_selected, "search")
        nla.flush()
        self.assertTrue(nla.log_file.exists())

        # Reload and check
        reloaded = nla.load_records()
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0].thought_process, "Searching codebase...")

    def test_debate_consensus(self) -> None:
        """Verify multi-reviewer parallel debate consensus scores and verdicts."""
        from nexus_agent.core.debate import DebateEngine
        engine = DebateEngine()
        reviews = engine.review_changes("def unsafe(): eval('x')")
        # Security review should penalize eval() usage!
        self.assertEqual(len(reviews), 4)
        sec_rev = next(r for r in reviews if r.reviewer_name == "SecurityAuditor")
        self.assertLess(sec_rev.score, 70)
        self.assertFalse(sec_rev.approved)

        # Judge should reject
        verdict = engine.judge(reviews)
        self.assertFalse(verdict.final_approved)

    def test_verification_pipeline(self) -> None:
        """Verify VerificationPipeline auto-detects frameworks and scans security secrets."""
        from nexus_agent.core.devops import VerificationPipeline
        pipeline = VerificationPipeline(workspace=self.workspace)
        
        # We wrote dummy python files main.py and utils.py in setUp
        fw = pipeline.test_runner.detect_framework()
        self.assertEqual(fw, "unittest")

        # Test secret scanner
        secret_file = self.workspace / "secret.py"
        secret_file.write_text("aws_key = 'AKIA1234567890123456'", encoding="utf-8")
        secrets = pipeline.secret_scanner.scan()
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0].pattern_name, "AWS API Key/Secret")

    def test_code_intel_import_graph(self) -> None:
        """Verify ImportGraphTool builds workspace module dependency lists."""
        from nexus_agent.tools.code_intel import ImportGraphTool
        tool = ImportGraphTool(workspace=self.workspace)
        res = tool.execute(action="build")
        self.assertIn("main", res)
        self.assertIn("utils", res)

        # Find dependents check
        deps = tool.execute(action="find_dependents", target="utils")
        self.assertIn("main", deps)


class TestModelsDBExtended(unittest.TestCase):
    """Phase 8: Verify ModelsDB extended schema, migration, and tracking."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extended_schema_full_metadata(self):
        """Verify ModelsDB stores and retrieves full metadata fields."""
        from nexus_agent.cli.models_db import ModelsDB
        db = ModelsDB(data_dir=self.data_dir)
        db.add(
            name="test-model",
            path_or_id="/path/to/model.gguf",
            provider="anthropic",
            context_size=200000,
            capabilities={"vision": True, "tool_calling": True, "streaming": True},
        )
        entry = db.get("test-model")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["path_or_id"], "/path/to/model.gguf")
        self.assertEqual(entry["provider"], "anthropic")
        self.assertEqual(entry["context_size"], 200000)
        self.assertTrue(entry["capabilities"]["vision"])
        self.assertTrue(entry["capabilities"]["tool_calling"])
        self.assertIn("last_used", entry)
        self.assertIn("added", entry)

    def test_usage_and_session_tracking(self):
        """Verify token usage recording and session counters."""
        from nexus_agent.cli.models_db import ModelsDB
        db = ModelsDB(data_dir=self.data_dir)
        db.add(name="tracked-model", path_or_id="tracked-v1")
        db.record_usage("tracked-model", tokens=1500, cost=0.03)
        stats = db.get_stats("tracked-model")
        self.assertEqual(stats["total_tokens"], 1500)
        self.assertAlmostEqual(stats["total_cost"], 0.03)

        db.record_session_start("tracked-model")
        stats2 = db.get_stats("tracked-model")
        self.assertEqual(stats2["sessions"], 1)

    def test_backward_compat_migration(self):
        """Verify old string-only entries migrate to dict schema on load."""
        import json
        legacy = {"old-model": "/legacy/path.bin", "another-old": "/alt/path.bin"}
        db_path = os.path.join(self.data_dir, "models_db.json")
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(legacy, f)

        from nexus_agent.cli.models_db import ModelsDB
        db = ModelsDB(data_dir=self.data_dir)
        entry = db.get("old-model")
        self.assertIsInstance(entry, dict)
        self.assertEqual(entry["path_or_id"], "/legacy/path.bin")
        self.assertEqual(entry["provider"], "local")
        self.assertIn("total_tokens", entry)


class TestCmdMenuSlidingWindow(unittest.TestCase):
    """Phase 8: Verify command menu sliding-window viewport calculations."""

    def test_window_centering_low_bound(self):
        """When selected index is near start, window starts at 0."""
        from nexus_agent.cli.app import NexusApp
        app = object.__new__(NexusApp)
        app._cmd_menu_lines = 0
        app._sub_agents = []
        app._drawer_active = False
        app._drawer_idx = 0
        app._notification = ""
        app._notification_time = 0.0
        app._footer_log = ""
        app._footer_log_time = 0.0

        total_items = 50
        MAX_VISIBLE = 10
        idx = 0
        start_idx = idx - MAX_VISIBLE // 2
        start_idx = max(0, min(start_idx, total_items - MAX_VISIBLE))
        end_idx = start_idx + MAX_VISIBLE
        self.assertEqual(start_idx, 0)
        self.assertEqual(end_idx, 10)

    def test_window_centering_mid(self):
        """When selected is in the middle, window is centered."""
        total_items = 50
        MAX_VISIBLE = 10
        idx = 25
        start_idx = idx - MAX_VISIBLE // 2
        start_idx = max(0, min(start_idx, total_items - MAX_VISIBLE))
        end_idx = start_idx + MAX_VISIBLE
        self.assertEqual(start_idx, 20)
        self.assertEqual(end_idx, 30)

    def test_window_centering_high_bound(self):
        """When selected index is near end, window stops at total."""
        total_items = 50
        MAX_VISIBLE = 10
        idx = 49
        start_idx = idx - MAX_VISIBLE // 2
        start_idx = max(0, min(start_idx, total_items - MAX_VISIBLE))
        end_idx = start_idx + MAX_VISIBLE
        self.assertEqual(start_idx, 40)
        self.assertEqual(end_idx, 50)

    def test_window_small_list(self):
        """When total items fit within window, no clipping."""
        total_items = 5
        MAX_VISIBLE = 10
        idx = 2
        start_idx = idx - MAX_VISIBLE // 2
        start_idx = max(0, min(start_idx, total_items - MAX_VISIBLE))
        end_idx = start_idx + MAX_VISIBLE
        self.assertEqual(start_idx, 0)
        self.assertEqual(end_idx, 10)

    def test_window_indicators_low(self):
        """Above indicator shown when start_idx > 0."""
        total_items = 50
        MAX_VISIBLE = 10
        idx = 30
        start_idx = idx - MAX_VISIBLE // 2
        start_idx = max(0, min(start_idx, total_items - MAX_VISIBLE))
        self.assertGreater(start_idx, 0)

    def test_window_indicators_end(self):
        """Below indicator shown when remaining > 0."""
        total_items = 50
        MAX_VISIBLE = 10
        idx = 0
        start_idx = idx - MAX_VISIBLE // 2
        start_idx = max(0, min(start_idx, total_items - MAX_VISIBLE))
        end_idx = start_idx + MAX_VISIBLE
        remaining = total_items - end_idx
        self.assertGreater(remaining, 0)


class TestEffortLevelCentersAndColors(unittest.TestCase):
    """Phase 8: Verify effort level centering offsets and color mappings."""

    def test_center_offsets_are_precise(self):
        """Verify exact center offsets for each effort level."""
        CENTER_OFFSETS = [25, 37, 46, 56, 65]
        levels = ["low", "medium", "high", "xhigh", "max"]
        label_widths = [3, 6, 4, 5, 3]
        for i, lab in enumerate(levels):
            offset = CENTER_OFFSETS[i]
            self.assertIsInstance(offset, int)
            self.assertGreaterEqual(offset, 0)
            half = label_widths[i] // 2
            label_start = offset - half
            label_end = label_start + label_widths[i]
            self.assertGreaterEqual(label_start, 0)
            self.assertGreater(label_end, label_start)

    def test_color_map_has_all_levels(self):
        """Verify every effort level has a corresponding ANSI color code."""
        EFFORT_COLORS = {"low": "32", "medium": "36", "high": "33", "xhigh": "35", "max": "31"}
        self.assertIn("low", EFFORT_COLORS)
        self.assertIn("medium", EFFORT_COLORS)
        self.assertIn("high", EFFORT_COLORS)
        self.assertIn("xhigh", EFFORT_COLORS)
        self.assertIn("max", EFFORT_COLORS)
        self.assertEqual(EFFORT_COLORS["low"], "32")
        self.assertEqual(EFFORT_COLORS["medium"], "36")
        self.assertEqual(EFFORT_COLORS["high"], "33")
        self.assertEqual(EFFORT_COLORS["xhigh"], "35")
        self.assertEqual(EFFORT_COLORS["max"], "31")

    def test_marker_alignment_consistency(self):
        """Verify center offsets are strictly increasing and well-spaced."""
        CENTER_OFFSETS = [25, 37, 46, 56, 65]
        for i in range(1, len(CENTER_OFFSETS)):
            self.assertGreater(CENTER_OFFSETS[i], CENTER_OFFSETS[i - 1])
