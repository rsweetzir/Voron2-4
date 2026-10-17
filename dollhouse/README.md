# Dollhouse (1:12 scale)

Parts, notes and print settings for a 1:12 scale dollhouse printed on this Voron. 1:12 is
the common dollhouse scale: one real foot is one scale inch, so real sizes divide by 12
(1 real inch = 2.117 mm).

## 1:12 scale dimensional lumber

North American lumber is sold by a **nominal** size (the rough-sawn size) and is planed
to a smaller **actual** size. The 1:12 sizes below are the actual sizes scaled down, which is
what real framing and trim measure.

| Nominal size | Actual real-world size (thickness × width) | 1:12 scale (thickness × width) |
|---|---|---|
| 1x2 | 0.75" × 1.50" | 1.59 mm × 3.18 mm |
| 1x3 | 0.75" × 2.50" | 1.59 mm × 5.29 mm |
| 1x4 | 0.75" × 3.50" | 1.59 mm × 7.41 mm |
| 1x6 | 0.75" × 5.50" | 1.59 mm × 11.64 mm |
| 1x8 | 0.75" × 7.25" | 1.59 mm × 15.35 mm |
| 1x10 | 0.75" × 9.25" | 1.59 mm × 19.58 mm |
| 1x12 | 0.75" × 11.25" | 1.59 mm × 23.81 mm |
| 2x2 | 1.50" × 1.50" | 3.18 mm × 3.18 mm |
| 2x3 | 1.50" × 2.50" | 3.18 mm × 5.29 mm |
| 2x4 | 1.50" × 3.50" | 3.18 mm × 7.41 mm |
| 2x6 | 1.50" × 5.50" | 3.18 mm × 11.64 mm |
| 2x8 | 1.50" × 7.25" | 3.18 mm × 15.35 mm |
| 2x10 | 1.50" × 9.25" | 3.18 mm × 19.58 mm |
| 2x12 | 1.50" × 11.25" | 3.18 mm × 23.81 mm |

Nominal sizes are the rough-sawn names (a 2x4 is sold as 2" × 4"); at 1:12 those would be
2.12 mm per nominal inch, if you want round-number parts rather than true-to-life ones.

So a 1x6 shiplap board is about 1.6 × 11.6 mm in section, and a 2x4 stud 3.2 × 7.4 mm.

Printing notes: at 1:12 a 1x board is only four 0.4 mm lines thick. Keep at least
1.2 mm (three lines) wherever a texture cuts into a board.

## Wood-grain boards from Blender

Thin boards printed **on their edge** (the board's wide face standing vertical) put the
face you see on the walls of the print. That helps in two ways: the layer lines run along
the board like grain, and wall texture from the model prints cleanly. Orca's fuzzy skin
also works on walls, if a random texture is enough.

### 1. Set Blender up for millimetres

Scene Properties → Units: **Unit System** Metric, **Unit Scale** `0.001`, **Length**
Millimeters. Typed values are then millimetres and STL exports come out at the right size.

### 2. Make the textured face

1. Add → Mesh → **Grid**. In the redo panel set **X Subdivisions** to the board length ÷ 0.2
   and **Y Subdivisions** to the width ÷ 0.2 (a 250 × 11.6 mm board: 1250 × 58). That
   gives a vertex every 0.2 mm, which is about the detail a 0.4 mm nozzle can show.
2. Scale it to the board: N panel → Dimensions, X = length, Y = width (e.g. 250 × 11.64).
   Apply the scale (Ctrl-A → Scale).
3. Add a **Displace** modifier:
   - Texture → New. Either:
     - **Image** (most realistic): a greyscale wood *displacement* or *height* map with
       knots. ambientCG and Poly Haven publish free CC0 wood textures with displacement
       maps. Set the texture's **Coordinates** to UV.
     - **Procedural**: texture type **Wood**, *Band Noise*, noise basis Blender Original,
       Size 0.5-2, Turbulence 5-15. This gives grain but no knots. For knots, add a
       second Displace with a **Wood** *Ring Noise* texture, coordinates **Object** using
       an Empty placed at the knot, masked by a small vertex group around it.
   - **Strength** 0.15-0.3 (mm), **Midlevel** 0.5, Direction Normal.
4. Apply the modifier (Ctrl-A over it).

### 3. Give it thickness, flat on the back

1. Edit mode, select all, **E** then `Z -1.6` to extrude the board's thickness.
2. With the new (back) side still selected: **S Z 0** to flatten it, so the back is flat
   for gluing. Check the thinnest point is still at least 1.2 mm.
3. Object mode → File → Export → STL (selection only). Scale 1.

If you add a shiplap rabbet, model it before texturing, or subtract it with a Boolean
after.

## Printing the boards on edge

- Stand the board on its long edge (wide face vertical) and add an **outer brim**
  (3-5 mm). At 1.6 × 11.6 mm a board is about 7× taller than it is thick.
- Wood PLA presets: `Voron PLA Wood Oak` + `Voron 0.20mm PLA Wood` (see
  [`filaments/pla-wood-oak.md`](../filaments/pla-wood-oak.md)). A 1.6 mm board is only
  walls, so flow stays low and the 10 mm³/s cap doesn't matter.
- Orca's Arachne wall generator (default) handles the varying thickness a texture
  creates better than the Classic one.
- **Colour bands by temperature:** wood PLA darkens as it gets hotter, so varying the
  nozzle temperature gives grain-like bands along the board. It shows on walls, which is
  exactly the visible face here. Select the **`Voron PLA Wood Oak Grain`** filament
  preset: it is the wood preset plus `WOOD_GRAIN MIN=205 MAX=230 BAND=0.8 START=0.6`,
  which sets a random nozzle temperature in that range for every 0.8 mm of height, from
  0.6 mm up (`klipper/macros.cfg`; Orca's layer-change G-code calls `_WOOD_GRAIN_LAYER`
  with the layer height). Band height is in mm, so it looks the same at 0.1 or 0.2 mm
  layers. Keep it within about 205-230°C; below that, long runs jammed (see the filament
  notes).
- **Fine layers:** `Voron 0.10mm PLA Wood` is the wood process at 0.1 mm layers (first
  layer 0.3 mm), for finer detail on the visible face. `ShiplapVertical` (a 1.59 × 12 ×
  301 mm board laid diagonally, with triangular end fins) slices to about 22 min and 8 g
  at 0.1 mm with a 5 mm outer brim.
