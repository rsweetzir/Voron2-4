# USB-CAN adapter: candleLight firmware

The USB-to-CAN adapter on the printer Pi is a "ConvertDevice xCAN" style CANable clone with an
**STM32F072C8T6** (64 KiB flash, 16 KiB RAM). It shipped with PCAN-USB clone firmware
(`0c72:000c` "XCAN-USB", Linux `peak_usb` driver); it now runs candleLight
(`1d50:606f`, Linux `gs_usb` driver), the firmware Klipper recommends for CAN adapters.

| File | Contents |
|---|---|
| `CONVERTDEVICE_xCAN_fw.bin` | Flashed 2026-10-06. sha256 `a5d43511e6da2bec29e50c6a6171e75dc800ac6b592a1fcbc36e707a59e5cce8` |
| `25-can.network` | `/etc/systemd/network/25-can.network` on the printer Pi: brings `can0` up at 1 Mbit/s |

## Build

Built on the printer Pi (Debian 12 bookworm, arm64) with Debian's `gcc-arm-none-eabi`
12.2.1 (newlib) and cmake 3.25, from
[candle-usb/candleLight_fw](https://github.com/candle-usb/candleLight_fw) commit
`85e5b3352db7f051aa879eeb71555dfce664c44c` (2026-09-17).

```
sudo apt install gcc-arm-none-eabi cmake dfu-util git
git clone https://github.com/candle-usb/candleLight_fw.git
cd candleLight_fw
git checkout 85e5b3352db7f051aa879eeb71555dfce664c44c   # optional: the exact build above
mkdir build && cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=../cmake/arm-none-eabi-gcc.cmake
make CONVERTDEVICE_xCAN_fw
```

Output: `build/CONVERTDEVICE_xCAN_fw.bin` (about 23 KB). The `CONVERTDEVICE_xCAN` target is an
STM32F072 board with LEDs on PA0 (RX) and PA1 (TX), active low; it fits the F072**C8**'s
64 KiB even though candleLight links it for the 128 KiB F072xB.

## Flash

1. Unplug the adapter, set the BOOT jumper (or hold BOOT), plug it back in.
2. `lsusb` shows `0483:df11 STMicroelectronics ... DFU`.
3. Flash:
   ```
   sudo dfu-util -a 0 -s 0x08000000:leave -D CONVERTDEVICE_xCAN_fw.bin
   ```
4. Remove the jumper and replug. `lsusb` shows `1d50:606f ... Geschwister Schneider CAN adapter`.

## Network

Install the network file and let systemd-networkd bring `can0` up on boot:

```
sudo cp 25-can.network /etc/systemd/network/
sudo systemctl enable --now systemd-networkd
ip -details link show can0      # bitrate 1000000, state UP, gs_usb
```

Klipper's recommended `txqueuelen` of 128 is already the `gs_usb` default.
Check for Klipper nodes on the bus with:

```
~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0
```

The bus must be terminated with 120 Ω at both ends: the adapter and the board at the far
end of the umbilical (enable only one toolhead-side terminator).
