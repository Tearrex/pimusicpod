# pimusicpod
Embedded Python software for streaming MP3 files over bluetooth with a Raspberry Pi!

![piplayer](https://github.com/Tearrex/pimusicpod/assets/26557969/22f6e4cd-2fc1-4a0f-a9c2-d510cf2aa454)

Main menu

<img src="https://github.com/Tearrex/pimusicpod/assets/26557969/be76cc8e-e618-45a4-9580-a32447fc4ad8" width="500" />


## Hardware Requirements
- Raspberry Pi Zero W
- waveshare OLED Display HAT [Amazon Link](https://www.amazon.com/1-3inch-OLED-Display-HAT-Communicating/dp/B07VCYTPRK/)
- Storage device for MP3 folders

And a bluetooth speaker...
## Software Requirements
- Raspberry Pi OS Lite
- Python 3 + dependencies
## Setup
Disclaimer: In order to attach the display HAT, you will need to have GPIO pins soldered to your board.

1. Clone to the home directory of your Pi

      $ ```git clone https://github.com/Tearrex/pimusicpod.git```

2. CD into the project folder and install the necessary Python packages

      $ ```pip3 install -r requirements.txt```

3. Edit the `modules/music.py` file and change the `MUSIC_DIR` value to match the parent directory of your music folders
4. Execute the main script

      $ ```python3 main.py```

The script will recursively scan the subfolders of your music directory and register them as playlists. You can switch between them by navigating the on-screen menu

> Music > Playlists

You can also rearrange the playback order of the current playlist through the queue submenu (shuffled by default)

> Music > Queue

Before starting the party, you must pair your Raspberry Pi to a bluetooth speaker. Make sure your speaker is in pairing mode and enable scanning from the on-screen menu

> Bluetooth > Scan

Give it a few seconds, then check the list of pairable devices from

> Bluetooth > Connect Device

If your device fails to appear, you may have to jump in and out of the device list menu until the Pi discovers the correct bluetooth MAC address.

Alternatively, you can try a one-off fixup from the System submenu

> System > BT Hack

This is a small CLI script that restarts the bluetooth and PulseAudio services which may be causing issues.

If all else fails, you can reboot the Raspberry Pi with the on-screen option and try pairing again

> System > Reboot
