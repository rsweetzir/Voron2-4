# Dollhouse (1:12 scale)

Parts, notes and print settings for a 1:12 scale dollhouse printed on this Voron. 1:12 is
the common dollhouse scale: one real foot is one scale inch, so real sizes divide by 12
(1 real inch = 2.117 mm).

## 1:12 scale dimensional lumber

North American lumber is sold by a **nominal** size (the rough-sawn size) and is planed
to a smaller **actual** size. Use the actual column to match real framing and trim, the
nominal column for round numbers that "read" right.

**Widths**

| Nominal width | Examples | Actual real-world width | 1:12 width (actual) | 1:12 width (nominal) |
|---|---|---|---|---|
| 2" | 1x2, 2x2 | 1.5 in (38 mm) | 3.18 mm | 4.23 mm |
| 3" | 1x3, 2x3 | 2.5 in (64 mm) | 5.29 mm | 6.35 mm |
| 4" | 1x4, 2x4 | 3.5 in (89 mm) | 7.41 mm | 8.47 mm |
| 6" | 1x6, 2x6 | 5.5 in (140 mm) | 11.64 mm | 12.70 mm |
| 8" | 1x8, 2x8 | 7.25 in (184 mm) | 15.35 mm | 16.93 mm |
| 10" | 1x10, 2x10 | 9.25 in (235 mm) | 19.58 mm | 21.17 mm |
| 12" | 1x12, 2x12 | 11.25 in (286 mm) | 23.81 mm | 25.40 mm |

**Thicknesses**

| Nominal thickness | Actual real-world thickness | 1:12 thickness (actual) | 1:12 thickness (nominal) |
|---|---|---|---|
| 1x | 0.75 in (19 mm) | 1.59 mm | 2.12 mm |
| 2x | 1.5 in (38 mm) | 3.18 mm | 4.23 mm |

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
  nozzle temperature every few layers gives grain-like bands along the board (it only
  shows on walls, which is exactly the visible face here). Keep it within about
  205-230°C; below that, long runs jammed (see the filament notes).
