"""Regressions for node sessions, existing registry entries and poll failures."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, AsyncMock

import requests

import test_library_controls as controls
from test_library_controls import sensors, switches, discovery
from test_library_buttons import ROOT, load_module

polling = load_module("polling_tests", ROOT / "polling.py")


class NodeRecoveryTests(unittest.IsolatedAsyncioTestCase):
    setUp = controls.ControlTests.setUp

    async def test_restart_reuses_entities_and_targets_current_session(self):
        registry = Mock()
        registry.test_entries = []
        registry.async_get_entity_id.return_value = None
        self.hass.registry = registry
        self.hass.data = {"tdarr": {"entry": {"coordinator": self.coordinator}}}
        entry = SimpleNamespace(entry_id="entry", options={}, async_on_unload=Mock())
        add = Mock()
        await sensors.async_setup_entry(self.hass, entry, add)
        status = next(e for e in add.call_args.args[0] if getattr(e, "type", None) == "node")
        fps = next(e for e in add.call_args.args[0] if getattr(e, "type", None) == "nodefps")
        pause = switches.Switch(self.coordinator, self.node, "n1", "entry")
        pause.hass = self.hass
        self.hass.async_add_executor_job.return_value = "OK"
        listener = self.coordinator.async_add_listener.call_args.args[0]
        for session in ("n2", "n3", "n4"):
            self.coordinator.data["nodes"] = {session: {
                "_id": session, "nodeName": "GPU", "nodePaused": False,
                "workers": {"worker": {"fps": 42}},
            }}
            listener()
            self.assertEqual(add.call_count, 1)
            self.assertTrue(status.available)
            self.assertEqual(status.native_value, "Online")
            self.assertEqual(fps.native_value, 42)
            await pause.async_turn_on()
            self.hass.async_add_executor_job.assert_awaited_with(
                self.coordinator.tdarr.pauseNode, session, True)

    def test_duplicate_live_names_are_not_controllable(self):
        pause = switches.Switch(self.coordinator, self.node, "n1", "entry")
        self.coordinator.data["nodes"]["other"] = {"_id": "other", "nodeName": "GPU"}
        self.assertFalse(pause.available)

    def test_repair_oldest_entity_preserves_entity_id_and_keeps_duplicates(self):
        entity = sensors.TdarrSensor(self.coordinator, self.node, {}, "node", "entry")
        def row(session, entity_id, created, config="entry", name="tdarr_node_GPU"):
            return SimpleNamespace(
                config_entry_id=config, platform="tdarr", entity_id=entity_id,
                unique_id=f"localhost-entry_node_{session}_node",
                original_name=name, created_at=created,
            )
        registry = Mock()
        registry.async_get_entity_id.return_value = None
        registry.test_entries = [
            row("n3", "sensor.gpu_3", "2026-10-19"),
            row("n1", "sensor.gpu", "2026-10-17"),
            row("n2", "sensor.gpu_2", "2026-10-18"),
            row("other", "sensor.wrong_server", "2020-01-01", config="different"),
            row("other", "sensor.wrong_node", "2020-01-01", name="tdarr_node_Other"),
        ]
        discovery.repair_node_identity(registry, SimpleNamespace(entry_id="entry"), entity, "sensor")
        registry.async_update_entity.assert_called_once_with(
            "sensor.gpu", new_unique_id=entity.unique_id)
        registry.async_remove.assert_not_called()


class PollingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.server = SimpleNamespace(**{
            name: Mock(return_value=[] if name == "getLibraries" else {}, __name__=name)
            for name in ("getStatus", "getNodes", "getStats", "getStaged", "getLibraries", "getSettings")
        })
        async def executor(method):
            return method()
        self.hass = SimpleNamespace(async_add_executor_job=executor)

    async def test_transient_timeout_retries_only_failed_read(self):
        self.server.getNodes.side_effect = [requests.Timeout("secret payload"), {}]
        result = await polling.poll_data(self.hass, self.server)
        self.assertEqual(result["nodes"], {})
        self.assertEqual(self.server.getNodes.call_count, 2)
        self.server.getStatus.assert_called_once()

    async def test_persistent_failure_reports_operation_without_secrets(self):
        self.server.getStats.side_effect = requests.Timeout("apikey=secret")
        with self.assertRaisesRegex(polling.PollError, "getStats: Timeout") as caught:
            await polling.poll_data(self.hass, self.server)
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(self.server.getStats.call_count, 2)

    async def test_auth_failure_not_retried(self):
        response = requests.Response()
        response.status_code = 401
        self.server.getStatus.side_effect = requests.HTTPError("secret", response=response)
        with self.assertRaisesRegex(polling.PollError, "getStatus: HTTP 401"):
            await polling.poll_data(self.hass, self.server)
        self.server.getStatus.assert_called_once()

    async def test_bad_response_type_is_not_reported_as_network_failure(self):
        self.server.getNodes.return_value = []
        with self.assertRaisesRegex(polling.PollError, "getNodes: unexpected response type"):
            await polling.poll_data(self.hass, self.server)

    async def test_settings_server_error_body_never_logged(self):
        self.server.getSettings.return_value = {"status": "ERROR", "status_code": 503, "message": "secret"}
        with self.assertRaisesRegex(polling.PollError, "getSettings: HTTP 503") as caught:
            await polling.poll_data(self.hass, self.server)
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(self.server.getSettings.call_count, 2)
