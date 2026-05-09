# Third-party assets

## Hardware layout figure (`assets/images/hardware_layout.png`)

The figure is assembled by `hardware/visualization/build_hardware_figure.py` from the unmodified part drawings below. The script positions the parts and draws the schematic wires, labels and the radio link. No part drawing was created or generated for this project.

| Asset | File in `hardware/visualization/parts/` | Source | License |
|---|---|---|---|
| ESP32 board (SparkFun ESP32 Thing, breadboard view; drawn as a representative ESP32) | `sparkfun_esp32_thing_breadboard.svg` | SparkFun Fritzing parts, https://github.com/sparkfun/Fritzing_Parts/blob/main/products/13907_sfe_esp32_thing.fzpz (breadboard SVG extracted from the part file) | CC-BY-SA 4.0 (`parts/SPARKFUN_LICENSE.md`) |
| nRF24L01 module | `NRF24L01_fix_breadboard.svg` | Fritzing parts library, https://github.com/fritzing/fritzing-parts/blob/develop/svg/core/breadboard/NRF24L01_fix_breadboard.svg | CC-BY-SA 3.0 |
| Full-size breadboard | `breadboard2.svg` | Fritzing parts library, https://github.com/fritzing/fritzing-parts/blob/develop/svg/core/breadboard/breadboard2.svg | CC-BY-SA 3.0 |
| 5 mm LEDs (red, green) | `LED-5mm-red.svg`, `LED-5mm-green.svg` | Fritzing parts library, https://github.com/fritzing/fritzing-parts/tree/develop/svg/obsolete/breadboard | CC-BY-SA 3.0 |
| 220 ohm resistor | `resistor_220.svg` | Fritzing parts library, https://github.com/fritzing/fritzing-parts/blob/develop/svg/core/breadboard/resistor_220.svg | CC-BY-SA 3.0 |
| Camera icon | `tabler-camera.svg` | Tabler Icons, https://github.com/tabler/tabler-icons/blob/main/icons/outline/camera.svg | MIT |

Fritzing's license (`parts/FRITZING_LICENSE.txt`): "All graphics and documentation of Fritzing are licensed under Creative Commons Attribution-ShareAlike 3.0 Unported... you may publish circuits and diagrams that you create with Fritzing and that use these graphics -- as long as you credit us, and publish your works under the same license." Credit: **part graphics from the Fritzing project (fritzing.org)**. SparkFun's parts are licensed CC-BY-SA 4.0; credit: **ESP32 Thing part graphic by SparkFun Electronics**. Because it uses these share-alike graphics, the hardware layout figure is shared under **CC-BY-SA 4.0** (compatible with both).

The Tabler Icons MIT license is in `parts/TABLER_ICONS_LICENSE.txt`.

## Detector training data

The YOLOv8 models in `vision/weights/` were trained on the BDD100K dataset (https://www.vis.xyz/bdd100k/), starting from the Ultralytics YOLOv8n pretrained weights (AGPL-3.0). BDD100K images are not redistributed in this repository. Its license allows research use; see the BDD100K terms before any other use of the weights.
