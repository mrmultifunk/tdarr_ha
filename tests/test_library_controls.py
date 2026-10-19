"""Regression coverage with mocked HA lifecycle/registry and real HTTP client types."""

import ast
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import requests
import voluptuous as vol

from test_library_buttons import ROOT, api, load_module, HomeAssistantError


class Entity:
    def __init__(self, *, coordinator, device_id, name):
        self.coordinator = coordinator
        self._device_id = device_id
        self.async_write_ha_state = Mock()

    @property
    def unique_id(self):
        return f"{self.coordinator.serverip}-{self._device_id}"

    @property
    def available(self):
        return self.coordinator.last_update_success


class Flow:
    def __init_subclass__(cls, **kwargs):
        pass

    def async_create_entry(self, **kwargs):
        return kwargs

    def async_show_form(self, **kwargs):
        return kwargs


def modules():
    stubs = {name: ModuleType(name) for name in (
        "control_test", "homeassistant", "homeassistant.components",
        "homeassistant.components.switch", "homeassistant.components.sensor",
        "homeassistant.core", "homeassistant.exceptions", "homeassistant.helpers",
        "homeassistant.helpers.entity_registry", "homeassistant.config_entries",
    )}
    stubs["control_test"].TdarrEntity = Entity
    stubs["control_test.const"] = load_module("control_test.const", ROOT / "const.py")
    stubs["control_test.tdarr"] = api
    stubs["control_test.nodes"] = load_module("control_test.nodes", ROOT / "nodes.py")
    stubs["homeassistant.components.switch"].SwitchEntity = type("SwitchEntity", (), {})
    sensor = stubs["homeassistant.components.sensor"]
    sensor.SensorEntity = type("SensorEntity", (), {})
    sensor.SensorDeviceClass = SimpleNamespace(DATA_SIZE="data_size")
    sensor.SensorStateClass = SimpleNamespace(MEASUREMENT="measurement")
    stubs["homeassistant.core"].callback = lambda fn: fn
    stubs["homeassistant.core"].HomeAssistant = object
    stubs["homeassistant.exceptions"].HomeAssistantError = HomeAssistantError
    config = stubs["homeassistant.config_entries"]
    config.ConfigFlow = Flow
    config.OptionsFlow = Flow
    config.ConfigEntry = object
    config.CONN_CLASS_LOCAL_POLL = "local_poll"
    registry = stubs["homeassistant.helpers.entity_registry"]
    registry.async_get = lambda hass: hass.registry
    registry.async_entries_for_config_entry = lambda registry, entry_id: [
        row for row in getattr(registry, "test_entries", [])
        if row.config_entry_id == entry_id
    ]
    with patch.dict(sys.modules, stubs):
        discovery = load_module("control_test.discovery", ROOT / "discovery.py")
        stubs["control_test.discovery"] = discovery
        sys.modules["control_test.discovery"] = discovery
        return (
            load_module("control_test.switch", ROOT / "switch.py"),
            load_module("control_test.sensor", ROOT / "sensor.py"),
            load_module("control_test.config_flow", ROOT / "config_flow.py"),
            discovery,
        )


switches, sensors, flows, discovery = modules()


class ProcessingApiTests(unittest.TestCase):
    @patch.object(api.requests, "post")
    def test_processing_updates_only_exact_library_flag(self, post):
        server = api.Server("localhost", "8265")
        for state in (True, False):
            server.setProcessLibrary("library-id", state)
            self.assertEqual(post.call_args.kwargs["json"], {"data": {
                "collection": "LibrarySettingsJSONDB", "mode": "update",
                "docID": "library-id", "obj": {"processLibrary": state},
            }, "timeout": 20000})
            self.assertEqual(post.call_args.kwargs["timeout"], 30)
        post.return_value.raise_for_status.assert_called()

    @patch.object(api.requests, "post")
    def test_library_processing_failure_propagates(self, post):
        post.return_value.raise_for_status.side_effect = requests.HTTPError()
        with self.assertRaises(requests.HTTPError):
            api.Server("localhost", "8265").setProcessLibrary("id", True)

    def test_every_http_request_has_transport_timeout(self):
        tree = ast.parse((ROOT / "tdarr.py").read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name)
                 and node.func.value.id == "requests"]
        self.assertGreater(len(calls), 10)
        for call in calls:
            self.assertTrue(any(k.arg == "timeout" for k in call.keywords))

    def test_legacy_scan_rejects_partial_and_ambiguous_names(self):
        server = api.Server("localhost", "8265")
        server.getLibraryStats = Mock(return_value=[
            {"_id": "a", "name": "Movies HD"}, {"_id": "b", "name": "Movies 4K"},
        ])
        with patch.object(api.requests, "post") as post:
            self.assertIn("ERROR", server.refreshLibrary("Movies", "scanFindNew", "/movies"))
            post.assert_not_called()


class ControlTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.library = {"_id": "a", "name": "Movies", "folder": "/movies",
                        "processLibrary": True, "totalFiles": 7, "sizeDiff": -1.234,
                        "totalTranscodeCount": 5, "totalHealthCheckCount": 4}
        self.node = {"_id": "n1", "nodeName": "GPU", "nodePaused": False, "workers": {}}
        self.coordinator = SimpleNamespace(
            serverip="localhost", last_update_success=True,
            data={"libraries": [{"name": "All", "totalFiles": 7}, self.library],
                  "nodes": {"n1": self.node}, "globalsettings": {"pauseAllNodes": False},
                  "server": {}, "stats": {}, "staged": {}},
            tdarr=SimpleNamespace(setProcessLibrary=Mock(), pauseNode=Mock()),
            async_request_refresh=AsyncMock(), async_add_listener=Mock(return_value=Mock()),
        )
        self.hass = SimpleNamespace(async_add_executor_job=AsyncMock())

    async def test_process_switch_write_and_external_updates(self):
        entity = switches.ProcessLibrarySwitch(self.coordinator, "entry", self.library)
        entity.hass = self.hass
        await entity.async_turn_off()
        self.hass.async_add_executor_job.assert_awaited_once_with(
            self.coordinator.tdarr.setProcessLibrary, "a", False)
        self.assertFalse(entity.is_on)
        self.coordinator.async_request_refresh.assert_awaited_once()
        self.library["processLibrary"] = True
        self.assertTrue(entity.is_on)

    async def test_process_failure_does_not_change_state(self):
        entity = switches.ProcessLibrarySwitch(self.coordinator, "entry", self.library)
        entity.hass = self.hass
        self.hass.async_add_executor_job.side_effect = requests.Timeout()
        with self.assertRaises(HomeAssistantError):
            await entity.async_turn_off()
        self.assertTrue(entity.is_on)
        entity.async_write_ha_state.assert_not_called()

    async def test_unknown_processing_flag_cannot_be_changed(self):
        entity = switches.ProcessLibrarySwitch(self.coordinator, "entry", self.library)
        entity.hass = self.hass
        self.library.pop("processLibrary")
        self.assertFalse(entity.available)
        with self.assertRaises(HomeAssistantError):
            await entity.async_turn_on()
        self.hass.async_add_executor_job.assert_not_awaited()

    async def test_existing_pause_switch_failure_is_visible(self):
        entity = switches.Switch(self.coordinator, self.node, "n1", "entry")
        entity.hass = self.hass
        self.hass.async_add_executor_job.return_value = "ERROR"
        with self.assertRaises(HomeAssistantError):
            await entity.async_turn_on()
        self.assertFalse(entity.is_on)

    def test_statistics_rename_negative_reset_missing_and_deleted(self):
        saved = sensors.LibraryStatistic(self.coordinator, "entry", self.library, "sizeDiff")
        count = sensors.LibraryStatistic(self.coordinator, "entry", self.library, "totalTranscodeCount")
        self.assertEqual(saved.native_value, -1.23)
        self.assertEqual(count.native_value, 5)
        identity = saved.unique_id
        self.library["name"] = "Renamed"
        self.assertIn("Renamed", saved.name)
        self.assertEqual(saved.unique_id, identity)
        self.library["totalTranscodeCount"] = 0
        self.assertEqual(count.native_value, 0)
        self.library.pop("sizeDiff")
        self.assertIsNone(saved.native_value)
        self.coordinator.data["libraries"] = []
        self.assertFalse(count.available)

    def test_existing_file_sensor_matches_id_after_rename(self):
        original = dict(self.library)
        entity = sensors.TdarrSensor(self.coordinator, original, {}, "library", "entry")
        self.library["name"] = "New name"
        self.library["totalFiles"] = 12
        self.assertEqual(entity.native_value, 12)
        self.assertIn("New name", entity.name)
        self.assertEqual(entity.legacy_unique_id, "localhost-tdarr_library_Movies")

    async def test_replace_node_same_count_and_migrate_entity_id(self):
        registry = Mock()
        registry.test_entries = []
        registry.async_get_entity_id.side_effect = lambda domain, platform, uid: (
            "sensor.my_gpu" if uid == "localhost-tdarr_node_GPU" else None)
        registry.async_get.return_value = SimpleNamespace(config_entry_id="entry")
        self.hass.registry = registry
        self.hass.data = {"tdarr": {"entry": {"coordinator": self.coordinator}}}
        entry = SimpleNamespace(entry_id="entry", options={}, async_on_unload=Mock())
        add = Mock()
        await sensors.async_setup_entry(self.hass, entry, add)
        registry.async_update_entity.assert_called_once_with(
            "sensor.my_gpu", new_unique_id="localhost-entry_node_name_GPU_node")
        first = add.call_args.args[0]
        old_node = next(e for e in first if getattr(e, "type", None) == "node")
        self.coordinator.data["nodes"] = {"n2": {"_id": "n2", "nodeName": "Replacement"}}
        listener = self.coordinator.async_add_listener.call_args.args[0]
        listener()
        self.assertEqual(len(add.call_args.args[0]), 2)
        self.assertFalse(old_node.available)
        listener()
        self.assertEqual(add.call_count, 2)


class OptionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_options_save_interval_key_without_mutating_connection(self):
        flow = flows.OptionsFlow()
        data = {"serverip": "localhost", "serverport": "8265", "apikey": "old"}
        flow.config_entry = SimpleNamespace(data=data, options={"other": "preserved"})
        result = await flow.async_step_init({"update_interval": 15, "apikey": " new "})
        self.assertEqual(result["data"], {"other": "preserved", "update_interval": 15, "apikey": "new"})
        self.assertEqual(data["apikey"], "old")
        self.assertEqual(data["serverport"], "8265")

    async def test_interval_schema_rejects_zero_and_recovers_old_saved_interval(self):
        flow = flows.OptionsFlow()
        flow.config_entry = SimpleNamespace(data={"update_interval": 45}, options={})
        form = await flow.async_step_init()
        self.assertEqual(form["data_schema"]({})["update_interval"], 45)
        with self.assertRaises(vol.Invalid):
            form["data_schema"]({"update_interval": 0})
