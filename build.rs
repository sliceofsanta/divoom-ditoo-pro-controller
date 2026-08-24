fn main() {
  // macOS: any binary touching IOBluetooth must carry NSBluetoothAlwaysUsageDescription,
  // otherwise TCC aborts the process (SIGABRT) instead of prompting for permission.
  // Embedding an Info.plist into the __TEXT segment is the supported way for CLI tools.
  if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos") {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
    println!("cargo:rustc-link-arg=-Wl,-sectcreate,__TEXT,__info_plist,{manifest_dir}/macos/Info.plist");
    println!("cargo:rerun-if-changed=macos/Info.plist");
  }
}
