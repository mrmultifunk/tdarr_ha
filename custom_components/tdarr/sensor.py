import logging
import math

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass
)

from . import TdarrEntity
from .const import DOMAIN, COORDINATOR, SENSORS
from .discovery import register_entities
from .nodes import node_name, find_node
from homeassistant.const import EntityCategory

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Discover nodes and libraries by ID without reloading the integration."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    def entities():
        for key, value in SENSORS.items():
            if value.get("type") == "single":
                yield TdarrSensor(coordinator, coordinator.data[value["entry"]],
                                  config_entry.options, key, config_entry.entry_id)
        for library in coordinator.data["libraries"]:
            yield TdarrSensor(coordinator, library, config_entry.options,
                              "library", config_entry.entry_id)
            if library.get("_id"):
                for key in LIBRARY_STATS:
                    yield LibraryStatistic(coordinator, config_entry.entry_id, library, key)
        for node in coordinator.data["nodes"].values():
            for key in ("node", "nodefps"):
                yield TdarrSensor(coordinator, node, config_entry.options,
                                  key, config_entry.entry_id)

    register_entities(hass, config_entry, coordinator, async_add_entities, entities, "sensor")


class TdarrSensor(
    TdarrEntity,
    SensorEntity,
):
    def __init__(self, coordinator, sensor, options, type, entry_id):

        self.sensor = sensor
        self.tdarroptions = options
        self.type = type
        self._attr_translation_key = type
        if type == "node":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        else:
            self._attr_suggested_display_precision = (
                2 if type == "stats_spacesaved" else
                1 if type in ("nodefps", "stats_totalfps") else 0
            )
        self._attr = {}
        self.coordinator = coordinator
        if self.type == "node":
            if "nodeName" in self.sensor:
                self._device_id = "tdarr_node_" + self.sensor.get("nodeName", "")
            else:
                self._device_id = "tdarr_node_" + self.sensor.get("_id", "")
        elif self.type == "nodefps":
            if "nodeName" in self.sensor:
                self._device_id = "tdarr_node_" + self.sensor.get("nodeName","") + "_fps"
            else:
                self._device_id = "tdarr_node_" + self.sensor.get("_id", "") + "_fps"
        elif self.type == "library":
            self._device_id = "tdarr_library_" + self.sensor["name"]
        else:
            self._device_id = "tdarr_" + self.type
        self.legacy_unique_id = f"{coordinator.serverip}-{self._device_id}"
        if type in ("node", "nodefps"):
            self._node_name = node_name(sensor)
            self._device_id = f"{entry_id}_node_name_{self._node_name}_{type}"
            self.session_unique_prefix = f"{coordinator.serverip}-{entry_id}_node_"
            self.session_unique_suffix = f"_{type}"
        elif type == "library" and sensor.get("_id"):
            self._device_id = f"{entry_id}_library_{sensor['_id']}_files"
        super().__init__(coordinator=coordinator, device_id=self._device_id, name=self.legacy_name)


    def get_value(self, ftype):
        if ftype == "state":
            if self.type == "node":
                return "Online"
            elif self.type == "nodefps":
                fps = 0
                for key1, value in (find_node(self.coordinator, self._node_name) or {}).get("workers", {}).items():
                    fps += value.get("fps", 0)
                return fps
            elif self.type == "stats_spacesaved":
                return round(self.coordinator.data.get("stats",{}).get("sizeDiff", 0), 2)
            elif self.type == "stats_transcodefilesremaining":
                return self.coordinator.data.get("stats",{}).get("table1Count", 0)
            elif self.type == "stats_transcodedcount":
                return self.coordinator.data.get("stats",{}).get("table2Count", 0)
            elif self.type == "stats_stagedcount":
                return self.coordinator.data.get("staged",{}).get("totalCount", 0)
            elif self.type == "stats_healthcount":
                return self.coordinator.data.get("stats",{}).get("table4Count", 0)
            elif self.type == "stats_transcodeerrorcount":
                return self.coordinator.data.get("stats",{}).get("table3Count", 0)
            elif self.type == "stats_healtherrorcount":
                return self.coordinator.data.get("stats",{}).get("table6Count", 0)
            elif self.type == "library":
                libraries = self.coordinator.data.get("libraries",{})
                for library in libraries:
                    if library.get("_id") == self.sensor.get("_id"):
                        _LOGGER.debug(library)
                        return library["totalFiles"]

            elif self.type == "stats_totalfps":
                fps = 0
                for key1, value1 in self.coordinator.data["nodes"].items():
                    for key2, value2 in value1.get("workers", {}).items():
                        fps += value2.get("fps", 0)
                return fps

        if ftype == "attributes":
            if self.type == "node":
                return (find_node(self.coordinator, self._node_name) or {})
            elif self.type == "stats_spacesaved":
                return self.coordinator.data.get("stats", {})
            elif self.type == "library":
                libraries = self.coordinator.data.get("libraries",{})
                for library in libraries:
                    if library.get("_id") == self.sensor.get("_id"):
                        data = {}
                        data["Total Files"] = library["totalFiles"]
                        data["Number of Transcodes"] = library["totalTranscodeCount"]
                        data["Space Saved (GB)"] = round(library["sizeDiff"], 0)
                        data["Number of Health Checks"] = library["totalHealthCheckCount"]
                        codecs = {}
                        for codec in library.get("video", {}).get("codecs", {}):
                            codecs[codec["name"]] = codec["value"]
                        data["Codecs"] = codecs
                        containers = {}
                        for container in library.get("video", {}).get("containers", {}):
                            containers[container["name"]] = container["value"]
                        data["Containers"] = containers
                        qualities = {}
                        for quality in library.get("video", {}).get("resolutions", {}):
                            qualities[quality["name"]] = quality["value"]
                        data["Resolutions"] = qualities
                        return data
            else:
                return None

    @property
    def legacy_name(self):
        if self.type in ("node", "nodefps"):
            suffix = "_fps" if self.type == "nodefps" else ""
            return f"tdarr_node_{self._node_name}{suffix}"
        elif self.type == "library":
            library = next((lib for lib in self.coordinator.data["libraries"]
                            if lib.get("_id") == self.sensor.get("_id")), self.sensor)
            return "tdarr_library_" + library["name"]
        else:
            return "tdarr_" + self.type


    @property
    def available(self):
        if not super().available:
            return False
        if self.type in ("node", "nodefps"):
            return find_node(self.coordinator, self._node_name) is not None
        if self.type == "library":
            return any(lib.get("_id") == self.sensor.get("_id")
                       for lib in self.coordinator.data["libraries"])
        return True

    @property
    def device_id(self):
        return self._device_id
    
    @property 
    def native_value(self):
        return self.get_value("state")


    @property
    def extra_state_attributes(self):
        return self.get_value("attributes")

    @property
    def native_unit_of_measurement(self):
        return SENSORS.get(self.type, {}).get("unit_of_measurement", None)

    @property
    def device_class(self):
        return SENSORS.get(self.type, {}).get("device_class", None)

    @property
    def icon(self):
        return SENSORS.get(self.type, {}).get("icon", None)
    
    @property
    def state_class(self):
        return None

# These are cumulative snapshots, not monotonically increasing meters: Tdarr
# allows stats to be reset and space savings can be negative.
LIBRARY_STATS = {
    "sizeDiff": ("Space saved", "GB", "mdi:harddisk", SensorDeviceClass.DATA_SIZE),
    "totalTranscodeCount": ("Transcodes", None, "mdi:video-check", None),
    "totalHealthCheckCount": ("Health checks", None, "mdi:check-decagram", None),
}


# Current file states from get-pies, distinct from lifetime operation counts.
LIBRARY_STATUS = {
    "transcode_queue": ("transcode", "queued", "Transcode queue", True),
    "transcode_errors": ("transcode", "error", "Transcode errors", True),
    "transcode_hold": ("transcode", "hold", "Transcode on hold", True),
    "transcode_success": ("transcode", "success", "Transcode successful files", False),
    "transcode_not_required": ("transcode", "not required", "Transcode not required", False),
    "transcode_ignored": ("transcode", "ignored", "Transcode ignored", False),
    "transcode_cancelled": ("transcode", "cancelled", "Transcode cancelled", False),
    "health_check_queue": ("healthCheck", "queued", "Health check queue", True),
    "health_check_errors": ("healthCheck", "error", "Health check errors", True),
    "health_check_success": ("healthCheck", "success", "Health check healthy files", False),
    "health_check_cancelled": ("healthCheck", "cancelled", "Health check cancelled", False),
}
LIBRARY_STATS.update({key: (label, "files", "mdi:file-multiple", None)
                      for key, (_, _, label, _) in LIBRARY_STATUS.items()})


def library_status_count(library, kind, status):
    """Missing/invalid breakdowns are unknown; omitted slices in valid lists are zero."""
    breakdown = library.get("status")
    rows = breakdown.get(kind) if isinstance(breakdown, dict) else None
    if not isinstance(rows, list):
        return None
    total = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            return None
        value = row.get("value")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            return None
        name = row["name"].strip().lower()
        if kind == "transcode":
            name = name.removeprefix("transcode").strip()
        if name == status:
            total += value
    return total


class LibraryStatistic(TdarrEntity, SensorEntity):
    """Expose existing library statistics as recorder-friendly numeric sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id, library, key):
        self._library_id = library["_id"]
        self._library_name = library["name"]
        self._key = key
        self._attr_translation_key = key
        if key in LIBRARY_STATUS:
            self._attr_entity_registry_enabled_default = LIBRARY_STATUS[key][3]
        self._attr_suggested_display_precision = 2 if key == "sizeDiff" else 0
        label, unit, icon, device_class = LIBRARY_STATS[key]
        self._label = label
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        super().__init__(
            coordinator=coordinator,
            device_id=f"{entry_id}_library_{self._library_id}_{key}",
            name=f"Tdarr {self._library_name} {label}",
        )

    @property
    def library(self):
        return next((lib for lib in self.coordinator.data["libraries"]
                     if lib.get("_id") == self._library_id), None)

    @property
    def legacy_name(self):
        library = self.library or {}
        return f"Tdarr {library.get('name', self._library_name)} {self._label}"

    @property
    def available(self):
        return super().available and self.library is not None

    @property
    def native_value(self):
        library = self.library or {}
        if self._key in LIBRARY_STATUS:
            kind, status, _, _ = LIBRARY_STATUS[self._key]
            return library_status_count(library, kind, status)
        value = library.get(self._key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        return round(value, 2) if self._key == "sizeDiff" else value
