"""Regression tests for connectivity, activity and read-only release checks."""

import sys
from datetime import timedelta
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import requests

from test_library_buttons import ROOT, load_module
from test_library_controls import Entity, discovery
from test_presentation import presentation


class Coordinator:
    def __init__(self, hass, *args, **kwargs):
        self.hass = hass
        self.data = None
        self.last_update_success = True

    def async_set_updated_data(self, data):
        self.data = data


stubs = {name: ModuleType(name) for name in (
    "server_test", "homeassistant", "homeassistant.components",
    "homeassistant.components.binary_sensor", "homeassistant.components.update",
    "homeassistant.const", "homeassistant.helpers",
    "homeassistant.helpers.update_coordinator",
)}
stubs["server_test"].TdarrEntity = Entity
for name in ("const", "nodes", "polling", "releases"):
    stubs[f"server_test.{name}"] = load_module(f"server_test.{name}", ROOT / f"{name}.py")
stubs["server_test.discovery"] = discovery
stubs["homeassistant.const"].EntityCategory = SimpleNamespace(DIAGNOSTIC="diagnostic")
binary = stubs["homeassistant.components.binary_sensor"]
binary.BinarySensorEntity = type("BinarySensorEntity", (), {})
binary.BinarySensorDeviceClass = SimpleNamespace(CONNECTIVITY="connectivity", RUNNING="running")
stubs["homeassistant.components.update"].UpdateEntity = type("UpdateEntity", (), {})
helpers = stubs["homeassistant.helpers.update_coordinator"]
helpers.DataUpdateCoordinator = Coordinator
helpers.UpdateFailed = type("UpdateFailed", (Exception,), {})
with patch.dict(sys.modules, stubs):
    sensors = load_module("server_test.binary_sensor", ROOT / "binary_sensor.py")
    updates = load_module("server_test.update", ROOT / "update.py")
    status_module = load_module("server_test.server_status", ROOT / "server_status.py")
releases = stubs["server_test.releases"]


class ServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hass = SimpleNamespace(async_add_executor_job=AsyncMock())
        self.local = SimpleNamespace(
            entry_id="entry", serverip="host", update_interval=timedelta(seconds=60),
            last_update_success=True, tdarr=SimpleNamespace(getStatus=Mock()),
            web_url="http://host:8265", server_device_id="server",
            data={"server": {"status": "good", "version": "3.00.00"}, "nodes": {}},
        )
        self.status = status_module.ServerStatusCoordinator(self.hass, self.local)

    async def test_connection_failure_recovery_and_safe_attributes(self):
        entity = sensors.ServerConnection(self.local, self.status)
        self.local.last_update_success = False  # Failure of unrelated stats endpoint.
        self.assertTrue(entity.available)
        self.assertTrue(entity.is_on)
        self.hass.async_add_executor_job.side_effect = requests.Timeout("secret-token")
        self.status.data = await self.status._async_update_data()
        self.assertTrue(entity.available)
        self.assertFalse(entity.is_on)
        self.assertEqual(entity.extra_state_attributes["error"], "Timeout")
        self.assertEqual(entity.extra_state_attributes["version"], "3.00.00")
        self.assertNotIn("secret-token", str(entity.extra_state_attributes))
        self.hass.async_add_executor_job.side_effect = None
        self.hass.async_add_executor_job.return_value = {"status": "good", "apiKey": "hidden"}
        self.status.data = await self.status._async_update_data()
        self.assertTrue(entity.is_on)
        self.assertNotIn("apiKey", entity.extra_state_attributes)

    async def test_invalid_status_response_is_disconnected(self):
        for response in ([], {}, {"status": "ERROR"}):
            self.hass.async_add_executor_job.return_value = response
            self.assertFalse((await self.status._async_update_data())["connected"])

    def test_activity_and_node_identity(self):
        node = {"_id": "session1", "nodeName": "GPU", "workers": {}}
        self.local.data["nodes"] = {"session1": node}
        entity = sensors.ProcessingActive(self.local, node)
        self.assertFalse(entity.is_on)
        self.assertEqual(presentation.device_info(entity)["identifiers"],
                         {("tdarr", "entry_node_name_GPU")})
        before = entity.unique_id
        node["workers"] = {"w": {"idle": False, "fps": 0}}
        self.local.data["nodes"] = {"session2": {**node, "_id": "session2"}}
        self.assertTrue(entity.is_on)
        self.assertEqual(entity.unique_id, before)
        for workers, expected in (({"w": {"idle": True}}, False),
                                  ({"w": {"fps": 10}}, None), (None, None)):
            self.assertIs(sensors.worker_activity(workers), expected)
        self.local.data["nodes"] = {}
        self.assertFalse(entity.available)

    def test_release_comparison_and_no_install(self):
        remote = SimpleNamespace(data="3.01.00", last_update_success=True)
        entity = updates.ServerUpdate(self.local, self.status, remote)
        self.assertEqual(entity._attr_supported_features, 0)
        self.assertTrue(entity.available)
        self.assertTrue(entity.version_is_newer("3.01.00", "3.00.00"))
        self.assertFalse(entity.version_is_newer("3.01.00", "3.02.00"))
        self.assertTrue(entity.version_is_newer("2.100.00", "2.99.00"))
        remote.last_update_success = False
        self.assertFalse(entity.available)
        self.assertTrue(sensors.ServerConnection(self.local, self.status).is_on)
        remote.last_update_success = True
        self.status.data["details"]["version"] = "dev_3.02.00"
        self.assertFalse(entity.available)

    def test_manifest_validation_and_no_local_credentials(self):
        package = {"linux_x64": {"Tdarr_Server": "https://example/server.zip"}}
        manifest = {"3.00.00": package, "3.01.00": package, "dev_4.00.00": package,
                    "9.00.00": {"linux_x64": {"Tdarr_Node": "node.zip"}}}
        self.assertEqual(releases.latest_stable(manifest), "3.01.00")
        for invalid in ({}, [], {"latest": package}):
            with self.assertRaises(ValueError):
                releases.latest_stable(invalid)
        with patch.object(releases.requests, "get") as get:
            get.return_value.json.return_value = manifest
            self.assertEqual(releases.fetch_latest(), "3.01.00")
            get.assert_called_once_with(releases.VERSIONS_URL, timeout=10)
            get.return_value.raise_for_status.assert_called_once()
