"""Server connectivity and node activity."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from . import TdarrEntity
from .const import COORDINATOR, DOMAIN
from .discovery import register_entities
from .nodes import find_node, node_name


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[COORDINATOR]
    async_add_entities([ServerConnection(coordinator, data["server_status"])])

    def entities():
        for node in coordinator.data.get("nodes", {}).values():
            yield ProcessingActive(coordinator, node)

    register_entities(hass, entry, coordinator, async_add_entities, entities, "binary_sensor")


class ServerConnection(TdarrEntity, BinarySensorEntity):
    _attr_translation_key = "server_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, status):
        super().__init__(coordinator=coordinator, device_id=f"{coordinator.entry_id}_connection",
                         name="Server connection")
        self.status = status

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.status.async_add_listener(self.async_write_ha_state))

    @property
    def available(self):
        return self.status.data is not None

    @property
    def is_on(self):
        return self.status.data["connected"]

    @property
    def extra_state_attributes(self):
        data = self.status.data
        attrs = {key: data["details"][key] for key in
                 ("status", "version", "uptime", "os", "isProduction")
                 if key in data["details"]}
        return {**attrs, "last_success": data["last_success"], "error": data["error"]}


def worker_activity(workers):
    """Use Tdarr's idle flag; missing/unsupported payloads remain unknown."""
    if not isinstance(workers, dict):
        return None
    activity = [not worker["idle"] if isinstance(worker, dict)
                and isinstance(worker.get("idle"), bool) else None
                for worker in workers.values()]
    if True in activity:
        return True
    return None if None in activity else False


class ProcessingActive(TdarrEntity, BinarySensorEntity):
    _attr_translation_key = "processing_active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, node):
        self._node_name = node_name(node)
        super().__init__(coordinator=coordinator,
                         device_id=f"{coordinator.entry_id}_node_name_{self._node_name}_processing_active",
                         name="Processing active")

    @property
    def available(self):
        return super().available and find_node(self.coordinator, self._node_name) is not None

    @property
    def is_on(self):
        node = find_node(self.coordinator, self._node_name)
        return worker_activity(node.get("workers")) if node else None

    @property
    def extra_state_attributes(self):
        node = find_node(self.coordinator, self._node_name)
        workers = node.get("workers") if node else None
        if not isinstance(workers, dict):
            return {}
        return {"active_workers": sum(isinstance(w, dict) and w.get("idle") is False
                                      for w in workers.values()),
                "worker_count": len(workers)}
