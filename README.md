# LAGGY virtual assistant for Klipper.
Python project to reuse the LCD-knob-screen of the Anycubic Kobra 2 neo and the Anycubic Kobra Go. Unlike the Klipper-Screen compatibility project below, it utilizes the knob of the screen giving it handy quick control features. 

Able to pause prints using a double click, change print speed, show basic information and a bit more.

Utilizing the Anycubic Kobra neo 2 / Kobra go SLI screen using these drivers:

https://github.com/jokubasver/Anycubic-Kobra-Go-Neo-LCD-Driver

The pinout in this project is given like this:

![image](https://github.com/user-attachments/assets/c71006e6-febe-4f51-8ced-cfdab8ce61fc)

The connection diagram of the drivers alone look like this:

```
5V -> 5V
GND -> GND
SCK -> GPIO 11 (SPI SCLK)
MOSI -> GPIO 10 (SPI MOSI)
CS -> GPIO 8 (SPI CE0)
RESET -> GPIO 25
DC (Marked as MISO on the mainboard) -> GPIO 24
```
In order to get the knob to work, we add this:
```
Encoder Switch -> GPIO 19
Encoder Out A -> GPIO 13
Encoder Out B -> GPIO 16
```

To clarify:

![ENCODER SWITCH](https://github.com/user-attachments/assets/19e1f957-c963-4801-a5e5-a8da31371905)

Do not use fbdev drivers but rather keep fbturbo. To ensure the driver selection type ```sudo nano /usr/share/X11/xorg.conf.d/99-fbturbo.conf```.

It should look like this:
```
Section "Device"
        Identifier      "Allwinner A10/A13 FBDEV"
        Driver          "fbturbo"
        Option          "fbdev" "/dev/fb0"

        Option          "SwapbuffersWait" "true"
EndSection
```
If not, change ```Driver          "fbdev"``` to ```Driver          "fbturbo"```, press CTRL+X, then Y, and reboot.

To download the Python scripts and assets use:
```git clone https://github.com/PowerCmptr/Laggy_Klipper```

Edit /etc/rc.local with ```sudo nano /etc/rc.local``` and add the python script under the main script (```sudo /path/to/Anycubic-Kobra-Go-Neo-LCD-Driver/build/fbcp-ili9341 &```). 
```
cd /path/to/Laggy_Klipper/
python3 main.py &
```
Now press CTRL+X. then Y and ENTER. Now reboot ```sudo reboot now``` and after a reboot LAGGY should appear on your screen and you're done!

![IMG_2512](https://github.com/user-attachments/assets/bfc56d29-5f18-4a56-b0da-eed078de4e18)
