"""Isolated scan regression tests; no live Home Assistant or Tdarr required."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import requests

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tdarr"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = load_module("tdarr_api_test", ROOT / "tdarr.py")


class EntityStub:
    def __init__(self, *, coordinator, device_id, name):
        self.coordinator = coordinator
        self._device_id = device_id

    @property
    def available(self):
        return self.coordinator.last_update_success


class HomeAssistantError(Exception):
    pass


def load_buttons():
    modules = {name: ModuleType(name) for name in (
        "scan_test", "scan_test.const", "homeassistant",
        "homeassistant.components", "homeassistant.components.button",
        "homeassistant.core", "homeassistant.exceptions",
    )}
    modules["scan_test"].TdarrEntity = EntityStub
    modules["scan_test.const"].COORDINATOR = "coordinator"
    modules["scan_test.const"].DOMAIN = "tdarr"
    modules["homeassistant.components.button"].ButtonEntity = type("ButtonEntity", (), {})
    modules["homeassistant.core"].callback = lambda fn: fn
    modules["homeassistant.exceptions"].HomeAssistantError = HomeAssistantError
    with patch.dict(sys.modules, modules):
        return load_module("scan_test.button", ROOT / "button.py")


buttons = load_buttons()


class ScanApiTests(unittest.TestCase):
    def setUp(self):
        self.server = api.Server("localhost", "8265", "test-key")

    @patch.object(api.requests, "post")
    def test_exact_payload_and_plain_text_response(self, post):
        self.server.scanLibrary("movies-id", "/media/movies")
        post.assert_called_once_with(
            "http://localhost:8265/api/v2/scan-files",
            json={"data": {"scanConfig": {
                "dbID": "movies-id", "arrayOrPath": "/media/movies", "mode": "scanFindNew",
            }}}, headers=self.server.headers, timeout=30,
        )
        post.return_value.raise_for_status.assert_called_once()
        post.return_value.json.assert_not_called()

    @patch.object(api.requests, "post")
    def test_missing_folder_never_sends_request(self, post):
        for folder in (None, "", " ", []):
            with self.assertRaises(ValueError):
                self.server.scanLibrary("id", folder)
        post.assert_not_called()

    @patch.object(api.requests, "post")
    def test_http_error_propagates(self, post):
        post.return_value.raise_for_status.side_effect = requests.HTTPError()
        with self.assertRaises(requests.HTTPError):
            self.server.scanLibrary("id", "/media")

    def test_library_metadata_and_aggregate(self):
        self.server.getLibraryStats = Mock(return_value=[
            {"_id": "a", "name": "Movies", "folder": "/movies"},
            {"_id": "b", "name": "Movies 4K", "folder": "/4k"},
        ])
        self.server.getPies = Mock(side_effect=lambda *args: {"totalFiles": 10})
        libraries = self.server.getLibraries()
        self.assertNotIn("_id", libraries[0])
        self.assertEqual(libraries[1]["_id"], "a")
        self.assertEqual(libraries[2]["folder"], "/4k")


class ButtonTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.library = {"_id": "a", "name": "Movies", "folder": "/movies"}
        self.coordinator = SimpleNamespace(
            data={"libraries": [{"name": "All"}, self.library]},
            last_update_success=True,
            tdarr=SimpleNamespace(scanLibrary=Mock()),
            async_add_listener=Mock(return_value=Mock()),
        )
        self.hass = SimpleNamespace(async_add_executor_job=AsyncMock())
        self.button = buttons.TdarrScanButton(self.coordinator, "entry", self.library)
        self.button.hass = self.hass

    async def test_rename_and_folder_change_keep_identity(self):
        identity = self.button._device_id
        self.library.update(name="Renamed", folder="/new-path")
        self.coordinator.data["libraries"].append(
            {"_id": "b", "name": "Renamed 4K", "folder": "/wrong-path"}
        )
        await self.button.async_press()
        self.hass.async_add_executor_job.assert_awaited_once_with(
            self.coordinator.tdarr.scanLibrary, "a", "/new-path"
        )
        self.assertEqual(identity, self.button._device_id)
        self.assertIn("Renamed", self.button.legacy_name)

    async def test_deleted_or_offline_library_cannot_scan(self):
        self.coordinator.last_update_success = False
        with self.assertRaises(HomeAssistantError):
            await self.button.async_press()
        self.coordinator.last_update_success = True
        self.coordinator.data["libraries"] = []
        with self.assertRaises(HomeAssistantError):
            await self.button.async_press()
        self.hass.async_add_executor_job.assert_not_awaited()

    async def test_request_failure_becomes_home_assistant_error(self):
        self.hass.async_add_executor_job.side_effect = requests.Timeout()
        with self.assertRaises(HomeAssistantError):
            await self.button.async_press()

    async def test_dynamic_discovery_no_aggregate_or_duplicates(self):
        self.hass.data = {"tdarr": {"entry": {"coordinator": self.coordinator}}}
        entry = SimpleNamespace(entry_id="entry", async_on_unload=Mock())
        add = Mock()
        await buttons.async_setup_entry(self.hass, entry, add)
        self.assertEqual(len(add.call_args.args[0]), 1)
        listener = self.coordinator.async_add_listener.call_args.args[0]
        listener()
        self.assertEqual(add.call_count, 1)
        self.coordinator.data["libraries"].append(
            {"_id": "b", "name": "Movies", "folder": "/other"}
        )
        listener()
        self.assertEqual(add.call_count, 2)
        self.assertEqual(add.call_args.args[0][0]._library_id, "b")
        entry.async_on_unload.assert_called_once()

    def test_config_entries_have_distinct_ids(self):
        other = buttons.TdarrScanButton(self.coordinator, "other", self.library)
        self.assertNotEqual(self.button._device_id, other._device_id)


if __name__ == "__main__":
    unittest.main()
