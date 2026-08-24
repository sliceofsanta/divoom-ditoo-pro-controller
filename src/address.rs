use std::fmt;
use std::str::FromStr;

/// Bluetooth device address, formatted as `AA:BB:CC:DD:EE:FF`.
///
/// On Linux the crate uses `bluer::Address` directly; this type provides the
/// same surface (parse, display, copy) on platforms without bluer.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Address(pub [u8; 6]);

#[derive(Debug)]
pub struct InvalidAddress(String);

impl fmt::Display for InvalidAddress {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    write!(f, "invalid Bluetooth address: {}", self.0)
  }
}

impl std::error::Error for InvalidAddress {}

impl FromStr for Address {
  type Err = InvalidAddress;

  fn from_str(s: &str) -> Result<Self, Self::Err> {
    let parts: Vec<&str> = s.split([':', '-']).collect();
    if parts.len() != 6 {
      return Err(InvalidAddress(s.to_string()));
    }
    let mut bytes = [0u8; 6];
    for (i, part) in parts.iter().enumerate() {
      bytes[i] = u8::from_str_radix(part, 16).map_err(|_| InvalidAddress(s.to_string()))?;
    }
    Ok(Address(bytes))
  }
}

impl fmt::Display for Address {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    let b = self.0;
    write!(
      f,
      "{:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}",
      b[0], b[1], b[2], b[3], b[4], b[5]
    )
  }
}
