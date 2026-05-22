"""Diagnose camera parameters — query actual settings and test different configs."""
import sys
import os
import time

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

from src.device.camera.hikrobot.hikrobot_camera import HikrobotLineScanCamera

# SDK imports (available after load_sdk)
from src.device.camera.hikrobot.sdk_loader import load_sdk
load_sdk()
from CameraParams_const import MV_GIGE_DEVICE
from CameraParams_header import MV_CC_DEVICE_INFO_LIST, MVCC_FLOATVALUE, MVCC_INTVALUE_EX
from MvCameraControl_class import MvCamera
from MvErrorDefine_const import MV_OK
from ctypes import c_bool, POINTER, cast


def query_params(cam, names):
    """Query actual camera hardware values for each param name."""
    for name in names:
        try:
            # Try to read from camera directly
            iv = MVCC_INTVALUE_EX()
            ret = cam._camera.MV_CC_GetIntValueEx(name, iv)
            if ret == MV_OK:
                print(f"  {name} (int) = {iv.nCurValue}")
                continue

            fv = MVCC_FLOATVALUE()
            ret = cam._camera.MV_CC_GetFloatValue(name, fv)
            if ret == MV_OK:
                print(f"  {name} (float) = {fv.fCurValue}")
                continue

            bv = c_bool()
            ret = cam._camera.MV_CC_GetBoolValue(name, bv)
            if ret == MV_OK:
                print(f"  {name} (bool) = {bv.value}")
                continue

            # Try enum
            print(f"  {name} = <not readable as int/float/bool, code=0x{ret:08X}>")
        except Exception as e:
            print(f"  {name} = <error: {e}>")


def main():
    print("=== Camera Parameter Diagnostics ===\n")

    # Enumerate
    devices = HikrobotLineScanCamera.enumerate_devices()
    if not devices:
        print("FAIL: No devices found")
        return 1
    target = devices[0]
    print(f"Device: {target.model} SN={target.serial_number}")

    # Open
    cam = HikrobotLineScanCamera()
    if not cam.open(target.serial_number):
        code, msg = cam.get_last_error()
        print(f"FAIL: open: 0x{code:08X} {msg}")
        return 1

    # Query key parameters
    print("\n--- Current camera parameters (hardware) ---")
    param_names = [
        "Width", "Height", "OffsetX", "OffsetY",
        "ExposureTime", "ExposureAuto",
        "Gain", "GainAuto",
        "LineRate",
        "PixelFormat",
        "TriggerMode", "TriggerSource",
        "PayloadSize",
        "AcquisitionMode",
        "AcquisitionFrameRate",
        "BlackLevel",
        "Gamma",
        "DigitalShift",
        "ReverseX", "ReverseY",
        "DeviceLinkThroughputLimit",
    ]
    query_params(cam, param_names)

    # Also read enum values as string
    print("\n--- Enum values (string) ---")
    enum_names = ["PixelFormat", "TriggerMode", "ExposureAuto", "GainAuto", "AcquisitionMode"]
    for name in enum_names:
        try:
            # We can try set_param with the current value to see if it works,
            # but reading back enum as string requires MV_CC_GetEnumValue which
            # we don't have in our code. Instead, try set+get pattern.
            pass
        except Exception:
            pass

    # Try enumerating pixel format options via feature node
    print("\n--- Available PixelFormat options ---")
    try:
        formats = ["Mono8", "BayerRG8", "BayerGR8", "BayerGB8", "BayerBG8",
                    "RGB8Packed", "RGB8", "BGR8", "YUV422_8", "YUV422_8_UYVY"]
        for fmt in formats:
            ret = cam._camera.MV_CC_SetEnumValueByString("PixelFormat", fmt)
            if ret == MV_OK:
                print(f"  SUPPORTED: {fmt}")
            else:
                print(f"  NOT SUPPORTED: {fmt} (0x{ret:08X})")
    except Exception as e:
        print(f"  Error iterating formats: {e}")

    # Try capture with different settings
    print("\n--- Capture test with different settings ---")

    test_configs = [
        {"ExposureTime": 5000.0, "Gain": 10.0, "PixelFormat": "Mono8", "TriggerMode": "Off"},
        {"ExposureTime": 5000.0, "Gain": 10.0, "PixelFormat": "Mono8", "TriggerMode": "On", "TriggerSource": "Software"},
        {"ExposureTime": 10000.0, "Gain": 10.0, "PixelFormat": "Mono8", "TriggerMode": "Off"},
    ]

    for idx, cfg in enumerate(test_configs):
        print(f"\n  Config {idx+1}: {cfg}")
        for k, v in cfg.items():
            cam.set_param(k, v)

        time.sleep(0.3)  # let params settle

        frames = []
        def on_pkt(pkt):
            frames.append(pkt)

        cam.register_line_callback(on_pkt)

        if not cam.start_grabbing():
            code, msg = cam.get_last_error()
            print(f"    start_grabbing FAIL: 0x{code:08X} {msg}")
            continue

        deadline = time.time() + 3
        while len(frames) < 3 and time.time() < deadline:
            time.sleep(0.1)

        cam.stop_grabbing()

        if frames:
            pkt = frames[0]
            arr = pkt.line_data
            print(f"    Frame: {pkt.width}x{pkt.height}, {pkt.pixel_format}")
            print(f"    Data: min={arr.min()}, max={arr.max()}, mean={arr.mean():.1f}, "
                  f"nonzero={arr.size and (arr > 0).sum()}")
            if arr.max() > 10:
                print(f"    BRIGHT! Saving frame...")
                import cv2
                fname = os.path.join(_project_root, f"camera_diag_frame_{idx}.png")
                cv2.imwrite(fname, arr)
                print(f"    Saved {fname}")
        else:
            print(f"    No frames received")

    cam.close()
    HikrobotLineScanCamera._finalize_sdk()
    print("\n=== Diagnostics complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
