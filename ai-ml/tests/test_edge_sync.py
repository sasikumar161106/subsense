"""
Edge Offline Buffering and Reconnection Sync Protocol Test Suite.
Verifies circular SPIFFS flash buffer overflow handling, FIFO rollover,
and reconnection handshake backfill to cloud.
"""

import subprocess
from pathlib import Path
import pytest


def test_native_firmware_c_test_harness():
    """
    Executes the native C++ test harness binary compiled with MSVC cl.exe.
    Verifies on-device int8 math, SRAM memory bounds (<38KB), local mesh radio
    corroboration, SPIFFS circular buffer rollover, and sync protocol.
    """
    exe_path = Path(__file__).resolve().parent.parent / "edge_firmware" / "hil_harness" / "test_firmware.exe"
    if not exe_path.exists():
        # Re-compile if needed
        cmd = (
            'call "C:\\Program Files\\Microsoft Visual Studio\\18\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" && '
            'cl /EHsc /O2 /Fe:edge_firmware\\hil_harness\\test_firmware.exe '
            'edge_firmware\\hil_harness\\test_firmware.cpp '
            'edge_firmware\\firmware\\subsense_edge_tinyml.cpp '
            'edge_firmware\\firmware\\mesh_corroboration.cpp '
            'edge_firmware\\firmware\\spiffs_circular_buffer.cpp '
            'edge_firmware\\firmware\\reconnection_sync.cpp'
        )
        compile_res = subprocess.run(
            ["cmd.exe", "/c", cmd],
            cwd=str(exe_path.parent.parent.parent),
            capture_output=True,
            text=True,
        )
        assert compile_res.returncode == 0, f"Compilation failed: {compile_res.stderr}"

    # Run executable
    run_res = subprocess.run([str(exe_path)], capture_output=True, text=True)
    print(run_res.stdout)
    assert run_res.returncode == 0, f"Native test failed: {run_res.stderr}"
    assert "ALL EMBEDDED FIRMWARE VERIFICATIONS PASSED!" in run_res.stdout
    assert "Measured SRAM Footprint: 240 bytes (Constraint: < 38,912 bytes)" in run_res.stdout
