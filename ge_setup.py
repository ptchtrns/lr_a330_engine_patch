#!/usr/bin/env python3
"""
A330-300 GE setup
=================

Turns a copy of the default Laminar Research Airbus A330-300 (Rolls-Royce Trent 700)
into a GE CF6-80E1 powered A330 for X-Plane 12.

Put this file in the copied aircraft folder, together with the add-on folders you want
to use, and run it. See README_GE_SETUP.md for step-by-step instructions.

Components (each one optional, asked when you run the script):

  1. GE engine model   - carda jowol's "General Electric CF6-80E1 Engine Mod for
                         JAR330" (free), with working thrust reverser animation and
                         the stock engine shake / wing flex movement.
                         https://forum.thresholdx.net/files/file/567-general-electric-cf6-80e1-engine-mod-for-jar330/
  2. FTSIM sound pack  - FTSIM+ Sounds "A330 GE" sound pack (payware), the stock
                         Trent engine sounds are muted.
                         https://www.ftsimplus.net/a330ge.html
  3. GE cockpit screens- upper/lower ECAM converted to the GE layout: N1 as the main
                         thrust gauge, N2 and fuel flow as numbers, GE-style N1 values,
                         2-spool vibration readouts.

The script keeps an untouched copy of every file it changes in "_ge_setup_backup", so
it can be run again at any time to add or remove components, or to put the aircraft
back to stock. Only the Python standard library is used - nothing else to install.
"""

import json
import math
import os
import re
import shutil
import struct
import sys
import zlib

VERSION = "1.0"

# --------------------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------------------

GE_NAME = "Airbus A330-300 GE"                                   # name in X-Plane's menu
GE_DESCRIP = "Airbus long range widebody twin (GE CF6-80E1)"

# Position of the GE engine objects (metres: lateral, vertical, longitudinal). Checked
# by eye in Plane Maker against the stock wing/pylon of the Laminar A330.
ENGINE_LAT, ENGINE_VERT, ENGINE_LONG = 30.4, -8.0, 77.1

BACKUP_DIR = "_ge_setup_backup"
STATE_FILE = os.path.join(BACKUP_DIR, "state.json")

ECAM = "cockpit_3d/generic/ECAM"
ECAM_SD = "cockpit_3d/generic/ECAM SECONDARY"

# Files this script changes, by their stock name (stored like this in the backup)
BACKUP_FILES = [
    "A330.acf",
    "fmod/A330.snd",
    "fmod/GUIDS.txt",
    ECAM + "/background-1.png",
    ECAM + "/EPR_arc-1.png",
    ECAM_SD + "/ENGINE/engine_background-1.png",
    ECAM_SD + "/CRUISE/cruise_bg-1.png",
]

# X-Plane finds these by the .acf file name, so they are renamed along with it
RENAME_STATIC = [
    ("A330.acf", "A330_GE.acf"),
    ("fmod/A330.snd", "fmod/A330_GE.snd"),
    ("A330_config.txt", "A330_GE_config.txt"),
    ("A330_vrconfig.txt", "A330_GE_vrconfig.txt"),
    ("A330_prefs.txt", "A330_GE_prefs.txt"),
    ("A330_icon11.png", "A330_GE_icon11.png"),
    ("A330_icon11_thumb.png", "A330_GE_icon11_thumb.png"),
]

LUA_REVERSERS = "plugins/xlua/scripts/A333.zz_ge_reversers"
LUA_DISPLAY = "plugins/xlua/scripts/A333.zz_ge_display"

SKIP_DIRS = {"objects", "liveries", "cockpit", "cockpit_3d", "airfoils", "data",
             "plugins", "fmod", "weapons", BACKUP_DIR}


class SetupError(Exception):
    pass


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

def p(rel):
    return os.path.join(ROOT, *rel.split("/"))


def exists(rel):
    return os.path.exists(p(rel))


def read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    nl = "\r\n" if b"\r\n" in raw[:20000] else "\n"
    return raw.decode("latin-1"), nl


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(text.encode("latin-1"))


def ask(question, default=True):
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            ans = input(f"{question} {hint} ").strip().lower()
        except EOFError:
            print()
            return default
        if ans == "":
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  Please type y (yes) or n (no) and press Enter.")


def say(msg=""):
    print(msg)


def rmtree(rel):
    if os.path.isdir(p(rel)):
        shutil.rmtree(p(rel))


def remove(rel):
    if os.path.isfile(p(rel)):
        os.remove(p(rel))


def renames():
    """All (stock, GE) name pairs, including livery icons."""
    pairs = list(RENAME_STATIC)
    if os.path.isdir(p("liveries")):
        for liv in sorted(os.listdir(p("liveries"))):
            for icon in ("icon11.png", "icon11_thumb.png"):
                pairs.append((f"liveries/{liv}/A330_{icon}", f"liveries/{liv}/A330_GE_{icon}"))
    return pairs


# --------------------------------------------------------------------------------------
# Minimal PNG reader / writer (8-bit RGBA, RGB, grey; non-interlaced)
# --------------------------------------------------------------------------------------

class Image:
    def __init__(self, w, h, px=None):
        self.w, self.h = w, h
        self.px = px if px is not None else bytearray(w * h * 4)

    def copy(self):
        return Image(self.w, self.h, bytearray(self.px))

    def get(self, x, y):
        i = (y * self.w + x) * 4
        return tuple(self.px[i:i + 4])

    def set(self, x, y, c):
        i = (y * self.w + x) * 4
        self.px[i:i + 4] = bytes(c)

    def erase(self, x0, y0, x1, y1):
        for y in range(max(0, y0), min(self.h, y1)):
            i = (y * self.w + max(0, x0)) * 4
            j = (y * self.w + min(self.w, x1)) * 4
            self.px[i:j] = bytes(j - i)

    def crop(self, x0, y0, x1, y1):
        out = Image(x1 - x0, y1 - y0)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if 0 <= x < self.w and 0 <= y < self.h:
                    out.set(x - x0, y - y0, self.get(x, y))
        return out

    def blend(self, x, y, c, cover=1.0):
        """Draw colour c (RGBA) over pixel (x, y) with extra coverage factor."""
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        sa = c[3] / 255.0 * cover
        if sa <= 0:
            return
        d = self.get(x, y)
        da = d[3] / 255.0
        oa = sa + da * (1 - sa)
        if oa <= 0:
            return
        rgb = [round((c[k] * sa + d[k] * da * (1 - sa)) / oa) for k in range(3)]
        self.set(x, y, (*rgb, round(oa * 255)))

    def paste(self, src, ox, oy):
        """Alpha-composite src over this image at (ox, oy)."""
        for y in range(src.h):
            for x in range(src.w):
                c = src.get(x, y)
                if c[3]:
                    self.blend(ox + x, oy + y, c)


def png_read(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SetupError(f"{path} is not a PNG file")
    pos, idat, hdr = 8, b"", None
    while pos < len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", chunk)
        elif typ == b"IDAT":
            idat += chunk
        pos += 12 + ln
    w, h, bd, ct, _, _, il = hdr
    chans = {0: 1, 2: 3, 4: 2, 6: 4}.get(ct)
    if bd != 8 or il != 0 or chans is None:
        raise SetupError(f"{path}: unsupported PNG format")
    raw = zlib.decompress(idat)
    stride = w * chans
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    i = 0
    for y in range(h):
        ft = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - chans] if x >= chans else 0
            b = prev[x]
            c = prev[x - chans] if x >= chans else 0
            if ft == 1:
                line[x] = (line[x] + a) & 255
            elif ft == 2:
                line[x] = (line[x] + b) & 255
            elif ft == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        prev = line
        for x in range(w):
            s = line[x * chans:(x + 1) * chans]
            if chans == 4:
                rgba = s
            elif chans == 3:
                rgba = (s[0], s[1], s[2], 255)
            elif chans == 2:
                rgba = (s[0], s[0], s[0], s[1])
            else:
                rgba = (s[0], s[0], s[0], 255)
            o = (y * w + x) * 4
            out[o:o + 4] = bytes(rgba)
    return Image(w, h, out)


def png_write(path, img):
    raw = bytearray()
    stride = img.w * 4
    for y in range(img.h):
        raw.append(0)
        raw += img.px[y * stride:(y + 1) * stride]

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", img.w, img.h, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def draw_line(img, p0, p1, width, col):
    """Anti-aliased thick line."""
    (x0, y0), (x1, y1) = p0, p1
    r = width / 2.0
    dx, dy = x1 - x0, y1 - y0
    ll = dx * dx + dy * dy
    for y in range(int(min(y0, y1) - r - 2), int(max(y0, y1) + r + 3)):
        for x in range(int(min(x0, x1) - r - 2), int(max(x0, x1) + r + 3)):
            cx, cy = x + 0.5, y + 0.5
            t = max(0.0, min(1.0, ((cx - x0) * dx + (cy - y0) * dy) / ll))
            d = math.hypot(cx - (x0 + t * dx), cy - (y0 + t * dy))
            img.blend(x, y, col, max(0.0, min(1.0, r + 0.5 - d)))


def draw_arc(img, cx, cy, radius, a_from, a_to, width, col):
    """Anti-aliased arc; angles in degrees, counter-clockwise from +x (y up)."""
    lo, hi = min(a_from, a_to), max(a_from, a_to)
    r = width / 2.0
    for y in range(int(cy - radius - r - 2), int(cy + radius + r + 3)):
        for x in range(int(cx - radius - r - 2), int(cx + radius + r + 3)):
            px, py = x + 0.5 - cx, cy - (y + 0.5)
            ang = math.degrees(math.atan2(py, px))
            if not (lo <= ang <= hi):
                continue
            d = abs(math.hypot(px, py) - radius)
            img.blend(x, y, col, max(0.0, min(1.0, r + 0.5 - d)))


# --------------------------------------------------------------------------------------
# Finding the add-on folders
# --------------------------------------------------------------------------------------

def walk_addons(max_depth=6):
    for top in sorted(os.listdir(ROOT)):
        if top in SKIP_DIRS or not os.path.isdir(p(top)):
            continue
        base_depth = p(top).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(p(top)):
            if dirpath.count(os.sep) - base_depth >= max_depth:
                dirnames[:] = []
            yield dirpath, dirnames, filenames


def find_engine_mod():
    """carda jowol's mod: a 'GE Engines' folder containing GE_L_Engine.obj."""
    hits = [d for d, _, files in walk_addons()
            if os.path.basename(d) == "GE Engines" and "GE_L_Engine.obj" in files
            and "GE_R_Engine.obj" in files]
    hits.sort(key=lambda d: ("JAR330 Base Folder" not in d, len(d)))
    return hits[0] if hits else None


def find_ftsim():
    """FTSIM sound pack: a folder holding GEEngines.bank and its A330.snd."""
    for d, _, files in walk_addons():
        if "GEEngines.bank" in files and "A330.snd" in files:
            text, _ = read_text(os.path.join(d, "A330.snd"))
            if FTSIM_MARKER in text:
                return d
    return None


# --------------------------------------------------------------------------------------
# Backup / state
# --------------------------------------------------------------------------------------

def load_state():
    if os.path.isfile(p(STATE_FILE)):
        with open(p(STATE_FILE)) as f:
            return json.load(f)
    return None


def save_state(state):
    os.makedirs(p(BACKUP_DIR), exist_ok=True)
    with open(p(STATE_FILE), "w") as f:
        json.dump(state, f, indent=2)


def backup_path(rel):
    return os.path.join(ROOT, BACKUP_DIR, *rel.split("/"))


def create_backup_from_stock():
    """First run on a fresh copy: keep the untouched stock files."""
    missing = [r for r in BACKUP_FILES if not exists(r)]
    if missing:
        raise SetupError("These stock files are missing, is this really a copy of the "
                         "Laminar A330-300?\n  " + "\n  ".join(missing))
    acf, _ = read_text(p("A330.acf"))
    if "A330_trent_700.obj" not in acf:
        raise SetupError("A330.acf has already been modified (the stock Trent engine is "
                         "not in it). Please start again from a fresh copy of the default "
                         "A330-300.")
    for r in BACKUP_FILES:
        dst = backup_path(r)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(p(r), dst)


def migrate_from_old_install():
    """Folders set up by the earlier install_ge_mod.sh / ge_ecam_patch scripts."""
    say("This folder was set up by the older GE install scripts. Converting it...")
    src = {
        "A330.acf": "A330_GE.acf.bak",
        "fmod/A330.snd": "fmod/A330_GE.snd.bak",
        "fmod/GUIDS.txt": "fmod/GUIDS.txt.bak",
    }
    for r in BACKUP_FILES[3:]:
        src[r] = "_rr_display_backup/" + r if exists("_rr_display_backup/" + r) else r
    for r, s in src.items():
        if not exists(s):
            raise SetupError(f"Can't find an original copy of {r} (looked for {s}). "
                             "Please start again from a fresh copy of the default A330-300.")
    acf, _ = read_text(p(src["A330.acf"]))
    if "A330_trent_700.obj" not in acf:
        raise SetupError(f"{src['A330.acf']} isn't the original aircraft file.")
    if src[BACKUP_FILES[3]] == BACKUP_FILES[3] and exists(ECAM + "/ge_percent-1.png"):
        raise SetupError("The original screen images are missing. Please start again from "
                         "a fresh copy of the default A330-300.")
    for r, s in src.items():
        dst = backup_path(r)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(p(s), dst)
    return {"version": VERSION, "engines": True,
            "sound": FTSIM_MARKER in read_text(p("fmod/A330_GE.snd"))[0],
            "screens": exists(ECAM + "/ge_percent-1.png"), "added": [], "legacy": True}


def cleanup_old_install_files():
    old = ["install_ge_mod.sh", "A330_GE.acf.bak", "fmod/A330_GE.snd.bak",
           "fmod/A330_GE.snd.pre-engine-fix", "fmod/GUIDS.txt.bak"]
    old_dirs = ["ge_ecam_patch", "_rr_display_backup"]
    present = [o for o in old + old_dirs if exists(o)]
    if not present:
        return
    say("\nLeft-over files from the older install scripts:\n  " + "\n  ".join(present))
    if ask("Delete them? (their content is now in _ge_setup_backup)", True):
        for o in old:
            remove(o)
        for o in old_dirs:
            rmtree(o)


def do_renames(to_ge=True):
    for stock, ge in renames():
        a, b = (stock, ge) if to_ge else (ge, stock)
        if exists(a) and not exists(b):
            os.makedirs(os.path.dirname(p(b)), exist_ok=True)
            os.replace(p(a), p(b))


# --------------------------------------------------------------------------------------
# Component 1: GE engine model
# --------------------------------------------------------------------------------------

def patch_acf_engines(lines):
    lat, vert, lng = f"{ENGINE_LAT:.9f}", f"{ENGINE_VERT:.9f}", f"{ENGINE_LONG:.9f}"

    def obj(n, flags, stl, x, y, z):
        return [f"P _obja/{n}/_obj_flags {flags}",
                f"P _obja/{n}/_v10_att_body -1",
                f"P _obja/{n}/_v10_att_file_stl {stl}",
                f"P _obja/{n}/_v10_att_gear -1",
                f"P _obja/{n}/_v10_att_phi_ref 0.000000000",
                f"P _obja/{n}/_v10_att_psi_ref 0.000000000",
                f"P _obja/{n}/_v10_att_the_ref 0.000000000",
                f"P _obja/{n}/_v10_att_wing -1",
                f"P _obja/{n}/_v10_att_x_acf_prt_ref {x}",
                f"P _obja/{n}/_v10_att_y_acf_prt_ref {y}",
                f"P _obja/{n}/_v10_att_z_acf_prt_ref {z}",
                f"P _obja/{n}/_v10_is_internal 0",
                f"P _obja/{n}/_v10_steers_with_gear 0"]

    block = (obj(43, 28, "GE Engines/GE_R_Engine.obj", lat, vert, lng)
             + obj(44, 0, "GE Engines/particles/GE-Particles.obj",
                   "-0.200000003", "0.200000003", "-11.000000000")
             + obj(45, 24, "GE Engines/ge_engine_l_n1.obj", "-" + lat, vert, lng)
             + obj(46, 24, "GE Engines/ge_engine_r_n1.obj", lat, vert, lng))

    repl = {
        "P _obja/6/_v10_att_file_stl A330_trent_700.obj": "P _obja/6/_v10_att_file_stl GE Engines/GE_L_Engine.obj",
        "P _obja/6/_obj_flags 24": "P _obja/6/_obj_flags 28",
        "P _obja/6/_v10_att_x_acf_prt_ref 0.000000000": "P _obja/6/_v10_att_x_acf_prt_ref -" + lat,
        "P _obja/6/_v10_att_y_acf_prt_ref 0.000000000": "P _obja/6/_v10_att_y_acf_prt_ref " + vert,
        "P _obja/6/_v10_att_z_acf_prt_ref 0.000000000": "P _obja/6/_v10_att_z_acf_prt_ref " + lng,
        "P _obja/6/_v10_is_internal 1081147483": "P _obja/6/_v10_is_internal 0",
    }
    out, found = [], set()
    for l in lines:
        if l in repl:
            found.add(l)
            out.append(repl[l])
        elif l == "P _obja/count 43":
            found.add(l)
            out.extend(block)
            out.append("P _obja/count 47")
        else:
            out.append(l)
    if len(found) != len(repl) + 1:
        raise SetupError("The aircraft file doesn't look like the stock A330 (engine object "
                         "entries not found). Is this a different version of the A330?")
    return out


# Engine shake + wing flex, copied from the stock Trent 700 object: the whole engine
# rotates with the wing flex around the wing pivot, then rocks a little on three axes
# from Laminar's own vibration datarefs (still computed by A333.math on this aircraft).
# Pivots/axes are in aircraft coordinates (metres, x right, y up, z aft), extracted from
# A330_trent_700.obj; they are converted into each GE object's own coordinates below.
SHAKE_CHAIN = {
    "L": [
        ("laminar/A333/math/wing_flex_left", (-8.423160, -0.447770, 26.623659), (0.000130, -0.000123, 1.000000),
         [(-13.0, 0.999811), (-12.0, 0.999811), (-7.0, 0.0), (-2.3333335, -0.999811), (2.333333, -2.000196), (7.0, -3.000007), (11.0, -3.000007)]),
        ("laminar/A333/engineL/vibration_x", (-9.304611, -0.338206, 26.897317), (-0.026772, -0.019888, 0.999444),
         [(-1.0, 0.500458), (0.0, 0.0), (1.0, -0.500458)]),
        ("laminar/A333/engineL/vibration_y", (-9.655431, -0.682837, 29.732738), (-0.990702, 0.134849, -0.018049),
         [(-1.0, 0.201741), (0.0, 0.0), (1.0, -0.201741)]),
        ("laminar/A333/engineL/vibration_z", (-9.304599, -0.338211, 26.897318), (-0.000004, -1.000000, 0.000047),
         [(-1.0, 0.500458), (0.0, 0.0), (1.0, -0.500458)]),
    ],
    "R": [
        ("laminar/A333/math/wing_flex_right", (8.423160, -0.447770, 26.623659), (-0.000130, -0.000123, 1.000000),
         [(-13.0, -0.999811), (-12.0, -0.999811), (-7.0, 0.0), (-2.3333335, 0.999811), (2.3333335, 2.000196), (7.0, 3.000007), (11.0, 3.000007)]),
        ("laminar/A333/engineR/vibration_x", (9.304621, -0.338206, 26.897297), (0.026752, -0.019892, 0.999444),
         [(-1.0, -0.498891), (0.0, 0.0), (1.0, 0.498891)]),
        ("laminar/A333/engineR/vibration_y", (9.655398, -0.682845, 29.732733), (-0.990703, -0.134839, 0.018048),
         [(-1.0, 0.197823), (0.0, 0.0), (1.0, -0.197823)]),
        ("laminar/A333/engineR/vibration_z", (9.304574, -0.338216, 26.897313), (0.000005, 1.000000, -0.000047),
         [(-1.0, 0.500458), (0.0, 0.0), (1.0, -0.498892)]),
    ],
}
SHAKE_OBJECTS = {"GE_L_Engine.obj": "L", "ge_engine_l_n1.obj": "L",
                 "GE_R_Engine.obj": "R", "ge_engine_r_n1.obj": "R"}
SHAKE_MARKER = "# ge_setup: engine shake + wing flex"
FT = 0.3048


def patch_engine_shake():
    """Wrap each GE engine object in the stock wing-flex / vibration animation."""
    for name, side in SHAKE_OBJECTS.items():
        path = p("objects/GE Engines/" + name)
        if not os.path.isfile(path):
            continue
        text, nl = read_text(path)
        if SHAKE_MARKER in text:
            continue
        lines = text.rstrip("\r\n").split(nl)
        last_idx = max(i for i, l in enumerate(lines) if l.startswith("IDX"))
        sign = -1 if side == "L" else 1
        attach = (sign * ENGINE_LAT * FT, ENGINE_VERT * FT, ENGINE_LONG * FT)
        anim = [SHAKE_MARKER, "ANIM_begin"]
        for dref, piv, axis, keys in SHAKE_CHAIN[side]:
            q = [piv[k] - attach[k] for k in range(3)]
            fwd = "%.6f %.6f %.6f" % tuple(q)
            back = "%.6f %.6f %.6f" % tuple(-v for v in q)
            anim.append(f"ANIM_trans {fwd} {fwd}")
            anim.append("ANIM_rotate_begin %.6f %.6f %.6f %s" % (*axis, dref))
            anim += [f"ANIM_rotate_key {k} {v}" for k, v in keys]
            anim.append("ANIM_rotate_end")
            anim.append(f"ANIM_trans {back} {back}")
        lines = lines[:last_idx + 1] + anim + lines[last_idx + 1:] + ["ANIM_end", ""]
        write_text(path, nl.join(lines))


LUA_REVERSERS_SRC = r'''--[[
*****************************************************************************************
* Program Script Name	:	A333.zz_ge_reversers   (installed by ge_setup.py)
*
* Purpose				:	The GE engine objects (carda jowol mod, made for the
*							JARDesign A330) animate the reverser sleeve and blocker
*							doors from JAR's datarefs (0 = stowed, 1 = deployed).
*							Feed them from X-Plane's own reverser position.
*****************************************************************************************
--]]

simDR_rev_deploy		= find_dataref("sim/flightmodel2/engines/thrust_reverser_deploy_ratio")

A333DR_ge_rev_l			= create_dataref("sim/custom/xap/anim/rev_l", "number")
A333DR_ge_rev_r			= create_dataref("sim/custom/xap/anim/rev_r", "number")

function after_physics()
	A333DR_ge_rev_l = simDR_rev_deploy[0]
	A333DR_ge_rev_r = simDR_rev_deploy[1]
end
'''


# --------------------------------------------------------------------------------------
# Component 2: FTSIM sound pack
# --------------------------------------------------------------------------------------

# Header comment inside FTSIM's own A330.snd (their wording, for the A330 GE pack too).
# Used only to recognise their file and find where their sound block starts.
FTSIM_MARKER = "x_A330 Sound Pack (NEO)"
FTSIM_BANKS = ["GEEngines.bank", "Weather.bank"]


def patch_sound(snd, ftsim_dir):
    ft_snd, _ = read_text(os.path.join(ftsim_dir, "A330.snd"))
    ft_lines = ft_snd.split("\n")
    start = next(i for i, l in enumerate(ft_lines) if FTSIM_MARKER in l)
    start = max(0, start - 3)

    # mute the stock Trent engine sounds so they don't play under the GE ones
    lines = snd.split("\n")
    out, i, muted = [], 0, 0
    while i < len(lines):
        if lines[i].strip() == "BEGIN_SOUND_ATTACHMENT":
            j = i
            while j < len(lines) and lines[j].strip() != "END_SOUND_ATTACHMENT":
                j += 1
            blk = lines[i:j + 1]
            if any(re.match(r"\s*EVENT_NAME /a330/engines/engine_[12]\s*$", l) for l in blk):
                blk = ["#" + l for l in blk]
                muted += 1
            out.extend(blk)
            i = j + 1
        else:
            out.append(lines[i])
            i += 1
    if muted != 2:
        say(f"  Note: expected to mute 2 stock engine sounds, muted {muted}.")
    return "\n".join(out).rstrip("\r\n") + "\n\n" + "\n".join(ft_lines[start:])


def patch_guids(guids, ftsim_dir):
    ft, _ = read_text(os.path.join(ftsim_dir, "GUIDS.txt"))
    have = set(guids.splitlines())
    new = [l for l in ft.splitlines()
           if l not in have and ("GE_Mod" in l or "Weather/Wind" in l)]
    if not new:
        return guids
    return guids.rstrip("\r\n") + "\n" + "\n".join(new) + "\n"


# --------------------------------------------------------------------------------------
# Component 3: GE cockpit screens (ECAM)
# --------------------------------------------------------------------------------------

HDR = re.compile(r"^(\s*)(gen_\w+) (.*)$")
N1_KF = [(0, -25), (20, -25), (100, 157), (117, 195.675)]   # needle angles, 2.275 deg/%

MOVE = {
    # E/WD: N1 dial moves up into the EPR dial position, N1 digits into the EPR box
    "N1 eng1_needle": (0, 165), "N1 eng1_needle red": (0, 165),
    "N1 eng2_needle": (0, 165), "N1 eng2_needle red": (0, 165),
    "N1 eng1": (-3, 157), "N1 eng1 red": (-3, 157),
    "N1 eng2": (-3, 157), "N1 eng2 red": (-3, 157),
    "XX N1 1": (-4, 157), "XX N1 2": (-4, 157),
    # N2 (stock "N3" HP spool readout) and fuel flow become centre digital rows
    "N3 eng1": (120, 32.5), "N3 grey1": (120, 32.5), "XX N3 1": (120, 32.5),
    "N3 eng2": (-116, 32.5), "N3 grey2": (-116, 32.5), "XX N3 2": (-116, 32.5),
    "FF eng1": (115, -56.5), "XX FF 1": (115, -56.5),
    "FF eng2": (-120, -56.5), "XX FF 2": (-120, -56.5),
    # SD ENGINE / CRUISE: GE is 2-spool, VIB N2 = HP spool (was the N3 row)
    "VIB N3 eng1": (0, 21), "VIB N3 eng2": (0, 21),
    "XX Vib31": (0, 21), "XX Vib32": (0, 21),
}
DELETE = ["EPR1_needle", "EPR2_needle", "EPR eng1", "EPR eng2",
          "N2 eng1", "N2 eng2", "XX N2_eng1", "XX N2_eng2",
          "VIB N2 eng1", "VIB N2 eng2", "XX Vib21", "XX Vib22"]
REDATA = {
    "EPR1_setting": "laminar/A333/ge/n1_donut_eng1",
    "EPR2_setting": "laminar/A333/ge/n1_donut_eng2",
    "EPR1_limit": "laminar/A333/ge/n1_limit",
    "EPR2_limit": "laminar/A333/ge/n1_limit",
}
N1_NEEDLES = ["N1 eng1_needle", "N1 eng1_needle red", "N1 eng2_needle", "N1 eng2_needle red"]
N1_ALL = N1_NEEDLES + ["N1 eng1", "N1 eng1 red", "N1 eng2", "N1 eng2 red"]
EXPECTED = {"deleted": 36, "moved": 92, "redata": 16, "n1_disp": 32, "thrust_limit": 4}


def _match(base, name):
    return name == base or name.startswith(base + " 2")


def _lookup(names, name):
    for base in sorted(names, key=len, reverse=True):
        if _match(base, name):
            return base
    return None


def patch_acf_screens(lines):
    out, i, stats, flex_block, pct_n = [], 0, dict.fromkeys(EXPECTED, 0), None, 0

    def kf_lines(sub):
        res = []
        for k, (v, a) in enumerate(N1_KF):
            tail = " 1.000000" if k < len(N1_KF) - 1 else ""
            res.append(f"{sub}KEY_FRAME {v:.6f} {a:.6f}{tail}")
        return res

    def set_kf(block, sub):
        first = next(k for k, l in enumerate(block) if l.strip().startswith("KEY_FRAME"))
        rest = [l for l in block if not l.strip().startswith("KEY_FRAME")]
        return rest[:first] + kf_lines(sub) + rest[first:]

    while i < len(lines):
        m = HDR.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j].strip() != "":
            j += 1
        block = lines[i:j]
        ind, name = m.group(1), m.group(3)
        sub = ind + "  "

        if _lookup(DELETE, name):
            stats["deleted"] += 1
            i = j + 1
            continue

        base = _lookup(MOVE, name)
        if base:
            dx, dy = MOVE[base]
            for k, l in enumerate(block):
                pm = re.match(r"^(\s*)POS (\S+) (\S+)$", l)
                if pm:
                    block[k] = f"{pm.group(1)}POS {float(pm.group(2)) + dx:.6f} {float(pm.group(3)) + dy:.6f}"
            stats["moved"] += 1

        rd = _lookup(REDATA, name)
        if rd:
            block = [f"{sub}DATAREF {REDATA[rd]}" if l.strip().startswith("DATAREF") else l
                     for l in block]
            block = set_kf(block, sub)
            stats["redata"] += 1
        elif _lookup(N1_NEEDLES, name):
            block = set_kf(block, sub)

        # N1 needle + digits show the GE N1 value; CF6-80E1 redline is 115.5 %
        if _lookup(N1_ALL, name):
            block = [l.replace("sim/cockpit2/engine/indicators/N1_percent[", "laminar/A333/ge/n1_disp[")
                      .replace(" 99.000000 ", " 115.500000 ") for l in block]
            stats["n1_disp"] += 1

        if _match("Flex deg", name):
            flex_block = list(block)

        if _match("Thrust Limit", name):
            if flex_block is None:
                raise SetupError("panel layout not as expected (FLX label not found)")
            rep = {"DATAREF": "DATAREF laminar/A333/ge/n1_limit",
                   "IMAGE": "IMAGE LED/airbus_display_LED_18_16dec_green",
                   "DIGITS": "DIGITS 4", "DECIMALS": "DECIMALS 1",
                   "PERIOD_WIDTH": "PERIOD_WIDTH 9", "LED_ROWS": "LED_ROWS 4"}
            block = [sub + rep[l.strip().split(" ")[0]] if l.strip().split(" ")[0] in rep else l
                     for l in block]
            out.extend(block)
            out.append("")
            # cyan "%" after the N1 thrust limit, cloned from the FLX "deg C" label
            pos = next(l for l in block if l.strip().startswith("POS")).split()
            px, py = float(pos[1]) + 35.0, float(pos[2])
            for l in flex_block:
                s = l.strip()
                if HDR.match(l):
                    out.append(f"{ind}gen_rotary GE N1 pct" + " 2" * pct_n)
                elif s.startswith("POS"):
                    out.append(f"{sub}POS {px:.6f} {py:.6f}")
                elif s.startswith("IMAGE"):
                    out.append(f"{sub}IMAGE ECAM/ge_percent")
                elif s.startswith("SHOW_"):
                    out.append(f"{sub}SHOW_EQUAL 1.000000 laminar/A333/ecam/engine_display")
                else:
                    out.append(sub + l.lstrip())
            out.append("")
            pct_n += 1
            stats["thrust_limit"] += 1
            i = j + 1
            continue

        out.extend(block)
        i = j

    if stats != EXPECTED:
        raise SetupError("The cockpit display layout in this A330 version differs from what "
                         f"the screen patch expects ({stats} vs {EXPECTED}).")
    return out


def make_screen_images():
    bg_orig = png_read(backup_path(ECAM + "/background-1.png"))
    sd_orig = png_read(backup_path(ECAM_SD + "/ENGINE/engine_background-1.png"))
    WHITE, RED = (255, 255, 255, 255), (255, 30, 30, 255)

    # ---- upper ECAM background ----
    bg = bg_orig.copy()
    for box in [(225, 3, 262, 20),     # EPR label
                (0, 100, 72, 120),     # FF KG/H left
                (408, 100, 480, 120),  # FF KG/H right
                (20, 158, 62, 176),    # N3 % left
                (430, 158, 472, 176),  # N3 % right
                (95, 136, 195, 210),   # lower N1 dial left
                (291, 136, 391, 210),  # lower N1 dial right
                (232, 173, 258, 205)]: # N1 % centre label
        bg.erase(*box)
    bg.paste(bg_orig.crop(235, 175, 255, 189), 235, 2)      # "N1" at top
    bg.paste(bg_orig.crop(240, 191, 249, 202), 240, 19)     # "%"
    bg.paste(sd_orig.crop(55, 1, 76, 14), 230, 141)         # "N2"
    bg.paste(bg_orig.crop(50, 162, 59, 173), 236, 156)      # "%"
    bg.paste(bg_orig.crop(5, 103, 25, 116), 230, 173)       # "FF"
    bg.paste(bg_orig.crop(30, 104, 67, 116), 222, 189)      # "KG/H"
    for a, b in [((196, 152), (220, 145)), ((284, 152), (260, 145)),
                 ((196, 186), (216, 178)), ((284, 186), (264, 178))]:
        draw_line(bg, a, b, 2, WHITE)
    png_write(p(ECAM + "/background-1.png"), bg)

    # ---- top dial arc: EPR -> N1 (frame 2 of EPR_arc) ----
    arc = png_read(backup_path(ECAM + "/EPR_arc-1.png"))
    arc.erase(100, 0, 200, 84)
    arc.paste(bg_orig.crop(95, 136, 195, 220), 100, 0)      # stock N1 dial art
    # CF6-80E1 N1 redline is 115.5 %: turn the stock red zone white, continue the arc
    # to the redline and put a short red zone there. Needle 0 deg points left, so
    # screen angle = 180 - needle angle. Dial pivot in frame 2 is (150, 47).
    PX, PY = 150, 47

    def ang_of(n1):
        return 180 - (157 + (n1 - 100) * 2.275)

    for y in range(arc.h):
        for x in range(100, 200):
            r, g, b, a = arc.get(x, y)
            if a == 0:
                continue
            if r > 180 and g < 140:
                arc.set(x, y, (255, 255, 255, a))
            d = math.hypot(x - PX, y - PY)
            ang = math.degrees(math.atan2(PY - y, x - PX))
            if d >= 37 and -25 <= ang <= 20:
                arc.set(x, y, (0, 0, 0, 0))
    draw_arc(arc, PX, PY, 43.5, 22, ang_of(114.3), 2.6, WHITE)
    draw_arc(arc, PX, PY, 43.5, ang_of(114.3), ang_of(116.5), 4.2, RED)
    ea = math.radians(ang_of(116.5))
    draw_line(arc, (PX + 38 * math.cos(ea), PY - 38 * math.sin(ea)),
              (PX + 45.5 * math.cos(ea), PY - 45.5 * math.sin(ea)), 2.2, RED)
    png_write(p(ECAM + "/EPR_arc-1.png"), arc)

    # ---- cyan "%" for the thrust limit readout ----
    pct = Image(14, 14)
    pct.paste(bg_orig.crop(50, 162, 59, 173), 2, 2)
    png_write(p(ECAM + "/ge_percent-1.png"), pct)
    png_write(p(ECAM + "/ge_percent.png"), Image(14, 14))   # size placeholder

    # ---- lower ECAM: ENGINE page (no N2 row, no VIB N3) ----
    sd = sd_orig.copy()
    sd.erase(0, 0, 128, 35)
    sd.erase(0, 305, 128, 320)
    png_write(p(ECAM_SD + "/ENGINE/engine_background-1.png"), sd)

    # ---- lower ECAM: CRUISE page (no VIB N3) ----
    cr = png_read(backup_path(ECAM_SD + "/CRUISE/cruise_bg-1.png"))
    cr.erase(180, 212, 320, 233)
    png_write(p(ECAM_SD + "/CRUISE/cruise_bg-1.png"), cr)


LUA_DISPLAY_SRC = r'''--[[
*****************************************************************************************
* Program Script Name	:	A333.zz_ge_display   (installed by ge_setup.py)
*
* Purpose				:	GE CF6-80E1 E/WD support. The flight model / FADEC stays
*							EPR-driven (stock Trent 700 logic), whose raw fan N1 tops
*							out around 88-91 % - Trent numbers, not CF6 ones.
*
*							So the E/WD shows a GE N1 derived from EPR. EPR behaves like
*							a corrected (temperature-normalised) parameter, so it is
*							mapped to corrected N1 and converted to physical N1 the way
*							a real fan behaves:  N1 = N1k(EPR) * sqrt(TAT_K / 288.15)
*							Without this, Trent climb EPR at altitude (~1.65) is higher
*							than sea-level TOGA EPR (~1.60) and climb would read above
*							takeoff.
*
*							Calibration (CF6-80E1, see README_GE_SETUP.md):
*							  TOGA sea level: ~100.7 % at 15 C, ~103 % at 30-36 C
*							  (flat-rate corner), 102.5 % at 40 C (Airbus data point)
*							  CLB ~90-91 % at sea level, ~97 % at FL100, ~101 % mid
*							  altitudes, ~96 % high up; cruise ~86-90 %;
*							  ground idle ~21-23 %; redline 115.5 %
*
*							Actual N1, thrust lever command (donut) and thrust limit
*							all go through the same conversion, so they stay
*							consistent and move smoothly. Below idle (start /
*							shutdown) the raw sim N1 is shown, blended into the
*							schedule as the engine reaches idle.
*****************************************************************************************
--]]

-- EPR -> GE corrected N1 % (N1k), i.e. physical N1 at TAT = 15 C
local schedule = {
	{1.000,  21.0}, {1.020,  26.0}, {1.050,  36.0}, {1.100,  50.0},
	{1.200,  66.0}, {1.300,  79.0}, {1.400,  89.5}, {1.450,  92.5},
	{1.500,  95.0}, {1.550,  97.0}, {1.576,  98.3}, {1.596, 100.7},
	{1.650, 103.5}, {1.720, 106.5},
}

local BLEND_LO = 12.0		-- raw N1 below this: show raw N1 only
local BLEND_HI = 18.0		-- raw N1 above this: show schedule only

simDR_EPR				= find_dataref("sim/cockpit2/engine/indicators/EPR_ratio")
simDR_N1				= find_dataref("sim/cockpit2/engine/indicators/N1_percent")
simDR_FADEC_EPR_cmd		= find_dataref("sim/flightmodel2/engines/EPR_FADEC")
simDR_TAT				= find_dataref("sim/weather/aircraft/temperature_leadingedge_deg_c")

A333DR_thrust_limit_epr	= find_dataref("laminar/A333/ecam/thrust_limit_epr")

A333DR_ge_n1_disp			= create_dataref("laminar/A333/ge/n1_disp", "array[2]")
A333DR_ge_n1_donut_eng1		= create_dataref("laminar/A333/ge/n1_donut_eng1", "number")
A333DR_ge_n1_donut_eng2		= create_dataref("laminar/A333/ge/n1_donut_eng2", "number")
A333DR_ge_n1_limit			= create_dataref("laminar/A333/ge/n1_limit", "number")

local theta_sqrt = 1.0		-- sqrt(TAT_K / 288.15), updated every frame

local function epr_to_n1(epr)
	local n1k
	if epr <= schedule[1][1] then
		n1k = schedule[1][2]
	elseif epr >= schedule[#schedule][1] then
		n1k = schedule[#schedule][2]
	else
		for i = 2, #schedule do
			if epr <= schedule[i][1] then
				local a, b = schedule[i-1], schedule[i]
				n1k = a[2] + (b[2] - a[2]) * (epr - a[1]) / (b[1] - a[1])
				break
			end
		end
	end
	return n1k * theta_sqrt
end

local function n1_display(eng)
	local raw = simDR_N1[eng]
	local w = math.max(0, math.min(1, (raw - BLEND_LO) / (BLEND_HI - BLEND_LO)))
	local ge = math.max(raw, epr_to_n1(simDR_EPR[eng]))
	return raw + (ge - raw) * w
end

function after_physics()
	theta_sqrt = math.sqrt(math.max(200.0, simDR_TAT + 273.15) / 288.15)

	A333DR_ge_n1_disp[0] = n1_display(0)
	A333DR_ge_n1_disp[1] = n1_display(1)

	A333DR_ge_n1_donut_eng1 = simDR_FADEC_EPR_cmd[0] == 0 and 0 or epr_to_n1(simDR_FADEC_EPR_cmd[0])
	A333DR_ge_n1_donut_eng2 = simDR_FADEC_EPR_cmd[1] == 0 and 0 or epr_to_n1(simDR_FADEC_EPR_cmd[1])

	A333DR_ge_n1_limit = epr_to_n1(A333DR_thrust_limit_epr)
end
'''


def write_lua(folder, src):
    name = os.path.basename(folder)
    write_text(os.path.join(p(folder), name + ".lua"), src)


# --------------------------------------------------------------------------------------
# Main flows
# --------------------------------------------------------------------------------------

def rename_acf_fields(lines):
    out = []
    for l in lines:
        if l.startswith("P acf/_name "):
            l = "P acf/_name " + GE_NAME
        elif l.startswith("P acf/_descrip "):
            l = "P acf/_descrip " + GE_DESCRIP
        out.append(l)
    return out


def apply(state, want, engine_dir, ftsim_dir):
    added = set(state.get("added", []))

    # ---- aircraft file: always rebuilt from the untouched stock copy ----
    acf, nl = read_text(backup_path("A330.acf"))
    lines = acf.split(nl)

    if want["engines"]:
        say("- Installing GE engine model...")
        lines = patch_acf_engines(lines)
        if engine_dir:
            shutil.copytree(engine_dir, p("objects/GE Engines"), dirs_exist_ok=True)
            added.add("objects/GE Engines")
        elif not exists("objects/GE Engines/GE_L_Engine.obj"):
            raise SetupError("GE engine files not found.")
        patch_engine_shake()
        write_lua(LUA_REVERSERS, LUA_REVERSERS_SRC)
    else:
        rmtree(LUA_REVERSERS)
        if "objects/GE Engines" in added:
            rmtree("objects/GE Engines")
            added.discard("objects/GE Engines")

    screens_ok = want["screens"]
    if want["screens"]:
        say("- Converting cockpit screens to GE layout (takes a few seconds)...")
        try:
            lines = patch_acf_screens(lines)
            make_screen_images()
            write_lua(LUA_DISPLAY, LUA_DISPLAY_SRC)
        except SetupError as e:
            say(f"  Screen conversion skipped: {e}")
            screens_ok = False
    if not screens_ok:
        for r in BACKUP_FILES[3:]:
            shutil.copy2(backup_path(r), p(r))
        remove(ECAM + "/ge_percent-1.png")
        remove(ECAM + "/ge_percent.png")
        rmtree(LUA_DISPLAY)

    lines = rename_acf_fields(lines)
    write_text(p("A330_GE.acf"), nl.join(lines))

    # ---- sound ----
    snd, snl = read_text(backup_path("fmod/A330.snd"))
    guids, gnl = read_text(backup_path("fmod/GUIDS.txt"))
    if want["sound"]:
        say("- Installing FTSIM GE sound pack...")
        if not ftsim_dir:
            raise SetupError("FTSIM sound pack folder not found.")
        snd = patch_sound(snd.replace(snl, "\n"), ftsim_dir).replace("\n", snl)
        guids = patch_guids(guids.replace(gnl, "\n"), ftsim_dir).replace("\n", gnl)
        for b in FTSIM_BANKS:
            if not exists("fmod/" + b):
                shutil.copy2(os.path.join(ftsim_dir, b), p("fmod/" + b))
                added.add("fmod/" + b)
    else:
        for b in FTSIM_BANKS:
            if "fmod/" + b in added:
                remove("fmod/" + b)
                added.discard("fmod/" + b)
    write_text(p("fmod/A330_GE.snd"), snd)
    write_text(p("fmod/GUIDS.txt"), guids)

    state.update({"version": VERSION, "engines": want["engines"], "sound": want["sound"],
                  "screens": screens_ok, "added": sorted(added)})
    state.pop("legacy", None)
    save_state(state)


def restore_stock(state):
    say("\nPutting the aircraft back to the default Laminar A330-300...")
    for r in BACKUP_FILES[3:]:
        shutil.copy2(backup_path(r), p(r))
    remove(ECAM + "/ge_percent-1.png")
    remove(ECAM + "/ge_percent.png")
    rmtree(LUA_DISPLAY)
    rmtree(LUA_REVERSERS)
    for a in state.get("added", []):
        rmtree(a) if os.path.isdir(p(a)) else remove(a)
    remove("A330_GE.acf")
    remove("fmod/A330_GE.snd")
    do_renames(to_ge=False)
    shutil.copy2(backup_path("A330.acf"), p("A330.acf"))
    shutil.copy2(backup_path("fmod/A330.snd"), p("fmod/A330.snd"))
    shutil.copy2(backup_path("fmod/GUIDS.txt"), p("fmod/GUIDS.txt"))
    shutil.rmtree(p(BACKUP_DIR))
    say("Done. The folder is the default A330-300 again (you can delete the add-on "
        "folders and this script if you like).")


def status(on):
    return "installed" if on else "not installed"


def main():
    say(f"A330-300 GE setup {VERSION}")
    say("=" * 40)
    say(f"Aircraft folder: {ROOT}\n")

    state = load_state()
    if state is None:
        if exists("A330.acf"):
            create_backup_from_stock()
            state = {"version": VERSION, "engines": False, "sound": False,
                     "screens": False, "added": []}
            do_renames(to_ge=True)
            save_state(state)
        elif exists("A330_GE.acf") and exists("A330_GE.acf.bak"):
            state = migrate_from_old_install()
            do_renames(to_ge=True)
            save_state(state)
        else:
            raise SetupError(
                "No A330.acf in this folder.\nPut ge_setup.py inside your COPY of the "
                "default 'Airbus A330-300' aircraft folder and run it from there.")
    else:
        do_renames(to_ge=True)
        say("This aircraft has been set up before. Current state:")
        for k, label in (("engines", "GE engine model"), ("sound", "FTSIM sound pack"),
                         ("screens", "GE cockpit screens")):
            say(f"  {label:<20} {status(state.get(k))}")
        say("")
        if ask("Put the aircraft back to the default Laminar A330 (remove everything)?", False):
            restore_stock(state)
            return

    engine_dir = find_engine_mod()
    ftsim_dir = find_ftsim()
    have_engines = engine_dir is not None or exists("objects/GE Engines/GE_L_Engine.obj")

    say("Found add-ons:")
    say(f"  GE engine model (carda jowol):  {os.path.relpath(engine_dir, ROOT) if engine_dir else ('already copied' if have_engines else 'NOT FOUND')}")
    say(f"  FTSIM GE sound pack:            {os.path.relpath(ftsim_dir, ROOT) if ftsim_dir else 'NOT FOUND'}")
    say("")

    want = {}
    if have_engines:
        want["engines"] = ask("1) Install the GE engine model?", True)
    else:
        say("1) GE engine model: folder not found, skipping (see README).")
        want["engines"] = False
    if ftsim_dir:
        want["sound"] = ask("2) Install the FTSIM GE sound pack?", True)
    else:
        say("2) FTSIM sound pack: folder not found, skipping (see README).")
        want["sound"] = False
    want["screens"] = ask("3) Convert the cockpit screens to the GE layout?", True)
    say("")

    apply(state, want, engine_dir, ftsim_dir)

    if state.get("version") and any(exists(o) for o in ("install_ge_mod.sh", "ge_ecam_patch",
                                                         "_rr_display_backup")):
        cleanup_old_install_files()

    say("\nAll done!")
    say(f"  GE engine model     {status(state['engines'])}")
    say(f"  FTSIM sound pack    {status(state['sound'])}")
    say(f"  GE cockpit screens  {status(state['screens'])}")
    say(f"\nStart X-Plane and pick '{GE_NAME}' from the aircraft list.")
    say("Run this script again any time to change or undo these choices.")


if __name__ == "__main__":
    ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    code = 0
    try:
        main()
    except SetupError as e:
        say(f"\nERROR: {e}")
        code = 1
    except KeyboardInterrupt:
        say("\nCancelled.")
        code = 1
    except Exception:
        import traceback
        traceback.print_exc()
        say("\nSomething unexpected went wrong (details above). Nothing in "
            "_ge_setup_backup was lost - you can run the script again.")
        code = 1
    if sys.stdin.isatty() and os.name == "nt":
        input("\nPress Enter to close this window...")
    sys.exit(code)
