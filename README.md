# OctoPrint-E3v3seprintjobdetails


<div align="center">

<a href=""><img src="https://i.imgur.com/HrwsfDM.jpeg" align="center" height="776" width="640"  ></a>

</div>

<br>




----------
<br><br><br>

# Background.
After Creality released the [Ender 3 V3 SE source code](https://github.com/CrealityOfficial/Ender-3V3-SE), many forks started to work on it and suddenly I was involved in this [thread on Creality's Forum](https://forum.creality.com/t/ender-3-v3-se-config-settings-to-roll-our-own-firmware-please/6333) were good folks from everywhere started a conversation about what could be good enhancements for the Firmware. So I thought will be a nice contribution for the community to merge the most common forks into One Repo and start from there new features for the firmware.

Also I wanted to go a little bit further, since I'm using [Octoprint](https://octoprint.org/), so I started to focusing on the integration of the Firmware with it, specially to make my LCD alive again.

## Special thanks to all the contributors:
* [@aschmitt1909](https://github.com/aschmitt1909/Ender-3V3-SE)
* [@queeup-Forks](https://github.com/queeup-Forks/Ender-3V3-SE)
* [@rtorchia](https://github.com/rtorchia/Ender-3V3-SE/commits/main/)
* [@eduard-sukharev](https://github.com/eduard-sukharev)
* And the folks from Creality Forum because they are making continuos tests and feature requests.

<br>

> [!CAUTION]
> 
> **Disclaimer**
>
> I'm not responsable of the damage or brick that may happen to your printer if you don't know what are you doing.
> I'm provided this fork tested on my own printer without warranties.** 


<br><br>

# Installation:
> [!TIP]
>
>First you need to flash creality firmware version 1.0.6. and the TFT files for the display.
>If your printer is already in that version you can do it directly.
>
>From: [Latest Release of Printer's Firmware without Gcode Preview](https://github.com/navaismo/Ender-3V3-SE) download the ZIP that fits your Octoprint configuration, recommended 150000 baud rate.
>
> or
>
>From: [Latest Release of Printer's Firmware with Gcode Preview](https://github.com/navaismo/Ender-3V3-SE-Gcode-Preview) download the ZIP that fits your Octoprint configuration, recommended 150000 baud rate.
>
>Unzip and:
>
> 1. Turn Off your printer.
> 2. Format you SD to FAT32 recommended to use MiniTool Partition or Gparted.
> 3. Rename the file to something random, i.E. “OC198B.bin” and copy to the SD.
> 4. Put the SD on your Printer SD-Card Reader(Not the LCD).
> 5. Turn On your printer.
> 6. Wait for the update to finish - it needs ~10-15 seconds.
> 7. Run a new Autolevel.
>
>For Octoprint:
>
> 1. Download the Latest Release plugin: navaismo/OctoPrint-E3v3seprintjobdetails
> 2. Install it manually using the Plugin Manager.
> 3. Follow the below section of Octoprint to configure it.
>

<br><br>


# Features for Octoprint.

## Configure the plugin:

### * Install Plugin's Dependencies:
To work correctly the plugin needs the following Plugins to be installed already:
 * [Print Time Genius](https://github.com/eyal0/OctoPrint-PrintTimeGenius)
 * [Dashboard](https://github.com/j7126/OctoPrint-Dashboard)

 Disable or Unistalled:
 * Disable Display Layer Progress

<br>

### * Set Correct Baud Rate.
Depending on the Firmware version that you've downloaded add the Baud Rate in the additional baud rates box.

_Note: If youe are using OCTO4A the only baud rate that will work is 115200 due to an Android or Octo4A limitation._

<div align="center">

<a href=""><img src="https://i.imgur.com/12DrB0x.png" align="center" height="400" width="640" ></a>

</div>


<br>

### * Add GCODE SCRIPTS.
To properly show the Ready connection string at Menu's header add the following in the
 * After Serial Connection to printer established
 * Before Serial Connection to printer is closed


<div align="center">

<a href=""><img src="https://i.imgur.com/8ovZgO3.png" align="center" height="400" width="840" ></a>

</div>

<br>

<div align="center">

<a href=""><img src="https://i.imgur.com/JsTXKEl.jpeg" align="center" height="576" width="440" ></a>

</div>

 <br>
 <br>

* For After Print Job Completes:
>
>```bash
>G1 X0 Y220
>```

 <br>



* For After Print Job is Cancelled:

_In this section is **important to add the last M117 command** it will help to clear some variables before going to Main Menu_

>
>```bash
>; relative moving
>G91
>; move head 10mm up
>G1 Z10 F800
>; absolute moving
>G90
>
>; move print head out of the way
>G1 X0 Y220 F3000
>
>; disable motors
>M84
>
>; disable all heaters
>{% snippet 'disable_hotends' %}
>M104 S0 ; Set Hotend to 0
>
>{% snippet 'disable_bed' %}
>M140 S0 ; Set Bed to 0
>
>;disable fan
>M106 S0
>
>; send message to printer.
>M117 Print was cancelled
>```


<br>

* For After Print Job is Paused:

>
>```bash
>{% if pause_position.x is not none %}
>; relative XYZE
>G91
>M83
>
>; retract filament of 0.8 mm up, move Z slightly upwards and 
>G1 Z+5 E-0.8 F4500
>
>; absolute XYZE
>M82
>G90
>
>; move to a safe rest position, adjust as necessary
>G1 X0 Y220
>{% endif %}
>
>```
>

<br>

* For After Print Job is Resumed
>
>```bash
>{% if pause_position.x is not none %}
>; relative extruder
>M83
>
>; prime nozzle
>G1 E-0.8 F4500
>G1 E0.8 F4500
>G1 E0.8 F4500
>
>; absolute E
>M82
>
>; absolute XYZ
>G90
>
>; reset E
>G92 E{{ pause_position.e }}
>
>; WARNING!!! - use M83 or M82(extruder absolute mode) according what your slicer generates
>M83 ; extruder relative mode
>
>; move back to pause position XYZ
>G1 X{{ pause_position.x }} Y{{ pause_position.y }} Z{{ pause_position.z }} F4500
>
>; reset to feed rate before pause if available
>{% if pause_position.f is not none %}G1 F{{ pause_position.f }}{% endif %}
>{% endif %}
>```

Of course you can change it to your desired behaviour above are just wroking eamples in my setup.

<br>

### * Configure O9000 commands:
Enable the option to Turn On the Job details on the LCD. Otherwise left M117 and any other plugin will send information to it. 

_M177 has a basic implementation and I'm not planning on improve M117 messages_ 


<div align="center">

<a href=""><img src="https://i.imgur.com/M4K7023.png" align="center"  ></a>

</div>

<br>

### * Configure The GCODE Preview transmission.
If you installed the firmware from the [Repo that Enable the Gcode Preview Using Octoprint](), enble the slicer so the plugin can send it to the LCD.

> [!IMPORTANT]
>
> - [x] The supported size for the GCODE Preview is a size of 96x96.
> - [x] Supported Slicers are Cura and Orca.
> - [x] In Orca use the following **96x96/JPG**.
> - [x] In Cura default **96x96** setting is enough.
> - [x] In your slicer use a filament color other than black or the Image will be barely visible.
> - [x] **Previews will only work after enable those settings and for the new Files that you upload, any old file will not work**
> - [x] **Transmitting and Rendering the preview will take up to 2 minutes**.
>

<br>

<div align="center">

<a href=""><img src="https://i.imgur.com/f5zKGgK.png" align="center"  ></a>

</div>

<br>



### * Select the Based Progress Type for the Percentage  .
* **Time Pogress**: Will render the circle percent progress based on the estimation of the Time Printer or PTG plugin. Is a known issue that Printer or PTG arent accurate at all so this is not the best option.

* **Layer Progress**: Will render the circle progress based on the calculation of the percent bewteen the Curren Layer and the Total Layers.

* **M73 Progress**: Will render the circle progress based on the information that the Gcode file send trhough M73 command. This is the recommended one.

 _You need to enable your slicer to send this information is not by default and must follow the standar command like: **M73 P10 R60**_


<br>

<div align="center">

<a href=""><img src="https://i.imgur.com/q7oevYd.png" align="center"  ></a>

</div>

<br>

## After configuring all the above you will be able to see the New Layout of the screen:


### Octoprint GUI while transmitting the Thumbnail.
  
<div align="center">

<a href=""><img src="https://i.imgur.com/B5pbWeH.png" align="center" height="476" width="940" ></a>

</div>

<br>


### Receiving Thumbnail.

<div align="center">

<a href=""><img src="https://i.imgur.com/OG4TiIl.jpeg" align="center" height="576" width="440" ></a>

</div>

<br>

### Rendering Thumbnail.

<div align="center">

<a href=""><img src="https://i.imgur.com/XQXIhTd.jpeg" align="center" height="576" width="440"  ></a>

</div>

<br>

### Loaded Thumbnail.

<div align="center">

<a href=""><img src="https://i.imgur.com/HrwsfDM.jpeg" align="center" height="576" width="440"  ></a>

</div>

<br>




### New Tune Layout.

<br>

<div align="center">

<a href=""><img src="https://i.imgur.com/Q5CJWSB.jpeg" align="center" height="576" width="440" ></a>

</div>

<br>


<div align="center">

<a href=""><img src="https://i.imgur.com/J2r8VFr.jpeg" align="center" height="576" width="440" ></a>

</div>

<br>


#### If you disable the Thumbnail in the plugin's configuration or using the [Firmware from this REPO](https://github.com/navaismo/Ender-3V3-SE), the default Creality Image will be rendered:

<div align="center">

<a href=""><img src="https://i.imgur.com/HDJQjH8_d.webp?maxwidth=1520&fidelity=grand" align="center" height="576" width="440" ></a>

</div>

<br>


# FAQS
Most of the questions has been answered in the Issue section of the Repo but here are the most common:

<p style="color: orange;"> <b>1.</b> Why I don't see the updates in real time on the LCD? </p>
TL;DR: Because rendering the LCD will affect your print quality.

Take a look on the [Issue #7](https://github.com/navaismo/OctoPrint-E3v3seprintjobdetails/issues/7) to get the full backgorund of why the Real Time response was removed.

<br>
<p style="color: orange;"> <b>2.</b> Do I need Octoprint to work with this? </p>
No, the common feeatures works for both, you just will see the stock LCD Layout. The new layout with Gcode Preview, Layer count etc. Will be render only using Octoprint.


<br>
<p style="color: orange;"> <b>3.</b> Why you don't Increase the connection Baud Rate? </p>
TL;DR: Because printer cannot handle communication above 150000.

Take a look on the [Issue #5](https://github.com/navaismo/Ender-3V3-SE/issues/5) to get the full backgorund.

<br>
<p style="color: orange;"> <b>4.</b> Got a leveling error? </p>
This error is only present when using Octoprint and is expected since you flashed a new Grid with no values. So after flashing the new firmware start a new fresh level procedure and then connect Octoprint again.


<br>
<p style="color: orange;"> <b>5.</b> Why the Render of GCcode Preview takes so much time? & Why there is no Gcode Preview without Octoprint?</p>
TL;DR: Because LCD is closed and we haven't found it it has a SRAM to store images. An thats why is only supported by Octoprint and not stand alone. To process the image and send it.

Take a look on [this Discussion](https://github.com/navaismo/Ender-3V3-SE/discussions/28) to see the efforts. Eduard and I spent a lot of time trying to find an Address with no luck.

<br>
<p style="color: orange;"> <b>6.</b> Sometimes when Thumbnail Enabled the printer pauses and has weird movement behaviour before the print starts?</p>
This is because the plugin programaticaly pauses the print job until the Thumbnail is rendered, to avoid affect the print quality.

It is recommended to Load the file first and then click on Print.
If is a direct print, is recommended to preheat the filament so the transmission will start faster, else it will wait till nozzle reach the temperature.

<br>
<p style="color: orange;"> <b>7.</b> Sometimes when the thumb is disabled an loaded the Job in LCD I see the Default image dissapearing slowly while the other is rendering. Can you just clean the LCD?</p>
This is a personal decision, I like a lot to see how the Creality Man dissapear slowly, it brings me peace.

<br>
<p style="color: orange;"> <b>8.</b> Sometimes in the Tune Menu appears the Nozzle and Bed Icons, Why?</p>
This is beacuse the encoder/Knob is moved too fast and enter in an unknow state that by default try to render the lower info area. If you move it slowly this will no appear.
