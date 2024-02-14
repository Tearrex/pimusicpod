from __future__ import annotations
from luma.core.interface.serial import i2c, spi
from luma.core.render import canvas
from luma.oled.device import sh1106
import RPi.GPIO as GPIO
from PIL import ImageFont
import os
import sys
import time
import json
from subprocess import check_output, Popen, CalledProcessError, DEVNULL, PIPE

from modules.music import MusicPlayer, InputManager
from modules.bluetooth import BTHack
from modules.elements import Text, Button, Toggle, Feed, Menu, Prompt, Slider


def get_settings():
    defaults = {
        "brightness": 50,
        "sleep-delay": 10,
        "reshuffle": 1
    }
    if not os.path.exists("settings.json"):
        obj = json.dumps(defaults, indent=4)
        with open("settings.json", 'w') as out:
            out.write(obj)
        print("Created new settings .json file")
    with open("settings.json", 'r') as sett:
        settings = json.load(sett)
    return settings


font = ImageFont.load_default()

padding = -2
top = padding
line_pad = [top, top+8, top+16, top+25, top+34, top+43, top+52]

# GPIO define and OLED configuration
RST_PIN = 25
CS_PIN = 8
DC_PIN = 24
KEY_UP_PIN = 6      # stick up
KEY_DOWN_PIN = 19   # stick down
KEY_LEFT_PIN = 5    # stick left // go back
KEY_RIGHT_PIN = 26  # stick right // go in // validate
KEY_PRESS_PIN = 13  # stick center button
KEY1_PIN = 21       # key 1 // up
KEY2_PIN = 20  # key 2 // cancel/goback
KEY3_PIN = 16       # key 3 // down

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(KEY_UP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_DOWN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_PRESS_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY3_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


class BTListElement():
    def __init__(self, output: str):
        params = output.split(' ', 2)
        self.name = params[2]
        self.mac = params[1]

    def __str__(self): return self.name


class ScreenMaster():
    # screen controller
    def __init__(self, settings):
        self.toggle = True
        self.wifi = True
        self.scanner = None
        # music controller
        self.music = MusicPlayer()
        # listen to button presses on bluetooth speaker
        self.manager = InputManager(self.music)
        self.settings = settings
        print(self.settings)
        self.brightness = self.settings["brightness"]

        self.sleepTime = 0
        self.sleepTimer = self.settings["sleep-delay"]
        self.reshuffle = (self.settings["reshuffle"] == 1)

        serial = spi(device=0, port=0, bus_speed_hz=8000000,
                     transfer_size=4096, gpio_DC=DC_PIN, gpio_RST=RST_PIN)
        self.device = sh1106(serial, rotate=2)  # sh1106
        self.device.show()

        self.bthack = BTHack()  # hacky tool for fixing pulseaudio issues

        self.curDevice = None

    def toggle_screen(self) -> None:
        self.toggle = not self.toggle
        if not self.toggle:
            self.device.hide()
        else:
            self.device.show()
        time.sleep(1)

    def DisplayText(self, lines, selection=None, topLeft=()) -> None:
        # simple routine to display 7 lines of text
        with canvas(self.device) as draw:
            for i, l in enumerate(lines):
                draw.text((0, line_pad[i]), l,  font=font, fill=255)
            if selection != None:
                draw.text((0, line_pad[selection]), '>',  font=font, fill=255)
            if topLeft:
                draw.text((topLeft[0], line_pad[0]),
                          topLeft[1],  font=font, fill=255)

    def confirm_prompt(self, prompt="Are you sure?") -> bool:
        print("Asking for confirmation")
        confOpts = [prompt, "  Yes", "  No"]
        confSelect = 2
        self.DisplayText(confOpts, confSelect)
        time.sleep(0.5)
        while GPIO.input(KEY_LEFT_PIN):
            if not GPIO.input(KEY_UP_PIN):  # button is released
                if confSelect == 1:
                    confSelect = (len(confOpts) - 1)
                else:
                    confSelect -= 1
                self.DisplayText(confOpts, confSelect)
                time.sleep(0.5)

            if not GPIO.input(KEY_DOWN_PIN):  # button is released
                if confSelect >= (len(confOpts) - 1):
                    confSelect = 1
                else:
                    confSelect += 1
                self.DisplayText(confOpts, confSelect)
                time.sleep(0.5)

            if not GPIO.input(KEY_PRESS_PIN) or not GPIO.input(KEY_RIGHT_PIN):
                if confSelect == 1:
                    return True
                else:
                    return False
        return False

    def list_devices(self, paired=False) -> list[BTListElement]:
        """Returns a list of bluetooth devices, each with keys\n
        `name` The name of the device\n
        `mac` The MAC address of the device"""
        if paired:
            output = check_output(
                "bluetoothctl paired-devices".split(' ')).decode().split('\n')
        else:
            output = check_output(
                "bluetoothctl devices".split(' ')).decode().split('\n')
        # print(output)
        devices = []
        for d in output:
            if d == '' or len(d.split('-')) >= 5 or 'RSSI' in d or 'harp' in d.lower() or 'ble' in d.lower():
                continue
            devices.append(BTListElement(d))
        return devices

    def run_bt_script(self, prompt="Running script...") -> None:
        with canvas(self.device) as draw:
            draw.text((0, line_pad[0]), prompt,  font=font, fill=255)
            draw.rectangle(((14, 28), (114, 36)), outline=255, fill=0)
        time.sleep(2)
        progress = 0
        if self.music.player:
            try:
                self.music.restart = True  # stop this song, but don't remove from queue
                self.music.player.stop()
            except Exception as e:
                print(e)
            finally:
                self.music.player = None
        # function yields integers for each step, accumulated to progress value
        for s in self.bthack.initiate(True, True):
            progress = max(min(progress + s, 100), 0)  # clamp to 100%
            with canvas(self.device) as draw:
                draw.text((0, line_pad[0]), prompt + "{}%".format(progress),  font=font, fill=255)
                draw.rectangle(((14, 28), (114, 36)),
                               outline=255, fill=0)  # outer rect
                draw.rectangle(
                    ((14, 28), (round(114 * (progress/100)), 36)), outline=255, fill=255)  # inner rect
        if progress == 100:
            with canvas(self.device) as draw:
                draw.text((0, line_pad[0]),
                          "Script succesful!",  font=font, fill=255)
                draw.rectangle(((14, 28), (114, 36)),
                               outline=255, fill=255)  # full bar
        else:
            self.DisplayText([prompt, "Script failed!"])  # shouldn't happen
        time.sleep(2)

    def save_settings(self) -> None:
        with open("settings.json", 'w') as out:
            out.write(json.dumps(self.settings, indent=4))

    def save_reshuffle(self, value) -> None:
        if self.reshuffle != value:
            # save changes
            self.reshuffle = value
            self.settings['reshuffle'] = self.reshuffle  # save object in file
            self.save_settings()

    def save_brightness(self) -> None:
        if self.settings['brightness'] != self.brightness:
            self.settings['brightness'] = self.brightness
            self.save_settings()

    def toggle_bt_scan(self, toggle) -> None:
        if toggle:
            if self.scanner:
                return
            self.scanner = Popen(
                ['bluetoothctl', 'scan', 'on'], stderr=PIPE, close_fds=True)
            print("Scanning for bluetooth devices...")
        else:
            if self.scanner:
                try:
                    self.scanner.terminate()
                except Exception:
                    pass
                finally:
                    try:
                        check_output("bluetoothctl scan off".split(
                            ' '), stderr=DEVNULL)
                    except Exception:
                        pass
                    self.scanner = None
                print("Stopped scanning for bluetooth devices...")

    def is_device_connected(self) -> bool:
        return self.curDevice != None

    def current_bt_device(self) -> str:
        """Simply returns the currently connected device object"""
        if self.curDevice:
            return self.curDevice['name']
        else:
            return "None"

    # too lazy to allow empty parameter fields
    def disconnect_bt_device(self, dummy) -> bool:
        if self.curDevice:
            yield (self.curDevice['name'], "Disconnecting...")
            time.sleep(1)
            try:
                check_output(
                    f"bluetoothctl disconnect {self.curDevice['mac']}".split(' '))
            except Exception as e:
                yield True
                yield (self.curDevice['name'], "Error disconnecting!")
                time.sleep(2)
                return True
            else:
                self.curDevice = None  # reset current device reference
                return True
        else:
            yield "No device connected!"
            time.sleep(2)
            return True

    def menu_manage_device(self, device: dict) -> bool:
        """
        Handles the operations involved with removing or
        pairing to the bluetooth device that was selected\n
        Device should be declared as a dictionary with keys `name`, `mac`, and `paired`
        """
        print(
            f"Selected '{device['name']}' with MAC: {device['mac']}")
        # yes, i know i should be using the bluetooth module...
        info = check_output(f"bluetoothctl info {device['mac']}".split(
            ' ')).decode().replace('\t', '').split('\n')
        if device['paired']:
            print("remove")
            yield (device['name'], "Removing...")
            time.sleep(1)
            try:
                check_output(f"bluetoothctl remove {device['mac']}".split(' '))
            except Exception as e:
                print(e)
                yield True
                yield (device['name'], "Failed to remove!")
                time.sleep(2)
            else:
                if self.curDevice and self.curDevice['mac'] == device['mac']:
                    self.curDevice = None
            return True
        else:
            print("connect")
            pairError = False
            if not 'Paired: yes' in info:
                yield (device['name'], "Trying to pair...")
                time.sleep(2)
                for i in range(3):
                    try:
                        check_output(
                            f"bluetoothctl pair {device['mac']}".split(' '))
                    except Exception as e:
                        time.sleep(4)
                    else:
                        break
                    pairError = True
                if pairError:
                    yield True  # clear text on screen
                    yield device['name']  # draw new title
                    yield "Failed to pair!"  # draw new message
                    time.sleep(3)  # give user time to read
            if not pairError:
                connectError = False
                if not 'Connected: yes' in info:
                    yield True  # yielding True clears the screen
                    yield (device['name'], "Paired", "Trying to connect...")
                    time.sleep(3)
                    try:
                        check_output(
                            f"bluetoothctl connect {device['mac']}".split(' '))
                    except Exception as e:
                        print(e)
                        try:
                            check_output(["pulseaudio", "-k"])
                        except CalledProcessError:
                            pass
                        else:
                            time.sleep(2)
                        check_output(["pulseaudio", "--start"])
                        time.sleep(2)
                        try:
                            check_output(
                                f"bluetoothctl connect {device['mac']}".split(' '))
                        except Exception:
                            yield True
                            yield (device['name'], "Paired", "Failed to connect!")
                            connectError = True
                            time.sleep(3)
                if not connectError:
                    if self.scanner:
                        try:
                            self.scanner.terminate()
                        except Exception:
                            pass
                        finally:
                            self.scanner = None
                    self.curDevice = device
                    self.manager.mac = device['mac']
                    yield True
                    yield (device['name'], "Connected!")
                    time.sleep(3)
                    if not 'Trusted: yes' in info:
                        trust = self.confirm_prompt(f"Trust {device['name']}?")
                        if trust:
                            check_output(
                                f"bluetoothctl trust {device['mac']}".split(' '))
                return True

    def menu_device_list(self, paired=False) -> list[Feed]:
        """
        Returns a list of discovered devices (if any) as `Feed` objects
        """
        devList = self.list_devices(paired)
        if len(devList) > 0:
            devices = []
            for d in devList:
                # should be its own Element type
                # barebones Button class for now
                args = {
                    "paired": paired,
                    "name": d.name,
                    "mac": d.mac
                }
                device = Feed(self, f" {d.name}",
                              self.menu_manage_device, args)
                devices.append(device)
            return devices
        else:
            return [Text("  No devices found")]

    def menu_remove_devices(
        self): return self.menu_device_list(True)

    def set_playlist(self, playlistName):
        # not the most ideal method but it works for now
        for i, p in enumerate(self.music.playlists):
            if (p.name == playlistName):
                self.music.definitive_switch(i)

    def get_playlists(self) -> list[Button]:
        return [Button(f" {playlist.name}", self.set_playlist, playlist.name) for playlist in self.music.playlists]

    def has_event0(self) -> bool:
        """
        Checks if event0 is found as an input device.
        """
        return str(os.path.exists('/dev/input/event0'))

    # playback helper functions
    def make_song_next(self, songIndex=0):
        if (songIndex == 0):
            return
        newIndex = 0
        if (self.music.player):
            newIndex = 1  # dont remove spot of currently playing song
        self.music.playlists[self.music.playlistIndex].tracks.insert(
            newIndex, self.music.playlists[self.music.playlistIndex].tracks.pop(songIndex))

    def make_song_last(self, songIndex):
        # bring song to the bottom of the queue
        if (songIndex == 0 and self.music.now == self.music.playlists[self.music.playlistIndex].tracks[songIndex]):
            return
        self.music.playlists[self.music.playlistIndex].tracks.append(
            self.music.playlists[self.music.playlistIndex].tracks.pop(songIndex))

    def remove_queued_song(self, songIndex):
        # remove song from queue
        if (songIndex == 0):
            return
        self.music.playlists[self.music.playlistIndex].tracks.pop(songIndex)

    def music_queue_list(self) -> list[Menu]:
        """
        Returns the current queue of songs as menu elements
        """
        _songs = [
            f"{track[:-4]}" for track in self.music.playlists[self.music.playlistIndex].tracks]  # list of song names

        if len(_songs) > 0:
            songs = []  # list of songs as interactable menu objects
            for i, s in enumerate(_songs):
                _songMenu = [Text(s),
                             Button("  Play next", self.make_song_next, i),
                             Button("  Play last", self.make_song_last, i),
                             Button("  Remove", self.remove_queued_song, i)]
                _song = Menu(self, f"{s}",
                             _songMenu, (1,), submenu=True, autoclose=True)
                songs.append(_song)
            return songs  # menu objects to display
        else:
            return [Text("  Queue is empty!")]

    def get_cur_playlist(self) -> str:
        return self.music.playlists[self.music.playlistIndex].name

    def get_cur_song(self) -> str:
        if self.music.player:
            # remove '.mp3' extension from end of string
            return self.music.player.get_source().split('/')[-1][:-4]
        else:
            return "None"

    def get_play_status(self) -> str:
        return "Pause" if self.music.player and self.music.now != None and self.music.player.is_playing() else "Play"

    def toggle_playback(self) -> None:
        if not self.curDevice:
            return
        if self.music.player:
            self.music.toggle_pause(self.manager)
        else:
            self.music.play(self.manager)

    def skip_song(self) -> None:
        self.music.now = None
        self.music.skip()

    def reboot_sys(self): os.system("sudo reboot -h now")
    def shutdown_sys(self): os.system("sudo shutdown -h now")

    def initiate(self):
        self.device.contrast(round(255 * (self.brightness/100)))

        # we pass the ScreenMaster instance to elements that need to takeover drawing
        musicPage = [Text("Now: ", self.get_cur_song),
                     Text("From: ", self.get_cur_playlist),
                     Text("Media Keys: ", self.has_event0),
                     Button(Text("  ", self.get_play_status),
                            self.toggle_playback),
                     Button("  Skip", self.skip_song),
                     Menu(self, "Playlists", None,
                          (0,), updater=self.get_playlists, submenu=True, autoclose=True),
                     Menu(self, "Queue", None, (0,), updater=self.music_queue_list, updateAgain=True,
                          submenu=True, paginate=True, sortable=True)]
        bluetoothPage = [Text("Current: ", self.current_bt_device),
                         Text(""),
                         Toggle("  Scan", False, self.toggle_bt_scan),
                         Menu(self, "Connect Device", None,
                              (0,), updater=self.menu_device_list, submenu=True, autoclose=True),
                         Menu(self, "Remove Device", None, (0,),
                              updater=self.menu_remove_devices, updateAgain=True, submenu=True, autoclose=True),
                         Feed(self, "  Disconnect", self.disconnect_bt_device)]
        systemPage = [Text("System Options"),
                      Prompt(self, "  Reboot", self.reboot_sys),
                      Prompt(self, "  Shutdown", self.shutdown_sys),
                      Prompt(self, "  BT Script", self.run_bt_script),
                      Prompt(self, "  Disable WiFi", None)]
        settingsPage = [Slider(self, "  Brightness", self.device, self.settings['brightness'], self.save_brightness),
                        Toggle("  Reshuffle", self.reshuffle == 1, self.save_reshuffle)]

        options = [Text("Pi MP3 Player"),
                   Menu(self, "Music", musicPage, (3,), submenu=True),
                   Menu(self, "Bluetooth", bluetoothPage, (2,), submenu=True),
                   Menu(self, "System", systemPage, (1,), submenu=True),
                   Menu(self, "Settings", settingsPage, (0,), submenu=True)]
        menu = Menu(self, "Main", options, (1,), btn1=self.toggle_screen)
        menu.activate()


if __name__ == '__main__':
    master = ScreenMaster(get_settings()) # load user configuration
    if len(sys.argv) == 1:
        # clear up funkiness with pulseaudio/dbus
        master.run_bt_script("Initializing...")
    try:
        master.initiate()  # draw the mp3 player menu
    except KeyboardInterrupt:
        print("haulting!")
        if master.manager.thread:
            try:
                master.manager.thread.terminate()
            except Exception:
                pass
            else:
                print("Input listener terminated!")
        # close music player so it doesn't load songs after exit
        master.music.closed = True
        # tell the input listener thread to die, can't terminate like subprocess
        master.manager.shouldDie = True
        # thread listens for media key presses from your speaker,
        # Ex: pressing play/pause button on speaker won't work natively, so i programmed this workaround
        if master.manager.thread and master.manager.thread.is_alive():
            master.manager.thread.join(timeout=7)
