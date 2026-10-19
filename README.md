# Tdarr Home Assistant Integration

## This fork

Based on [itchannel/tdarr_ha](https://github.com/itchannel/tdarr_ha).

### 1.20.1: English interface

Integration-provided names, settings and messages are now English, including
when Home Assistant uses Danish. The Danish locale intentionally uses the same
English text to keep the interface consistent. User-assigned names and library
or node names from Tdarr are preserved, as are all entity IDs.

### 1.20.0: clearer devices and controls

The integration now groups existing entities into separate devices:

| Device | Contents |
| --- | --- |
| Tdarr Server | Global controls and aggregate statistics |
| Tdarr · node name | Pause, speed and diagnostic status |
| Tdarr · library name | Scan, processing, file count and library statistics |

Controls have short English names using Home Assistant's entity translation
mechanism; user-assigned names remain in place. Server/node status appears under diagnostics,
and Ignore schedules under configuration. Counts suggest zero decimals, speed one
decimal, and saved space two decimals. Values, units and switch direction do not
change: **Pause processing ON means paused**, while **Processing enabled ON means
the library can be processed**.

Every device links to the Tdarr web interface. The configured server address is
used by default; an optional **Web interface URL** in integration options supports
a different web port or reverse proxy without changing the API connection.

Existing unique IDs and entity IDs are retained, including the 1.19.1 node-session
fix. Home Assistant moves the registered entities to their new devices; it does
not recreate them. Customized names and entity-based automation references are
preserved. Device/area-based targets may need adjustment because the entities are
now assigned to separate devices. Assign the new devices to the desired rooms.
The original server device and its customization remain. No entities or orphan
duplicates are automatically deleted.

### 1.19.1: node session recovery

Version 1.19.0 incorrectly treated the node `_id` as persistent. Tdarr can issue
a new session ID on each node startup, leaving old entities unavailable and
creating duplicates. Version 1.19.1 identifies nodes by their configured unique
`nodeName` and resolves the current session ID for readings and pause commands.
Keep node names unique and unchanged across restarts. A deliberate node rename
is a new identity; unlike library IDs, session IDs cannot identify that rename.

On upgrade, the oldest matching node entity is reused with its entity ID and
customizations preserved. Matching is scoped to the config entry, entity type
and original node name. Existing duplicates are not automatically deleted or
disabled: they may still be referenced in user dashboards and automations.
After updating and restarting Home Assistant, verify the restored original
entities, then remove unused orphan duplicates through the entity settings.
Do not remove/re-add the Tdarr integration or edit `.storage` manually.

Transient polling timeouts, connection errors and HTTP 502/503/504 responses
are retried once. Control commands are never automatically retried. Persistent
errors now report the failed read and a safe error type/status (for example,
`getNodes: ReadTimeout`) instead of discarding the cause. The coordinator handles
failure/recovery logging without an extra warning on every poll. Real persistent
failures still make entities unavailable; stale data is not presented as current.

Version 1.19.0 adds **Process Library** switches and separate library statistics,
alongside the **Scan for new files** buttons introduced in 1.18.1.

### Library controls and statistics

Each real library has:

- **Scan for new files**: starts a Find new scan.
- **Process Library**: enables/disables Tdarr processing for that library. This
  changes Tdarr's `processLibrary` setting; it is not an immediate worker kill
  or a pause of all nodes. It does not change the library's plugins or flows.
- **Space saved** in GB, **Transcodes**, and **Health checks** numeric sensors.
- The existing **file count** sensor and its detailed attributes.

Statistics use the existing Tdarr responses, without extra polling calls.
The new sensors support history/long-term statistics as numeric measurements.
Missing values are shown as unknown, not fabricated zeroes. Savings may be
negative and counters may reset when statistics are reset in Tdarr.

New nodes and libraries are discovered on the next poll without reloading all
servers. Removed ones become unavailable. Switches reflect changes made in the
Tdarr UI on the next poll, and report failed commands in Home Assistant.

### Upgrade notes for 1.19.0

- Historical note (superseded for nodes by 1.19.1 above): existing node and library entities migrate from name-based unique IDs to
  stable IDs, preserving their Home Assistant entity IDs and customizations
  when the old name identifies exactly one current entity. Do not rename nodes
  or libraries at the same time as this upgrade. Already-renamed or ambiguous
  legacy entries cannot be safely matched and are not guessed or deleted.
- The polling interval is now saved correctly in options (minimum 5 seconds).
  Values previously saved by the old flow in config data remain a fallback.
- API keys are no longer logged by the options flow. Options are compatible
  with Home Assistant's current read-only `config_entry` property.
- All HTTP calls have transport timeouts; failed polling becomes unavailable.
- The legacy `tdarr.refresh_library` action now requires an exact library name
  or ID instead of matching a substring. Existing exact-name calls still work.

Each button appears under its library device and can be used in
dashboards or with Home Assistant's `button.press` action. No helpers or manual
library paths are needed. New libraries are discovered on the next integration
update. Deleted libraries become unavailable; their entities can be removed
manually. Library renames retain the same unique ID.

The button runs Tdarr's **Scan (Find new)** using the library's exact ID and
configured source folder. It finds new files and removes database entries for
files that no longer exist in that folder. It does not run **Scan (Fresh)** or
reset the library database. A successful press means Tdarr accepted the request,
not that the scan has finished.

### Install this fork

Add `https://github.com/mrmultifunk/tdarr_ha` as a HACS custom repository with
category **Integration**, download this fork, and restart Home Assistant.
This fork uses the same `tdarr` integration domain as the original: install only
one version. If already using the original, switch the HACS repository to this
fork while preserving your Home Assistant integration configuration.

Find the buttons under **Settings → Devices & services → Tdarr → the library device**.
The existing sensors, switches, and `tdarr.refresh_library` action are retained.

### Development checks

Run `python -m unittest discover -s tests -v` with `requests` and `voluptuous` installed.
These isolated tests mock Home Assistant and HTTP; they do not replace a live
test against your Home Assistant and Tdarr installations.

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/itchannel)

## Install
Use HACS and add as a custom repo. Once the integration is installed go to your integrations and follow the configuration options below:
- Tdarr Server IP
- Tdarr Port (Prefilled to Tdarr default port 8265)

## Currently Supported
- Server status
- Node information
- Node FPS
- Library information and Statistics
- Switches to pause/unpause a node

## Screenshots
![Paused Sensor](https://github.com/itchannel/screenshots/raw/main/tdarr_node_paused.jpg)

![Library Sensor](https://github.com/itchannel/screenshots/raw/main/tdarr_library_sensor.jpg)

## Additional Information

The integration will automatically add new nodes as they come online. Old nodes that are no longer used will need to be manually deleted from HA if no longer used.

All sensors display any available additional info in the sensor attributes section. This information can be used by you to create more verbose sensors using Home Assistant templates. 


This is a custom integration I have created to allow me to use HA to control my nodes such as pausing/unpausing transcoding depending on how much excess solar electricity I have. 