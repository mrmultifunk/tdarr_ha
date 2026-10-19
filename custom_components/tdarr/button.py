"""Buttons for scanning individual Tdarr libraries."""

from requests.exceptions import RequestException

from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from . import TdarrEntity
from .const import COORDINATOR, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a scan button for each library, including newly discovered ones."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    known_ids = set()

    @callback
    def add_new_libraries():
        entities = []
        for library in coordinator.data.get("libraries", []):
            library_id = library.get("_id")
            # The aggregate 'All' statistics entry has no library ID.
            if library_id and library_id not in known_ids:
                known_ids.add(library_id)
                entities.append(
                    TdarrScanButton(coordinator, config_entry.entry_id, library)
                )
        if entities:
            async_add_entities(entities)

    add_new_libraries()
    config_entry.async_on_unload(coordinator.async_add_listener(add_new_libraries))


class TdarrScanButton(TdarrEntity, ButtonEntity):
    """Start a Find new scan without resetting the library's database."""

    _attr_icon = "mdi:folder-search"
    _attr_translation_key = "scan_new_files"

    def __init__(self, coordinator, entry_id, library):
        self._library_id = library["_id"]
        self._library_name = library["name"]
        super().__init__(
            coordinator=coordinator,
            device_id=f"{entry_id}_library_{self._library_id}_scan_new_files",
            name=f"Tdarr {self._library_name} Scan for new files",
        )

    @property
    def library(self):
        """Resolve the current name and folder using the stable library ID."""
        return next(
            (
                library
                for library in self.coordinator.data.get("libraries", [])
                if library.get("_id") == self._library_id
            ),
            None,
        )

    @property
    def legacy_name(self):
        library = self.library
        name = library["name"] if library else self._library_name
        return f"Tdarr {name} Scan for new files"

    @property
    def available(self):
        library = self.library
        return (
            super().available
            and library is not None
            and isinstance(library.get("folder"), str)
            and bool(library["folder"].strip())
        )

    async def async_press(self):
        """Send the scan request outside Home Assistant's event loop."""
        if not self.available:
            raise HomeAssistantError("Tdarr library is unavailable or has no source folder")
        library = self.library
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.tdarr.scanLibrary,
                self._library_id,
                library["folder"],
            )
        except (RequestException, ValueError) as err:
            raise HomeAssistantError("Could not start the Tdarr library scan") from err
