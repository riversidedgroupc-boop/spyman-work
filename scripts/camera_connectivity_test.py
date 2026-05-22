"""Quick camera connectivity test — discover, open, grab a few frames, save one."""
import sys
import os
import time

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to sys.path so `src` package is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

from src.device.camera.hikrobot.hikrobot_camera import HikrobotLineScanCamera


def main():
    print("=== Hikrobot Line Scan Camera Connectivity Test ===\n")

    # Step 1: Enumerate
    print("[1/5] Enumerating devices...")
    devices = HikrobotLineScanCamera.enumerate_devices()
    if not devices:
        print("  FAIL: No devices found. Check power, network, IP config, firewall.")
        return 1
    for d in devices:
        print(f"  Device: {d.model} | SN={d.serial_number} | IP={d.ip_address} | MAC={d.mac_address} | {d.user_defined_name}")

    # Step 2: Open first device
    target = devices[0]
    print(f"\n[2/5] Opening camera SN={target.serial_number}...")
    cam = HikrobotLineScanCamera()
    if not cam.open(target.serial_number):
        code, msg = cam.get_last_error()
        print(f"  FAIL: 0x{code:08X} {msg}")
        return 1
    print(f"  OK: Connected to {target.model} @ {target.ip_address}")

    # Step 2.5: Configure camera for free-run (no external trigger needed)
    print("\n[2.5/5] Configuring camera parameters...")
    cam.set_param("TriggerMode", "Off")        # free-run, no external trigger
    cam.set_param("ExposureTime", 200.0)       # 200 us exposure
    cam.set_param("Gain", 1.0)                 # a bit of gain
    print(f"  TriggerMode=Off, ExposureTime=200us, Gain=1.0")

    # Step 3: Register callback
    print("\n[3/5] Registering callback and starting grab (collecting first 10 frames)...")
    frames = []
    def on_packet(pkt):
        frames.append(pkt)

    cam.register_line_callback(on_packet)

    # Step 4: Start grabbing, collect a few frames
    if not cam.start_grabbing():
        code, msg = cam.get_last_error()
        print(f"  FAIL: start_grabbing: 0x{code:08X} {msg}")
        cam.close()
        return 1

    # Wait for frames
    deadline = time.time() + 5
    while len(frames) < 10 and time.time() < deadline:
        time.sleep(0.1)

    cam.stop_grabbing()

    if not frames:
        print("  FAIL: No frames received within 5 seconds")
        cam.close()
        return 1

    pkt = frames[0]
    print(f"  OK: Received {len(frames)} frames")
    print(f"      Frame 0: {pkt.width}x{pkt.height}, {pkt.pixel_format}, encoder={pkt.encoder_count}")
    if pkt.line_data is not None:
        arr = pkt.line_data
        print(f"      Data shape: {arr.shape}, dtype={arr.dtype}, "
              f"min={arr.min()}, max={arr.max()}, mean={arr.mean():.1f}")

    # Step 5: Save a sample frame
    print("\n[5/5] Saving sample frames...")
    try:
        import cv2
        for i, p in enumerate(frames[:3]):
            if p.line_data is not None:
                fname = os.path.join(_project_root, f"camera_test_frame_{i}.png")
                cv2.imwrite(fname, p.line_data)
                print(f"  OK: Saved {fname} ({os.path.getsize(fname)} bytes)")
    except ImportError:
        print("  WARNING: cv2 not available, skipping save")

    # Status
    st = cam.get_status()
    print(f"\nCamera status: connected={st.connected}, grabbing={st.grabbing}, "
          f"lines={st.received_line_count}, line_rate={st.line_rate}")

    cam.close()
    HikrobotLineScanCamera._finalize_sdk()  # Release SDK resources properly
    print("\n=== Connectivity test PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
