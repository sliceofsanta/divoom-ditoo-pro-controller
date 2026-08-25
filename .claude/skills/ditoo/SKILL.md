---
name: ditoo
description: Show something on the Divoom Ditoo Pro's 16x16 LED panel - draw an image, or set the status face. Use when asked to put something on the Ditoo, the pixel display, or the speaker's screen; or when a visual signal on the physical display would be genuinely useful.
---

# Ditoo Pro display

A 16x16 RGB LED panel driven over Bluetooth. A daemon holds one connection, so
changes land in well under a second.

`integrations/claude-code/ditoo-state.sh` is the entry point (call it by its
absolute path from anywhere).

## Show an image

```bash
integrations/claude-code/ditoo-state.sh draw /path/to/image.gif
```

Any format the `image` crate reads (GIF, PNG, JPEG, BMP, WebP). Animated GIFs
play as animations. Anything not already 16x16 is resized to fit, so art
designed at that size looks far better than a downscaled photo.

The image is copied into the run directory, never into the user's faces
directory. It stays up until the next status change - which the session hooks
trigger constantly, so `draw` is for a deliberate moment, not a persistent
display.

## Set a status face

```bash
integrations/claude-code/ditoo-state.sh chilling
```

States: `thinking`, `working`, `alerting`, `success`, `error`, `compacting`,
`chilling`, `off`. These are normally driven automatically by session hooks -
set one by hand only when asked.

## Check it

```bash
integrations/claude-code/ditoo-state.sh status
```

Reports whether the daemon holds the connection, what is displayed, and the
tail of the log. `start` and `stop` control the daemon; while it runs the
device cannot be used as a Bluetooth speaker.

## Drawing something new

The panel is 256 pixels. What works:

- **Colour carries.** From across a room colour and motion are all that read.
- **Every frame must differ.** Duplicate frames read as a stutter, and a shape
  cycle sharing a period with a colour pulse aliases into a single flip.
- **Motion under ~1.5 pixels vanishes** into the pixel grid entirely.
- **Silhouette barely survives.** Detail only resolves up close.

Do NOT design the status faces - those are the user's own artwork. `draw` is
for one-off images.
