"""Tests for `core/updater.py` — version parsing and PyPI check."""

import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.core.updater import (
    PYPI_URL,
    _parse_version,
    check_for_update,
    get_installed_version,
)


class TestParseVersion(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(_parse_version("1.2.3"), (1, 2, 3))

    def test_two_part(self):
        self.assertEqual(_parse_version("0.10"), (0, 10))

    def test_with_prefix_does_not_match(self):
        # The parser is strict — it doesn't strip "v" prefixes.
        self.assertEqual(_parse_version("v1.2.3"), (0,))

    def test_with_suffix(self):
        self.assertEqual(_parse_version("1.2.3a1"), (1, 2, 3))

    def test_empty_returns_zero_tuple(self):
        self.assertEqual(_parse_version(""), (0,))

    def test_garbage_returns_zero_tuple(self):
        self.assertEqual(_parse_version("nonsense"), (0,))


class TestGetInstalledVersion(unittest.TestCase):
    def test_returns_metadata(self):
        # If the real package is installed (it is, in CI), metadata works.
        # We don't patch; we just verify it returns a non-empty string.
        v = get_installed_version()
        self.assertIsInstance(v, str)
        self.assertTrue(v)

    def test_falls_back_to_module_attribute(self):
        from importlib import metadata as importlib_metadata

        real_pnf = importlib_metadata.PackageNotFoundError

        def raise_pnf(*args, **kwargs):
            raise real_pnf("nope")

        with patch(
            "nexus_agent.core.updater.importlib_metadata.version",
            side_effect=raise_pnf,
        ):
            v = get_installed_version()
        self.assertIsInstance(v, str)
        self.assertTrue(v)

    def test_raises_when_no_source(self):
        from importlib import metadata as importlib_metadata

        real_pnf = importlib_metadata.PackageNotFoundError

        def raise_pnf(*args, **kwargs):
            raise real_pnf("nope")

        with patch(
            "nexus_agent.core.updater.importlib_metadata.version",
            side_effect=raise_pnf,
        ):
            # Wipe the __version__ attribute for the duration of the call
            with patch("nexus_agent.core.updater.nexus_agent") as mod:
                mod.configure_mock(**{"__version__": None})
                # The real getter is `getattr(nexus_agent, "__version__", None)`.
                # Patching the module to a MagicMock means `nexus_agent.__version__`
                # is a MagicMock by default — but `__version__` exists.
                # The fallback path then returns a MagicMock, not None.
                # To force the "no source" path, we patch `getattr` itself.
                with patch(
                    "nexus_agent.core.updater.getattr",
                    side_effect=lambda obj, name, default=None: default
                    if name == "__version__" else getattr(obj, name, default),
                ):
                    with self.assertRaises(ValueError):
                        get_installed_version()


class TestCheckForUpdate(unittest.TestCase):
    def _mock_response(self, status: int = 200, payload: dict | None = None):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = payload or {}
        return r

    def test_returns_true_when_newer(self):
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                200, {"info": {"version": "99.0.0"}}
            )
            MockClient.return_value = ctx
            info = check_for_update("1.0.0")
        self.assertTrue(info.available)
        self.assertEqual(info.latest, "99.0.0")
        self.assertEqual(info.current, "1.0.0")

    def test_returns_false_when_same(self):
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                200, {"info": {"version": "1.0.0"}}
            )
            MockClient.return_value = ctx
            info = check_for_update("1.0.0")
        self.assertFalse(info.available)
        self.assertEqual(info.latest, "1.0.0")

    def test_returns_false_when_older(self):
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                200, {"info": {"version": "0.5.0"}}
            )
            MockClient.return_value = ctx
            info = check_for_update("1.0.0")
        self.assertFalse(info.available)

    def test_404_response(self):
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(404)
            MockClient.return_value = ctx
            info = check_for_update("1.0.0")
        self.assertFalse(info.available)
        self.assertIn("404", info.error or "")

    def test_network_error(self):
        import httpx
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.side_effect = httpx.ConnectError("nope")
            MockClient.return_value = ctx
            info = check_for_update("1.0.0")
        self.assertFalse(info.available)
        self.assertIn("nope", info.error or "")

    def test_malformed_json(self):
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            r = self._mock_response(200)
            r.json.side_effect = ValueError("not json")
            ctx.__enter__.return_value.get.return_value = r
            MockClient.return_value = ctx
            info = check_for_update("1.0.0")
        self.assertFalse(info.available)
        self.assertIn("not json", info.error or "")

    def test_no_version_in_response(self):
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(200, {"info": {}})
            MockClient.return_value = ctx
            info = check_for_update("1.0.0")
        self.assertFalse(info.available)
        self.assertIn("No version", info.error or "")

    def test_uses_custom_package(self):
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                200, {"info": {"version": "2.0.0"}}
            )
            MockClient.return_value = ctx
            info = check_for_update("1.0.0", package="other-pkg")
            called_url = ctx.__enter__.return_value.get.call_args.args[0]
        self.assertIn("other-pkg", called_url)
        self.assertTrue(info.available)

    def test_uses_timeout(self):
        with patch("nexus_agent.core.updater.httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                200, {"info": {"version": "1.0.0"}}
            )
            MockClient.return_value = ctx
            check_for_update("1.0.0", timeout_s=3.5)
            client = MockClient.call_args.kwargs
            self.assertEqual(client["timeout"], 3.5)

    def test_pypi_url_constant(self):
        self.assertTrue(PYPI_URL.startswith("https://pypi.org/"))


if __name__ == "__main__":
    unittest.main()
