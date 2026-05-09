# Wiring (ESP32 prototype)

Both boards are ESP32s programmed from the Arduino IDE with the RF24 library. Pin numbers are taken from the sketches in `esp32_prototype/`.

## nRF24L01+ to ESP32 (same on both boards)

| nRF24L01+ pin | ESP32 pin |
|---|---|
| VCC | 3.3 V |
| GND | GND |
| CE | GPIO 4 |
| CSN | GPIO 5 |
| SCK | GPIO 18 (default VSPI SCK) |
| MOSI | GPIO 23 (default VSPI MOSI) |
| MISO | GPIO 19 (default VSPI MISO) |
| IRQ | not connected |

Power the module from 3.3 V only. A 10 uF capacitor across VCC and GND near the module helps with the brown-outs nRF24L01+ boards often have.

## LEDs on the receiver (ESP32 2)

Each LED goes from its GPIO pin through a 220 ohm resistor to ground. There is no yellow LED: phases change directly from red to green.

| Approach | Red | Green |
|---|---|---|
| North | GPIO 13 | GPIO 12 |
| South | GPIO 14 | GPIO 27 |
| East | GPIO 26 | GPIO 25 |
| West | GPIO 33 | GPIO 32 |

## Radio settings (both sketches)

Pipe address `00001`, power level `RF24_PA_LOW`, 32-byte payloads, other settings at the RF24 defaults. The serial monitor runs at 115200 baud.
