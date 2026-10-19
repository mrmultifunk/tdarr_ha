"""Display changes must not change identities, readings or command semantics."""

import json
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import voluptuous as vol

from test_library_buttons import ROOT, buttons, load_module
import test_library_controls as controls

package = ModuleType("ui_test")
with patch.dict(sys.modules, {
    "ui_test": package,
    "ui_test.const": load_module("ui_test.const", ROOT / "const.py"),
}):
    presentation = load_module("ui_test.presentation", ROOT / "presentation.py")


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.library = {"_id": "lib", "name": "Film", "totalFiles": 12}
        self.node = {"_id": "session1", "nodeName": "Arc-A750", "workers": {}}
        self.coordinator = SimpleNamespace(
            entry_id="entry", serverip="localhost", server_device_id="server-device",
            web_url="http://localhost:8265", last_update_success=True,
            data={"server": {"version": "3.00.00"}, "libraries": [self.library],
                  "nodes": {"session1": self.node}},
        )

    def test_library_entities_share_device_and_preserve_identity(self):
        c = self.coordinator
        entities = [
            controls.sensors.TdarrSensor(c, self.library, {}, "library", "entry"),
            controls.sensors.LibraryStatistic(c, "entry", self.library, "sizeDiff"),
            controls.switches.ProcessLibrarySwitch(c, "entry", self.library),
            buttons.TdarrScanButton(c, "entry", self.library),
        ]
        for entity in entities:
            info = presentation.device_info(entity)
            self.assertEqual(info["identifiers"], {("tdarr", "entry_library_lib")})
            self.assertEqual(info["name"], "Tdarr · Film")
            self.assertEqual(info["via_device_id"], "server-device")
            self.assertEqual(info["configuration_url"], c.web_url)
        self.assertEqual(entities[0].unique_id, "localhost-entry_library_lib_files")
        self.assertEqual(entities[1].unique_id, "localhost-entry_library_lib_sizeDiff")
        self.assertEqual(entities[2].unique_id, "localhost-entry_library_lib_process")
        self.assertEqual(entities[3]._device_id, "entry_library_lib_scan_new_files")
        self.library["name"] = "Film renamed"
        self.assertEqual(presentation.device_info(entities[0])["name"], "Tdarr · Film renamed")
        self.assertEqual(entities[0].unique_id, "localhost-entry_library_lib_files")

    def test_node_grouping_survives_new_session(self):
        status = controls.sensors.TdarrSensor(self.coordinator, self.node, {}, "node", "entry")
        pause = controls.switches.Switch(self.coordinator, self.node, "session1", "entry")
        before = presentation.device_info(status)
        self.coordinator.data["nodes"] = {"session2": {**self.node, "_id": "session2"}}
        self.assertEqual(presentation.device_info(status), before)
        self.assertEqual(before["identifiers"], presentation.device_info(pause)["identifiers"])
        self.assertEqual(status.unique_id, "localhost-entry_node_name_Arc-A750_node")
        self.assertEqual(pause.unique_id, "localhost-entry_node_name_Arc-A750_paused")

    def test_server_and_all_files_keep_original_device(self):
        for kind, value in (("server", {}), ("library", {"name": "All"})):
            entity = controls.sensors.TdarrSensor(self.coordinator, value, {}, kind, "entry")
            info = presentation.device_info(entity)
            self.assertEqual(info["identifiers"], {("tdarr", "localhost")})
            self.assertNotIn("via_device_id", info)

    def test_precision_and_categories_do_not_change_values(self):
        files = controls.sensors.TdarrSensor(self.coordinator, self.library, {}, "library", "entry")
        fps = controls.sensors.TdarrSensor(self.coordinator, self.node, {}, "nodefps", "entry")
        space = controls.sensors.LibraryStatistic(self.coordinator, "entry", self.library, "sizeDiff")
        status = controls.sensors.TdarrSensor(self.coordinator, self.node, {}, "node", "entry")
        schedules = controls.switches.Switch(self.coordinator, {}, "ignoreSchedules", "entry")
        self.assertEqual(files._attr_suggested_display_precision, 0)
        self.assertEqual(files.native_value, 12)
        self.assertEqual(fps._attr_suggested_display_precision, 1)
        self.assertEqual(space._attr_suggested_display_precision, 2)
        self.assertEqual(status._attr_entity_category, "diagnostic")
        self.assertEqual(schedules._attr_entity_category, "config")

    def test_english_text_and_key_coverage_in_both_locales(self):
        english = json.loads((ROOT / "strings.json").read_text())
        self.assertEqual(english, json.loads((ROOT / "translations/en.json").read_text()))
        required = {
            "sensor": set(controls.sensors.SENSORS) | set(controls.sensors.LIBRARY_STATS),
            "switch": {"pauseAll", "ignoreSchedules", "node_paused", "process_library"},
            "button": {"scan_new_files"},
        }
        for lang in ("en", "da"):
            document = json.loads((ROOT / f"translations/{lang}.json").read_text())
            self.assertEqual(document, english)
            for domain, keys in required.items():
                self.assertEqual(keys, set(document["entity"][domain]))
                for key in keys:
                    self.assertTrue(document["entity"][domain][key]["name"])

    def test_web_url_accepts_custom_port_and_rejects_credentials(self):
        for url in ("", "http://192.168.0.117:8265", "https://tdarr.example/path"):
            self.assertEqual(controls.flows.web_url(url), url)
        for url in ("ftp://example", "http://user:secret@example", "not-a-url", "http://host:bad"):
            with self.assertRaises(vol.Invalid):
                controls.flows.web_url(url)
