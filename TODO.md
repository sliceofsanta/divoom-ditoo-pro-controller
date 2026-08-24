# Divoom Ditoo Pro Controller - Feature Status

## Implemented

- [x] Scan for Bluetooth devices
- [x] Send animation/image to display
- [x] Set date/time
- [x] Toggle alarm on/off
- [x] Convert GIF to Divoom 16x16 format
- [x] Convert Divoom 16x16 format to GIF
- [x] Debug/inspect Divoom format images
- [x] Keyboard backlight control (next/prev/toggle)
- [x] Screen brightness control
- [x] Scrolling text
- [x] Static text (with multiline and alignment)
- [x] Scrolling text multiline and alignment
- [x] Clock face selection
- [x] Get/set volume
- [x] Play/pause control
- [x] Set language
- [x] Light mode selection (light, hot, special, music via 0x45)
- [x] Read and validate device responses (ACK/NAK)
- [x] Video playback (via libmpv, behind `video` feature flag)

## Not Implemented

### Display & Images
- [ ] Drawing pad control
- [ ] Sand painting mode
- [ ] GIF speed control
- [ ] Screen direction configuration
- [ ] Watch face mode (ext cmd 0x14 / JSON)
- [ ] Score mode (JSON)
- [ ] Set box color / sleep color

### Audio & Music
- [ ] EQ control
- [ ] Microphone on/off
- [ ] SD card music playback (list, play by ID, next/prev, play mode)
- [ ] Mix music mode
- [ ] Power-on voice control / volume

### Alarms (extended)
- [ ] Alarm with custom scene/GIF
- [ ] Alarm volume control
- [ ] Alarm voice control

### Sleep Mode
- [ ] Sleep timer
- [ ] Sleep light effect
- [ ] Sleep scene
- [ ] Sleep color

### Device Settings
- [ ] Set device name
- [ ] Auto power-off timer
- [ ] Energy control

### Notifications
- [ ] Android notification forwarding (ANCS)
- [ ] Custom notification pictures

### Games
- [ ] Game control
- [ ] Game key input

### File Management & Updates
- [ ] Firmware update over Bluetooth
- [ ] Hot-swap content updates
- [ ] SD/TF card management

### Work Modes
- [ ] Switch between Bluetooth / Line-in / SD Card / USB Audio modes

### Integrations
- [x] Claude Code progress display (seven animated mascot states via hooks)
- [x] Long-running daemon holding one connection (`daemon` subcommand) --
      sub-second state changes, and one connect chime per daemon rather than
      one per state change
- [ ] Merge states across concurrent Claude Code sessions (error > alerting >
      working > thinking > success > chilling) rather than last-writer-wins
- [ ] Drive context-aware mascot actions instead of looping a fixed clip per state
- [ ] Investigate uploading faces once and switching with `clock set` (ext 0x14)
      for instant, connectionless-feeling switching

### Protocol
- [ ] JSON-based command protocol (SPP_JSON)
- [ ] Configurable Bluetooth adapter selection (Linux)
- [ ] Bluetooth scanning on macOS (pair via System Settings and use `devices` for now)
