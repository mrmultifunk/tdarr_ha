"""Entity discovery and migration without changing existing entity IDs."""

from collections import Counter

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

def register_entities(hass, entry, coordinator, async_add_entities, factory, domain):
    """Discover by stable ID and migrate only unambiguous legacy identities."""
    known = set()

    @callback
    def discover():
        candidates = list(factory())
        legacy_counts = Counter(getattr(entity, "legacy_unique_id", None) for entity in candidates)
        registry = er.async_get(hass)
        new = []
        for entity in candidates:
            if entity.unique_id in known:
                continue
            legacy = getattr(entity, "legacy_unique_id", None)
            if legacy and legacy != entity.unique_id and legacy_counts[legacy] == 1:
                old_id = registry.async_get_entity_id(domain, DOMAIN, legacy)
                existing = registry.async_get_entity_id(domain, DOMAIN, entity.unique_id)
                if old_id and not existing:
                    old = registry.async_get(old_id)
                    if old.config_entry_id == entry.entry_id:
                        registry.async_update_entity(old_id, new_unique_id=entity.unique_id)
            known.add(entity.unique_id)
            new.append(entity)
        if new:
            async_add_entities(new)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
