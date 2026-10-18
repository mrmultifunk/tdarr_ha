# Tdarr Home Assistant Integration

## This fork

Based on [itchannel/tdarr_ha](https://github.com/itchannel/tdarr_ha).
Version 1.18.1 adds a **Scan for new files** button for each library.

Each button appears under the existing Tdarr server device and can be used in
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

Find the buttons under **Settings → Devices & services → Tdarr → Devices**.
The existing sensors, switches, and `tdarr.refresh_library` action are retained.

### Development checks

Run `python -m unittest discover -s tests -v` with `requests` installed.
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