"""Read-only Tdarr server release notifications. Installation is external."""

from datetime import timedelta
import logging

from homeassistant.components.update import UpdateEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import TdarrEntity
from .const import COORDINATOR, DOMAIN
from .polling import error_reason
from .releases import fetch_latest, version_key, RELEASE_URL


class ReleaseCoordinator(DataUpdateCoordinator):
    def __init__(self, hass):
        super().__init__(hass, logging.getLogger(__name__), name="tdarr_releases",
                         update_interval=timedelta(hours=6))

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(fetch_latest)
        except Exception as err:
            raise UpdateFailed(f"Tdarr release check: {error_reason(err)}") from err


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    releases = ReleaseCoordinator(hass)
    # An Internet outage must not prevent setup of the local integration.
    await releases.async_refresh()
    async_add_entities([ServerUpdate(data[COORDINATOR], data["server_status"], releases)])


class ServerUpdate(TdarrEntity, UpdateEntity):
    _attr_translation_key = "server_update"
    _attr_supported_features = 0
    _attr_release_url = RELEASE_URL
    _attr_title = "Tdarr Server"

    def __init__(self, coordinator, status, releases):
        super().__init__(coordinator=coordinator, device_id=f"{coordinator.entry_id}_server_update",
                         name="Server update")
        self.status = status
        self.releases = releases

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        for coordinator in (self.status, self.releases):
            self.async_on_remove(coordinator.async_add_listener(self.async_write_ha_state))

    @property
    def available(self):
        return (self.status.data["connected"] and self.releases.last_update_success
                and version_key(self.installed_version) is not None)

    @property
    def installed_version(self):
        return self.status.data["details"].get("version")

    @property
    def latest_version(self):
        return self.releases.data

    def version_is_newer(self, latest_version, installed_version):
        latest, installed = version_key(latest_version), version_key(installed_version)
        return latest is not None and installed is not None and latest > installed
