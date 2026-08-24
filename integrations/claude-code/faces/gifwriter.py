"""Minimal animated-GIF writer (stdlib only).

Exists so the face generator has no pip dependencies. Implements just enough of
GIF89a for small looping animations: a global colour table, per-frame delays,
and the LZW compression GIF requires.
"""

import struct

MAX_TABLE = 4096


def lzw_encode(indices, min_code_size):
  """GIF-flavoured LZW. Codes are packed LSB-first into a byte stream."""
  clear_code = 1 << min_code_size
  end_code = clear_code + 1

  table = {}
  next_code = 0
  code_size = 0

  def reset_table():
    nonlocal table, next_code, code_size
    table = {(i,): i for i in range(clear_code)}
    next_code = end_code + 1
    code_size = min_code_size + 1

  out = bytearray()
  bit_buffer = 0
  bit_count = 0

  def emit(code):
    nonlocal bit_buffer, bit_count
    bit_buffer |= code << bit_count
    bit_count += code_size
    while bit_count >= 8:
      out.append(bit_buffer & 0xFF)
      bit_buffer >>= 8
      bit_count -= 8

  reset_table()
  emit(clear_code)

  prefix = ()
  for index in indices:
    candidate = prefix + (index,)
    if candidate in table:
      prefix = candidate
      continue
    emit(table[prefix])
    if next_code < MAX_TABLE:
      table[candidate] = next_code
      next_code += 1
      # Widen one code later than "the table just filled". Decoders build their
      # table one entry behind the encoder, so bumping at (1 << code_size)
      # desyncs them -- real decoders reject the stream as truncated or report
      # an invalid code. This matches giflib's `RunningCode > MaxCode1` rule.
      if next_code == (1 << code_size) + 1 and code_size < 12:
        code_size += 1
    else:
      emit(clear_code)
      reset_table()
    prefix = (index,)

  if prefix:
    emit(table[prefix])
  emit(end_code)

  if bit_count > 0:
    out.append(bit_buffer & 0xFF)
  return bytes(out)


def _sub_blocks(data):
  """GIF image data travels in length-prefixed blocks of at most 255 bytes."""
  out = bytearray()
  for start in range(0, len(data), 255):
    chunk = data[start:start + 255]
    out.append(len(chunk))
    out += chunk
  out.append(0)
  return bytes(out)


def write_gif(path, frames, palette, delays_ms, loop=True):
  """Write an animated GIF.

  frames     -- list of 2D index grids (rows of palette indices)
  palette    -- list of (r, g, b), at most 256 entries
  delays_ms  -- per-frame delay in milliseconds (GIF stores centiseconds)
  """
  if not frames:
    raise ValueError("no frames")
  if len(palette) > 256:
    raise ValueError(f"palette too large: {len(palette)}")

  height = len(frames[0])
  width = len(frames[0][0])

  # Global colour table size must be a power of two, minimum 2 entries.
  size_exponent = 0
  while (1 << (size_exponent + 1)) < max(2, len(palette)):
    size_exponent += 1
  table_entries = 1 << (size_exponent + 1)

  min_code_size = max(2, size_exponent + 1)

  out = bytearray(b"GIF89a")
  # Logical screen descriptor: GCT present, 8-bit colour resolution.
  out += struct.pack("<HH", width, height)
  out.append(0x80 | 0x70 | size_exponent)
  out.append(0)  # background colour index
  out.append(0)  # pixel aspect ratio

  for entry in range(table_entries):
    rgb = palette[entry] if entry < len(palette) else (0, 0, 0)
    out += bytes(rgb)

  if loop:
    out += b"\x21\xFF\x0BNETSCAPE2.0\x03\x01" + struct.pack("<H", 0) + b"\x00"

  for frame, delay_ms in zip(frames, delays_ms):
    # Graphic control extension: disposal 1 (leave in place), no transparency.
    out += b"\x21\xF9\x04"
    out.append(0x04)
    out += struct.pack("<H", max(1, round(delay_ms / 10)))
    out.append(0)  # transparent colour index (unused)
    out.append(0)  # block terminator

    out += b"\x2C"
    out += struct.pack("<HHHH", 0, 0, width, height)
    out.append(0)  # no local colour table, not interlaced

    indices = [index for row in frame for index in row]
    out.append(min_code_size)
    out += _sub_blocks(lzw_encode(indices, min_code_size))

  out += b"\x3B"

  with open(path, "wb") as handle:
    handle.write(bytes(out))
  return len(out)
