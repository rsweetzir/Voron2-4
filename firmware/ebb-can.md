# EBB: switching from USB to CAN

The BTT EBBCan (STM32G0B1, 8 MHz crystal) currently runs Klipper over USB (`ebb.config`).
`ebb-can.config` is the same build with the interface changed to **CAN on PB0/PB1 at
1 Mbit/s**, matching `can0` on the printer Pi (see `candlelight/`). Neither build has a
bootloader: the firmware sits at 0x08000000 and is flashed over USB with the STM32 ROM DFU.

Do this only once the CAN umbilical is wired: after flashing, the EBB no longer appears on
USB, and Klipper will not start until `ebb_extruder.cfg` uses its CAN UUID.

## Build

On the printer Pi, from the Klipper version the host runs (firmware and host must match):

```
cd ~/klipper
cp ~/voron-klipper-config/firmware/ebb-can.config ~/fw/ebb-can.config   # if not already there
make KCONFIG_CONFIG=$HOME/fw/ebb-can.config olddefconfig
make KCONFIG_CONFIG=$HOME/fw/ebb-can.config OUT=$HOME/fw/out_ebb_can/ -j4
```

Output: `~/fw/out_ebb_can/klipper.bin`. Check the config kept the CAN choice
(`make menuconfig` silently falls back to USB if the interface lines are wrong):

```
grep -E '^CONFIG_(CANSERIAL|STM32_CANBUS_PB0_PB1|CANBUS_FREQUENCY)=' ~/fw/ebb-can.config
# CONFIG_STM32_CANBUS_PB0_PB1=y, CONFIG_CANSERIAL=y, CONFIG_CANBUS_FREQUENCY=1000000
```

Built 2026-10-06 from Klipper v0.13.0-622-gdb78babf9, not flashed yet.

## Flash

1. Stop Klipper so it doesn't fight over the board: `sudo systemctl stop klipper`.
2. Connect the EBB to the Pi by USB (it already is while running the USB build).
3. Enter DFU: hold **BOOT**, press and release **RESET**, release BOOT.
   `lsusb` shows `0483:df11 STMicroelectronics ... DFU`.
4. Flash (same command used for the USB build, different file):
   ```
   sudo dfu-util -d 0483:df11 -R -a 0 -s 0x8000000:leave -D ~/fw/out_ebb_can/klipper.bin
   ```
5. Unplug the EBB's USB cable; power and data now come through the umbilical.

## Wire and terminate

- CAN-H / CAN-L from the adapter to the EBB (and the Eddy Duo, on the same pair).
- 120 Ω termination at both ends only: the adapter, and the board at the far end of
  the umbilical (EBB 120R jumper on, *or* the Eddy's, not both).
- `ip -details -s link show can0` should stay `ERROR-ACTIVE` with no bus errors.

## Find the UUID and update Klipper

```
~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0
# Found canbus_uuid=xxxxxxxxxxxx, Application: Klipper
```

In `ebb_extruder.cfg`, replace the `serial:` line in `[mcu EBBCan]` with:

```
canbus_uuid: xxxxxxxxxxxx
```

(An older UUID, `0e0d81e4210c`, is commented in that file from an earlier CAN setup;
use what `canbus_query.py` reports now.) Then `sudo systemctl start klipper` and check
Mainsail for `EBBCan` connecting.

## Roll back to USB

Enter DFU as above and flash the USB build, then restore the `serial:` line:

```
sudo dfu-util -d 0483:df11 -R -a 0 -s 0x8000000:leave -D ~/fw/out_ebb/klipper.bin
```

## Later updates

Without a bootloader, every firmware update needs the USB cable and the BOOT/RESET
buttons. Installing [Katapult](https://github.com/Arksine/katapult) (8 KiB, CAN) would
allow updates over CAN; the Klipper build would then need
`CONFIG_FLASH_APPLICATION_ADDRESS=0x8002000`.
