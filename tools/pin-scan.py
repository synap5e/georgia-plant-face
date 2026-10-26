#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["capstone"]
# ///
"""Disassemble an RP2040 Arduino flash dump and list small-constant args to calls."""

import collections
import struct
import sys

import capstone

BASE = 0x10000000


def main() -> None:
    data = open(sys.argv[1], "rb").read()[: int(sys.argv[2], 0)]
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.skipdata = True
    calls: dict[int, list[tuple[int, int, int | None]]] = collections.defaultdict(list)
    r0 = r1 = None
    for ins in md.disasm(data[0x100:], BASE + 0x100):
        m, ops = ins.mnemonic, ins.op_str
        if m in ("movs", "mov") and ops.startswith("r0, #"):
            r0 = int(ops.split("#")[1], 0)
        elif m in ("movs", "mov") and ops.startswith("r1, #"):
            r1 = int(ops.split("#")[1], 0)
        elif m == "bl":
            tgt = int(ops.lstrip("#"), 0)
            if r0 is not None and r0 < 30:
                calls[tgt].append((ins.address, r0, r1))
            r0 = r1 = None
        elif m.startswith(("b", "pop", "bx")):
            r0 = r1 = None
    for tgt, lst in sorted(calls.items(), key=lambda kv: -len(kv[1])):
        args = sorted({(a, b) for _, a, b in lst}, key=str)
        print(f"{tgt:#x} x{len(lst)} args(r0,r1)={args[:12]} from={[hex(a) for a, _, _ in lst[:4]]}")
    _ = struct


if __name__ == "__main__":
    main()
