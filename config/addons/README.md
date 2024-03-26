# Addons
This directory contains possible addons for your MMU setup. 

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) EREC Filament Cutter
An addon used to control filament cutting at the MMU rather than the toolhead
<img src="https://github.com/kevinakasam/ERCF_Filament_Cutter/blob/main/Images/Banner.png" width=60%>
### Compatibility
**MMU:** ERCFv2<br>
**Printer:** _Any_
### Github
https://github.com/kevinakasam/ERCF_Filament_Cutter
### Config
1. Add `[include mmu/addons/mmu_erec_cutter.cfg]` to your `printer.cfg`
1. Edit `mmu_erec_cutter.cfg` and `mmu_erec_cutter_hw.cfg` to work with your setup
1. In `mmu_macro_vars.cfg` set `variable_user_post_unload_extension : "EREC_CUTTER_ACTION"`
1. Optionally in `mmu_macro_vars.cfg` set `variable_user_pre_unload_extension : "BLOBIFIER_PARK"` to park the nozzle on the tray during a swap

<hr>

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Blobifier
An addon used to create purge blobs instead of using a wipe tower
<img src="https://raw.githubusercontent.com/Dendrowen/Blobifier/main/Pictures/Render_Full.png" width=60%>
### Compatibility
**MMU:** _Any_<br>
**Printer:** Voron v2, others in the works
### Github
https://github.com/Dendrowen/Blobifier
### Config
1. Add `[include mmu/addons/blobifier.cfg]` to your `printer.cfg`
1. Edit `blobifier.cfg` and `blobifier_hw.cfg` to work with your setup
1. Set `variable_user_post_load_extension : "BLOBIFIER"` in `mmu_macro_vars.cfg`
1. Optionally set `variable_user_pre_unload_extension : "BLOBIFIER_PARK"` in `mmu_macro_vars.cfg` to park the nozzle on the tray during a swap

<hr>

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) EAP
An addon used to create purge pellets instead of/or in conjunction with using a wipe tower
<img src="https://github.com/bombela/EjectionAssistedPurge/blob/master/doc/installed_closeup.jpg" width=60%>
<video src="https://github.com/bombela/EjectionAssistedPurge/blob/master/doc/in_action.mp4" width=60%>
### Compatibility
**MMU:** _Any_<br>
**Printer:** Voron v2, Untested on Voron Trident
### Github
https://github.com/bombela/EjectionAssistedPurge
### Config
1. Add `[include mmu/addons/eap.cfg]` to your `printer.cfg`
1. Edit `eap.cfg` and `eap_hw.cfg` to work with your setup
1. Set `variable_user_post_load_extension : "PURGE"` in `mmu_macro_vars.cfg`
1. Optionally set `variable_user_pre_unload_extension : "PURGE_PARK"` in `mmu_macro_vars.cfg` to park the nozzle on the tray during a swap ### This is still WIP