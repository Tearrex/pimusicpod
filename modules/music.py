from subprocess import call, Popen, PIPE, DEVNULL, check_output
from evdev import eventio, uinput, InputEvent, InputDevice, categorize, ecodes
import time
import os
import threading
import random
from omxplayer import OMXPlayer

from modules.bluetooth import BTHack

MUSIC_DIR = "/home/pi/music/playlists"


class InputManager:
    def __init__(self, music):
        self.music = music
        self.shouldReconnect = False
        self.mac = None
        self.jbl = False
        self.thread = None
        self.spamTime = 0
        self.spamTimer = 2
        self.skipTime = 0
        self.skipTimer = 4  # change the actuation time slow/fast
        self.switchTime = 0
        self.switchTimer = 4  # change the actuation time slow/fast
        self.shouldDie = False

    def programmer(self):
        dev = InputDevice('/dev/input/event0')

        print("Listening for inputs...\n")
        for event in dev.read_loop():
            if self.shouldDie:
                print("listener will die now...")
                break
            # there are duplicate inputs for some reason
            if time.time() - self.spamTime <= self.spamTimer:
                #print("ignoring spam")
                continue
            self.spamTime = time.time()

            if event.code != 0:
                yield event.code

    def listener(self):
        if not os.path.exists('/dev/input/event0'):
            print("\nNo event0 found!")
            return
        try:
            dev = InputDevice('/dev/input/event0')

            print("Listening for inputs...\n")
            for event in dev.read_loop():
                if self.shouldDie:
                    break
                # there are duplicate inputs for some reason
                if time.time() - self.spamTime <= self.spamTimer:
                    #print("ignoring spam")
                    continue
                self.spamTime = time.time()

                if self.jbl:
                    if event.code == 163:
                        # if command repeated in rapid succession: skip
                        if time.time() - self.switchTime <= self.switchTimer:
                            # user wants to switch playlists
                            #print("switch called")
                            self.skipTime = 0
                            self.switchTime = 0
                            self.music.switch_playlists()
                            continue
                        elif time.time() - self.skipTime <= self.skipTimer:
                            #print("skip called")
                            self.skipTime = 0
                            self.switchTime = time.time()
                            self.music.skip()
                            continue

                        self.skipTime = time.time()
                        self.music.toggle_pause()
                    elif event.code == 200:
                        self.music.play()
                    elif event.code == 201:
                        # this code occurs when there is actually output on the speaker
                        # should use it to check if the player is being stupid
                        self.music.toggle_pause()
                    else:
                        print(f"strange  code: {event.code}")
                else:
                    if event.code == 163:
                        self.music.skip()
                    elif event.code == 200:
                        self.music.play()
                    elif event.code == 201:
                        self.music.toggle_pause()
                    else:
                        print(f"strange code: {event.code}")
        except Exception as e:
            print(e)
        finally:
            if self.music.player:
                try:
                    self.music.player.pause()
                except Exception as e:
                    print(e)
                else:
                    print("Paused music (disconnected)")
            if self.shouldReconnect:
                thread = threading.Thread(
                    target=self.attempt_reconnect, args=(self.mac,))
                thread.start()
            self.music.curDevice = None
            if self.thread:
                self.thread = None
            #print("something happened!")

    def create_input_listener(self, force=False):
        if not os.path.exists('/dev/input/event0'):
            return False
        elif self.thread != None and self.thread.is_alive() and not force:
            return True
        else:
            self.thread = threading.Thread(target=self.listener)
            self.thread.start()
            return True

    def attempt_reconnect(self, mac):
        print("Trying to reconnect speaker...")
        time.sleep(10)
        restored = False
        for i in range(4):
            try:
                check_output(f'bluetoothctl connect {mac}'.split(' '))
            except Exception as e:
                info = check_output(f'bluetoothctl info {mac}'.split(
                    ' ')).decode().replace('\t', '').split('\n')
                if not "Connected: yes" in info:
                    if i != 3:
                        print(f"Failed attempt {i + 1} of 4...")
                    else:
                        print("Failed to reconnect speaker.")
                else:
                    restored = True
                    break
                time.sleep(10)
            else:
                restored = True
                break
        if restored:
            print("Restored bluetooth connection!")
            if self.music.player and self.music.player.playback_status() == "Paused":
                try:
                    self.music.toggle_pause(self)
                except Exception as e:
                    print(e)
                else:
                    print("Resuming playback.")


class Playlist:
    def __init__(self, name):
        self.name = name
        self.tracks = []
        self.totalTracks = 0
        self.load_tracks()

    def load_tracks(self):
        self.tracks = os.listdir(f"{MUSIC_DIR}/{self.name}")
        self.totalTracks = len(self.tracks)
        self.shuffle()
        print(f"Playlist '{self.name}' has {self.totalTracks} tracks!")

    def shuffle(self):
        # for i in range(len(self.tracks)-1, 0, -1):
        #    j = random.randint(0, i+1)
        #    self.tracks[i], self.tracks[j] = self.tracks[j], self.tracks[i]
        random.shuffle(self.tracks)


class MusicPlayer:
    def __init__(self):
        self.player = None
        self.now = None
        self.switching = False
        self.playlists = []
        self.playlistIndex = 0
        self.fetch_playlists()
        self.closed = False
        self.restart = False

    def fetch_playlists(self):
        folders = os.listdir(MUSIC_DIR)
        for f in folders:
            self.playlists.append(Playlist(f))

    def switch_playlists(self):
        if len(self.playlists) <= 1:
            return
        self.switching = True
        curPlaylist = self.playlists[self.playlistIndex].name
        if self.playlistIndex + 1 >= len(self.playlists):
            self.playlistIndex = 0
        else:
            self.playlistIndex += 1
        newPlaylist = self.playlists[self.playlistIndex].name
        print(f"Switched playlists from `{curPlaylist}` to `{newPlaylist}`")
        # print(self.player.playback_status())
        self.skip()

    def definitive_switch(self, index, skip=False):
        # if len(self.playlists) <= 1: return
        self.switching = True
        curPlaylist = self.playlists[self.playlistIndex].name
        #if self.currentPlaylist + 1 >= len(self.playlists): self.currentPlaylist = 0
        # else: self.currentPlaylist += 1
        if index == self.playlistIndex:
            # reshuffle current playlist
            self.playlists[index].load_tracks()
            print(f"Reshuffled `{curPlaylist}`")
        else:
            self.playlistIndex = index
            newPlaylist = self.playlists[self.playlistIndex].name
            print(
                f"Switched playlists from `{curPlaylist}` to `{newPlaylist}`")
        # print(self.player.playback_status())
        if skip:
            self.skip()

    def on_player_stop(self, p, e):
        if self.closed:
            print("Quitting the music player...")
            return
        if not self.switching:
            # Exit status: {e}\n")
            print(
                f"Ended: {self.playlists[self.playlistIndex].tracks.pop(0)}\n")
        else:
            # Exit status: {e}\n")
            print(
                f"Ended: {self.playlists[self.playlistIndex].tracks[0]}\n")
            self.switching = False
        # self.playlists[self.currentPlaylist].tracks.pop(0)
        #if str(e) == '0': self.player.quit()
        self.player = None
        if self.restart:
            self.restart = False
            return
        if len(self.playlists[self.playlistIndex].tracks) > 0:
            if not self.closed:
                #print("pulling a sneaky one ehehehehe!")
                self.create_player()
        else:
            print("END OF PLAYLIST")
            if not self.closed:
                self.playlists[self.playlistIndex].load_tracks()
                self.create_player()

    # omxplayer -o alsa:pulse Prolly_w_music_YUNG_VAMP.mp3

    def create_player(self, trackIndex=0, sleep=0):
        if self.player or self.closed:
            print("player already exists")
            return
        curPlaylist = self.playlists[self.playlistIndex]
        toPlay = f"{MUSIC_DIR}/{curPlaylist.name}/{curPlaylist.tracks[trackIndex]}"
        try:
            print(toPlay)
            player = OMXPlayer(toPlay,
                               dbus_name=f"org.mpris.MediaPlayer2.omxplayer1",
                               args=['-o', 'alsa:pulse', '--no-osd'])
            self.player = player
            self.player.exitEvent = self.on_player_stop
        except Exception as e:
            print(e)
            print(
                "Something nasty happened! Rebooting . . .")
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                print("Nevermind!")
            else:
                os.system("sudo reboot -h now")
        else:
            self.player = player
            # print(self.player.volume())
            if not self.switching:
                self.now = toPlay.split('/')[-1][:-4]
                print(
                    f"Now playing: {self.now} from '{curPlaylist.name}'({curPlaylist.totalTracks-len(curPlaylist.tracks)+1}/{curPlaylist.totalTracks})")
            else:
                self.player.stop()
        #command = [f"omxplayer -o alsa:pulse {musicDir}/{track}"]
        #self.currentTrack = track
        # self.player = Popen(command, stdin=PIPE, stdout=PIPE,
        # close_fds=True, bufsize=0, shell=True)

    def play(self, _input=None):
        if not self.player and len(self.playlists[self.playlistIndex].tracks) > 0:
            if _input and os.path.exists('/dev/input/event0'):
                if not _input.thread or not _input.thread.is_alive():
                    _input.create_input_listener(True)
                print("Created input listener!")
            print("Starting . . .")
            self.create_player()

    def toggle_pause(self, _input=None):
        if not self.player:
            print("player doesnt exist")
            return
        if _input and os.path.exists('/dev/input/event0'):
            if not _input.thread or not _input.thread.is_alive():
                _input.create_input_listener(True)
                print("Created input listener!")
        # print(self.player.volume())
        self.player.play_pause()
        if self.player.playback_status() == "Paused":
            print("❚❚")
        else:
            print("⏵︎")
        #self.player.stdin.write(bytes('p', 'utf-8'))
        #self.player.communicate(input=bytes('p', 'utf-8'))
        # self.player.stdin.flush()

    def skip(self):
        if not self.player:
            print("no player to skip")
            return
        curTrack = self.playlists[self.playlistIndex].tracks[0]
        try:
            self.player.stop()
        except EnvironmentError as e:
            print(f"Can't skip {curTrack}: {e}")
        else:
            print(f"\nSkipping: {curTrack}")


if __name__ == '__main__':
    # set this to false before work so it reboots on any errors!!!
    debug = True
    print("Disabling debug mode in 5 seconds (Ctrl+C to cancel)")
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print(f"\nDebug mode enabled!")
    else:
        debug = False

    hack = BTHack()
    if not os.path.exists('/dev/input/event0') and not hack.initiate():
        print(f"\n\nCan't launch!")
        exit()

    music = MusicPlayer()
    manager: InputManager = InputManager(music)
    try:
        status = manager.listener()
    except KeyboardInterrupt:
        print("oh no!")
    except Exception as e:
        print(e)
    finally:
        print("i sleep now")
        music.closed = True
        exit()
    # while True:
    #    if not manager.music.player and not manager.music.paused:
        #print("start new track!")
        # manager.music.play()
    #    else:
    #        print("sleeping")
        # if manager.music.player:
        # manager.music.player.wait()
        # manager.music.tracks.remove(manager.music.currentTrack)
        #manager.music.currentTrack = None
        #manager.music.player = None
    #        time.sleep(5)
    #manager.shouldDie = True
    # manager.thread.join()
