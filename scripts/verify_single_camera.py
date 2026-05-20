"""Quick verification: enumerate cameras and test basic capture via virtual camera."""
import time
import cv2
import numpy as np

from src.device.camera.simulator.virtual_line_scan import VirtualLineScanCamera

def main():
    print("=== Virtual Line Scan Camera Verification ===\n")

    # Enumerate
    devices = VirtualLineScanCamera.enumerate_devices()
    print(f"Enumerated {len(devices)} device(s):")
    for d in devices:
        print(f"  - {d.model} ({d.serial_number}) @ {d.ip_address}")

    # Connect
    cam = VirtualLineScanCamera(width=2048, line_rate=20000)
    cam.open(devices[0].serial_number)
    print(f"\nConnected: {cam.get_status().connected}")

    # Collect lines and build image block
    block = np.zeros((512, 2048), dtype=np.uint8)
    line_idx = 0
    target_height = 512

    def on_line(packet):
        nonlocal line_idx
        if line_idx < target_height and packet.line_data is not None:
            block[line_idx, :] = packet.line_data[0, :]
            line_idx += 1

    cam.register_line_callback(on_line)
    cam.start_grabbing()
    print("Acquisition started, waiting for 512 lines...")

    start = time.time()
    while line_idx < target_height and (time.time() - start) < 5.0:
        time.sleep(0.01)

    cam.stop_grabbing()
    cam.close()

    print(f"Collected {line_idx} lines")
    print(f"Image block shape: {block.shape}")

    if line_idx >= target_height:
        cv2.imwrite("D:/work/copper-defect-eval-tool/outputs/verify_block.png", block)
        print("Image block saved to outputs/verify_block.png")
    else:
        print("WARNING: Not enough lines collected")

    print("\n=== Single Camera Verification Complete ===")

if __name__ == "__main__":
    main()
