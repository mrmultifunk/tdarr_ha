"""Tdarr node, server and library controls."""

from requests.exceptions import RequestException
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from . import TdarrEntity
from .const import DOMAIN, COORDINATOR, SWITCHES
from .discovery import register_entities
from .nodes import node_name, find_node


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    def entities():
        for node in coordinator.data["nodes"].values():
            yield Switch(coordinator, node, node["_id"], config_entry.entry_id)
        for key in SWITCHES:
            yield Switch(coordinator, {}, key, config_entry.entry_id)
        for library in coordinator.data["libraries"]:
            if library.get("_id"):
                yield ProcessLibrarySwitch(coordinator, config_entry.entry_id, library)

    register_entities(hass, config_entry, coordinator, async_add_entities, entities, "switch")


class Switch(TdarrEntity, SwitchEntity):
    """Pause a node or control a server-wide switch."""

    def __init__(self, coordinator, node, key, entry_id):
        self.object_name = key
        self._node_id = node.get("_id")
        self._node_name = node_name(node) if self._node_id else None
        if key == "pauseAll":
            device_id = "tdarr_pause_all"
        elif key == "ignoreSchedules":
            device_id = "tdarr_ignore_schedules"
        else:
            device_id = f"{entry_id}_node_name_{self._node_name}_paused"
            self.session_unique_prefix = f"{coordinator.serverip}-{entry_id}_node_"
            self.session_unique_suffix = "_paused"
        self.legacy_unique_id = (
            f"{coordinator.serverip}-tdarr_node_{self._node_name}_paused"
            if self._node_id else None
        )
        super().__init__(coordinator=coordinator, device_id=device_id, name=device_id)

    @property
    def node(self):
        return find_node(self.coordinator, self._node_name)

    @property
    def name(self):
        if self._node_id:
            node = self.node or {}
            return f"tdarr_node_{node.get('nodeName', self._node_name)}_paused"
        return self._device_id

    @property
    def available(self):
        return super().available and (self._node_id is None or self.node is not None)

    @property
    def is_on(self):
        if self.object_name in SWITCHES:
            field = "pauseAllNodes" if self.object_name == "pauseAll" else "ignoreSchedules"
            return self.coordinator.data["globalsettings"].get(field)
        node = self.node
        return node.get("nodePaused") if node else None

    @property
    def icon(self):
        return SWITCHES.get(self.object_name, {}).get("icon", "mdi:pause-circle")

    async def _set_state(self, enabled):
        if not self.available:
            raise HomeAssistantError("Tdarr node or server is unavailable")
        try:
            result = await self.hass.async_add_executor_job(
                self.coordinator.tdarr.pauseNode,
                self.node["_id"] if self._node_id else self.object_name,
                enabled
            )
            if result != "OK":
                raise HomeAssistantError("Tdarr rejected the switch command")
        except RequestException as err:
            raise HomeAssistantError("Could not update the Tdarr switch") from err
        # Confirmed writes update cached state immediately, then poll for truth.
        if self._node_id:
            node = self.node
            if node is not None:
                node["nodePaused"] = enabled
        else:
            field = "pauseAllNodes" if self.object_name == "pauseAll" else "ignoreSchedules"
            self.coordinator.data["globalsettings"][field] = enabled
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        await self._set_state(True)

    async def async_turn_off(self, **kwargs):
        await self._set_state(False)


class ProcessLibrarySwitch(TdarrEntity, SwitchEntity):
    """Enable or disable processing for one library, not the whole node."""

    _attr_icon = "mdi:folder-play"

    def __init__(self, coordinator, entry_id, library):
        self._library_id = library["_id"]
        self._library_name = library["name"]
        super().__init__(
            coordinator=coordinator,
            device_id=f"{entry_id}_library_{self._library_id}_process",
            name=f"Tdarr {self._library_name} Process Library",
        )

    @property
    def library(self):
        return next((lib for lib in self.coordinator.data["libraries"]
                     if lib.get("_id") == self._library_id), None)

    @property
    def name(self):
        library = self.library or {}
        return f"Tdarr {library.get('name', self._library_name)} Process Library"

    @property
    def available(self):
        library = self.library
        return (super().available and library is not None
                and isinstance(library.get("processLibrary"), bool))

    @property
    def is_on(self):
        library = self.library
        return library.get("processLibrary") if library else None

    async def _set_state(self, enabled):
        if not self.available:
            raise HomeAssistantError("Tdarr library processing state is unavailable")
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.tdarr.setProcessLibrary, self._library_id, enabled
            )
        except (RequestException, ValueError) as err:
            raise HomeAssistantError("Could not change Tdarr library processing") from err
        library = self.library
        if library is not None:
            library["processLibrary"] = enabled
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        await self._set_state(True)

    async def async_turn_off(self, **kwargs):
        await self._set_state(False)
