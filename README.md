# A330-300 GE setup for X-Plane 12

This turns X-Plane 12's default **Airbus A330-300** (Rolls-Royce engines) into an
**A330-300 with GE CF6-80E1 engines**. You end up with a second aircraft in your list
called **"Airbus A330-300 GE"**. The original A330 is not touched.

You can choose any of these three parts:

| Part | What you get | What you need |
|---|---|---|
| **1. GE engine model** | GE engines on the wings instead of the Rolls-Royce ones, with working thrust reversers, engine shake and wing flex like the default engines | carda jowol's [General Electric CF6-80E1 Engine Mod for JAR330](https://forum.thresholdx.net/files/file/567-general-electric-cf6-80e1-engine-mod-for-jar330/) (free) |
| **2. FTSIM sound pack** | GE engine sounds | [FTSIM+ Sounds A330 GE sound pack](https://www.patreon.com/FTSIM/posts/a330-310ge-sp-x-37803750) (payware) |
| **3. GE cockpit screens** | The engine displays look like a real GE A330: N1 as the main gauge, GE-style numbers, GE limits | nothing, it's built in |

---

## What you need

- **X-Plane 12**
- **Python 3**, a free program that runs the setup. See step 1.
- The add-ons for parts 1 and 2, if you want them. You can skip either one.
  - **GE engines (free):** [General Electric CF6-80E1 Engine Mod for JAR330](https://forum.thresholdx.net/files/file/567-general-electric-cf6-80e1-engine-mod-for-jar330/). Download it from that page.
    It says "for JAR330", but you don't need the JARDesign A330.
    The script installs it into the default Laminar A330.
  - **GE sounds (paid):** [FTSIM+ Sounds A330 GE sound pack](https://www.patreon.com/FTSIM/posts/a330-310ge-sp-x-37803750). Buy and download it from FTSIM's site.

---

## Step by step

### Step 1: Install Python (one time only)

- **Windows:** go to <https://www.python.org/downloads/> and click the big yellow
  "Download Python" button. Run the installer.
  **Important:** on the first installer screen, tick the box
  **"Add python.exe to PATH"**, then click "Install Now".
- **Mac:** go to <https://www.python.org/downloads/>, download it and install it like
  any other program.
- **Linux:** Python is almost always installed already.

### Step 2: Make a copy of the default A330

1. Open your X-Plane 12 folder. With Steam it's usually
   `C:\Program Files (x86)\Steam\steamapps\common\X-Plane 12`.
   (In Steam: right-click X-Plane 12 → Manage → Browse local files.)
2. Open **Aircraft**, then **Laminar Research**.
3. Find the folder **Airbus A330-300**. **Copy** it (right-click → Copy).
4. Go back to the **Aircraft** folder and **paste** it there (right-click → Paste).
5. Rename the copy to **Airbus A330-300 GE** (right-click → Rename).

From now on, everything happens inside **this copy**. Never change the original.

### Step 3: Put the files into the copy

Put these into your new **Airbus A330-300 GE** folder:

1. **This setup script:** `ge_setup.py`, and this README if you like.
2. **The GE engine mod (for part 1):** unzip carda jowol's download and drop the
   **whole unzipped folder** (for example `GE_CF6_330_mod_1.1.1`) into the copy.
   You don't need to dig inside it, the script finds what it needs.
3. **The FTSIM A330 GE sound pack (for part 2):** unzip it and drop the **whole unzipped folder**
   (for example `xA330GE_Sp(v1.03)(Lam)`) into the copy.

Folder names don't matter. The script looks inside the folders to find the right files.

When you're done, the folder should look roughly like this:

```
Airbus A330-300 GE\
├── A330.acf                     <- was already there
├── cockpit_3d\                  <- was already there
├── fmod\                        <- was already there
├── ... other A330 files ...
├── ge_setup.py                  <- you added this
├── GE_CF6_330_mod_1.1.1\        <- you added this (engines)
└── xA330GE_Sp(v1.03)(Lam)\      <- you added this (sounds)
```

### Step 4: Run the setup

- **Windows:** double-click **`ge_setup.py`**.
  If that opens a text editor instead, right-click it → **Open with** → **Python**.
- **Mac:** open **Terminal** (search for it with Spotlight). Type `python3`
  followed by a space, **drag `ge_setup.py` into the Terminal window**, and press
  **Enter**.
- **Linux:** open a terminal in the folder and type `python3 ge_setup.py`.

A black window opens and asks up to three questions, for example:

```
1) Install the GE engine model? [Y/n]
```

Press **Enter** for **yes**, or type **n** and press **Enter** for **no**.
A part whose files weren't found is skipped automatically.

It finishes in a few seconds and says **"All done!"**.

### Step 5: Fly

Start X-Plane, open the aircraft list and pick **"Airbus A330-300 GE"**.

---

## Changing your mind later

Run `ge_setup.py` again, the same way as in step 4. It shows what's installed and
asks again:

- Answer **yes** to add a part, or **no** to remove it.
- It first asks whether to **put the aircraft back to the default A330**. Answer **y**
  to undo everything.

The script keeps an untouched copy of every file it changes in a folder called
**`_ge_setup_backup`**. **Don't delete that folder.** The script needs it to change or
undo things.

---

## Problems?

| What you see | What to do |
|---|---|
| **"No A330.acf in this folder"** | `ge_setup.py` isn't in your A330 copy. Move it into the **Airbus A330-300 GE** folder (step 3). |
| **"A330.acf has already been modified"** | This copy was already changed by something else. Delete it and make a fresh copy (step 2). |
| **"GE engine model: folder not found"** | The engine mod isn't in the folder, or it's still zipped. Unzip it and put the whole folder inside the copy. |
| **"FTSIM sound pack: folder not found"** | Same as above, for the sound pack. |
| **Windows: "python is not recognized"**, or nothing happens | Reinstall Python and tick **"Add python.exe to PATH"** (step 1). |
| **The window flashes and closes** | Open a Command Prompt in the folder (type `cmd` in Explorer's address bar and press Enter), then type `python ge_setup.py` to see the message. |
| **"Screen conversion skipped"** | Your A330 version differs from the one this was made for. Everything else still installs. The screens just stay Rolls-Royce style. |
| **The plane doesn't appear in X-Plane** | Restart X-Plane. Check that the folder is directly inside `Aircraft`. |

**After an X-Plane update:** Steam updates the original A330, not your GE copy. To get
the update into the GE version, delete the GE copy and repeat steps 2–4. Your add-on
folders can be reused.

---

## What exactly does it change? (for the curious)

- **Name:** renames `A330.acf` to `A330_GE.acf`, plus its sound and settings files, and
  sets the name in the list to "Airbus A330-300 GE". This keeps X-Plane's settings for
  the two planes apart.
- **Engines:** swaps the Rolls-Royce engine 3D model for carda jowol's GE model. A small
  script (`plugins/xlua/scripts/A333.zz_ge_reversers`) makes its reversers open and
  close with reverse thrust. The mod was originally made for the JARDesign A330, so this
  connection wasn't there by default.
  It also gives the GE engines the default A330's engine shake (they rock slightly with
  engine vibration) and makes them move with the wing as it flexes, using the same
  pivots and values as the stock engines.
- **Sounds:** adds FTSIM's GE engine sounds and mutes the stock Rolls-Royce engine
  sounds so they don't play on top.
- **Screens:**
  - Upper ECAM: the EPR gauge is replaced by the GE **N1** gauge, and N2 and fuel flow
    become numbers in the middle.
  - Thrust limit is shown as N1 %, and the N1 red line moves to the GE value of
    **115.5 %**.
  - Lower ECAM, ENGINE and CRUISE pages: the third (N3) rows are removed, because the GE
    engine has two spools, not three.
  - A small script (`plugins/xlua/scripts/A333.zz_ge_display`) works out the GE N1
    values.

**Not changed:** how the plane flies. Thrust, fuel burn and engine behaviour are still
the default Laminar model. Only what you see and hear changes.

### How the GE N1 numbers are worked out

Underneath, the default engine is controlled by EPR (a Rolls-Royce-style thrust
setting), and its own N1 only reaches about 88–91 % at full power. GE engines run at
higher N1. So the displayed N1 is calculated from EPR and corrected for air temperature,
the way a real fan behaves:

    N1 = N1k(EPR) × √(TAT in kelvin / 288.15)

It's calibrated to published CF6-80E1 figures:

| Condition (standard day) | Displayed N1 |
|---|---|
| TOGA, sea level, 15 °C / 30 °C / 40 °C | 100.7 / 103.3 / 102.5 % |
| Climb at sea level / FL100 / FL150 / FL250–390 | 90 / ~96 / 100 / ~95–96 % |
| Cruise, FL350 | ~86–90 % |
| Ground idle | ~21–23 % |

| CF6-80E1 data | Value | Source |
|---|---|---|
| N1 red line | 115.5 % | A330 GE CF6-80E1 power plant training manual |
| EGT limit, takeoff / max continuous | 975 °C / 940 °C | same |
| A330-301, CF6-80E1A2, FLEX 40 °C, sea level, 15 °C | N1 102.5 % | Airbus "Takeoff Safety", appendix 4-H |
| Cruise FL290, 130 t, M0.80 | N1 88.1 % | A330 GE FCOM example |

I couldn't find a public GE climb N1 table, so climb values follow from the default
climb thrust table run through the same calculation.

Sources:
- <https://pdfcoffee.com/a330ge-7180-ge-cf6-80e1-power-plant-pdf-free.html>
- <https://skybrary.aero/sites/default/files/bookshelf/3685.pdf>
- <https://community.infiniteflight.com/t/a330-200-300-n1-altitude-fuel-flow-charts/1186663>
- <https://www.geaerospace.com/sites/default/files/datasheet-CF6-80E1.pdf>

---

## Credits

- **Laminar Research:** the default A330-300.
- **carda jowol (Daniel Carley):** [General Electric CF6-80E1 Engine Mod for JAR330](https://forum.thresholdx.net/files/file/567-general-electric-cf6-80e1-engine-mod-for-jar330/).
- **FTSIM+ Sounds:** [FTSIM+ Sounds A330 GE sound pack](https://www.patreon.com/FTSIM/posts/a330-310ge-sp-x-37803750).

The add-ons belong to their authors. This setup doesn't include any of their files. It
only installs the copies you got yourself from the links above. Please don't share
their files. If you like their work, support them (the engine mod's manual has a
donation link).

This setup is an unofficial community tool. It isn't affiliated with or endorsed by
Laminar Research, carda jowol or FTSIM+ Sounds.
