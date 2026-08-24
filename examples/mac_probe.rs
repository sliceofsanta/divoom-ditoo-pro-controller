//! Temporary diagnostic: replicate the transport's connect sequence on the
//! plain main thread (no tokio) to isolate IOBluetooth thread-affinity issues.
#[cfg(target_os = "macos")]
fn main() {
  use std::cell::RefCell;
  use std::ffi::c_void;
  use std::rc::Rc;
  use std::time::{Duration, Instant};

  use objc2::rc::Retained;
  use objc2::runtime::AnyObject;
  use objc2::{define_class, msg_send, AllocAnyThread, DefinedClass};
  use objc2_foundation::{NSDate, NSDefaultRunLoopMode, NSObject, NSRunLoop, NSString};
  use objc2_io_bluetooth::{IOBluetoothDevice, IOBluetoothRFCOMMChannel};

  struct Ivars {
    buffer: Rc<RefCell<Vec<u8>>>
  }

  define_class!(
    #[unsafe(super(NSObject))]
    #[name = "MacProbeDelegate"]
    #[ivars = Ivars]
    struct Delegate;

    impl Delegate {
      #[unsafe(method(rfcommChannelData:data:length:))]
      fn data(&self, _c: *mut AnyObject, data: *mut c_void, len: usize) {
        let bytes = unsafe { std::slice::from_raw_parts(data as *const u8, len) };
        self.ivars().buffer.borrow_mut().extend_from_slice(bytes);
      }
    }
  );

  impl Delegate {
    fn new(buffer: Rc<RefCell<Vec<u8>>>) -> Retained<Self> {
      let this = Self::alloc().set_ivars(Ivars { buffer });
      unsafe { msg_send![super(this), init] }
    }
  }

  fn pump(secs: f64) {
    unsafe {
      let rl = NSRunLoop::currentRunLoop();
      let date = NSDate::dateWithTimeIntervalSinceNow(secs);
      rl.runMode_beforeDate(NSDefaultRunLoopMode, &date);
    }
  }

  let ns = NSString::from_str("B1:21:81:BE:C4:E0");
  let device = match unsafe { IOBluetoothDevice::deviceWithAddressString(Some(&ns)) } {
    Some(d) => d,
    None => {
      println!("no device");
      return;
    }
  };
  println!("connected={}", unsafe { device.isConnected() });
  if unsafe { device.isConnected() } {
    println!("closeConnection -> {}", unsafe { device.closeConnection() });
    let dl = Instant::now() + Duration::from_secs(5);
    while unsafe { device.isConnected() } && Instant::now() < dl {
      pump(0.05);
    }
    println!("after wait connected={}", unsafe { device.isConnected() });
    std::thread::sleep(Duration::from_millis(500));
  }
  let buffer = Rc::new(RefCell::new(Vec::new()));
  let delegate = Delegate::new(Rc::clone(&buffer));
  let mut ch: Option<Retained<IOBluetoothRFCOMMChannel>> = None;
  let st = unsafe {
    device.openRFCOMMChannelSync_withChannelID_delegate(Some(&mut ch), 2, Some(&delegate))
  };
  println!("open ch2 -> {}", st);
  let Some(ch) = ch else {
    println!("MAIN-THREAD RESULT: open failed");
    return;
  };
  let pkt: [u8; 7] = [0x01, 0x03, 0x00, 0x09, 0x0c, 0x00, 0x02];
  let wr = unsafe { ch.writeSync_length(pkt.as_ptr() as *mut c_void, 7) };
  println!("write -> {}", wr);
  let dl = Instant::now() + Duration::from_secs(4);
  while Instant::now() < dl && buffer.borrow().len() < 10 {
    pump(0.05);
  }
  println!("rx: {}", hex::encode(&*buffer.borrow()));
  unsafe { ch.closeChannel() };
  println!("MAIN-THREAD RESULT: {}", if buffer.borrow().len() >= 10 { "WORKS" } else { "no reply" });
}

#[cfg(not(target_os = "macos"))]
fn main() {}
