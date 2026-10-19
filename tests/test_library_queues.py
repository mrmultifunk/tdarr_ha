"""Per-library file statuses must not inherit server or other library totals."""

from types import SimpleNamespace
import unittest

from test_library_controls import sensors
from test_presentation import presentation


class LibraryQueueTests(unittest.TestCase):
    def test_status_names_and_independent_libraries(self):
        first = {"_id": "one", "name": "Movies", "status": {
            "transcode": [{"name": "Queued", "value": 8},
                          {"name": "Transcode error", "value": 12},
                          {"name": "Hold", "value": 3}],
            "healthCheck": [{"name": "Queued", "value": 5},
                            {"name": "Error", "value": 18}]}}
        second = {"_id": "two", "name": "TV", "status": {
            "transcode": [{"name": "Queued", "value": 99}]}}
        coordinator = SimpleNamespace(
            serverip="host", entry_id="entry", last_update_success=True,
            web_url="http://host", server_device_id="server",
            data={"libraries": [first, second], "stats": {"table1Count": 999}})
        for key, expected in (("transcode_queue", 8), ("transcode_errors", 12),
                              ("transcode_hold", 3), ("health_check_queue", 5),
                              ("health_check_errors", 18)):
            entity = sensors.LibraryStatistic(coordinator, "entry", first, key)
            self.assertEqual(entity.native_value, expected)
            self.assertEqual(presentation.device_info(entity)["identifiers"],
                             {("tdarr", "entry_library_one")})
            self.assertTrue(entity._attr_entity_registry_enabled_default)
        queue = sensors.LibraryStatistic(coordinator, "entry", second, "transcode_queue")
        identity = queue.unique_id
        self.assertEqual(queue.native_value, 99)
        second["name"] = "Renamed TV"
        self.assertEqual(queue.unique_id, identity)
        coordinator.data["libraries"] = [first]
        self.assertFalse(queue.available)
        self.assertIsNone(queue.native_value)
        optional = sensors.LibraryStatistic(coordinator, "entry", first, "transcode_success")
        self.assertFalse(optional._attr_entity_registry_enabled_default)

    def test_empty_and_missing_are_different(self):
        count = sensors.library_status_count
        self.assertEqual(count({"status": {"transcode": []}}, "transcode", "queued"), 0)
        for data in ({}, {"status": None}, {"status": {}},
                     {"status": {"transcode": {}}}):
            self.assertIsNone(count(data, "transcode", "queued"))

    def test_labels_and_invalid_values(self):
        count = sensors.library_status_count
        for name in ("Queued", " queued ", "Transcode queued"):
            self.assertEqual(count({"status": {"transcode": [
                {"name": name, "value": 8.0}]}}, "transcode", "queued"), 8)
        for value in (None, True, "8", -1, float("nan"), float("inf")):
            self.assertIsNone(count({"status": {"transcode": [
                {"name": "Queued", "value": value}]}}, "transcode", "queued"))
        self.assertEqual(count({"status": {"transcode": [
            {"name": "Future status", "value": 10}]}}, "transcode", "queued"), 0)
