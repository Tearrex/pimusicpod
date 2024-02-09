from subprocess import check_output, CalledProcessError, DEVNULL
import time, os

# try to do the dirty work

class BTHack:
    def initiate(self, hack_only=False, shouldYield=False):
        #print("Checking cards . . .\n")
        #status = self.check_refusal()
        #if not status: return False
        #elif status != None:
            # first thing to uncomment if this doesnt work
        print("Killing PulseAudio . . .\n")
        try: check_output(["pulseaudio", "-k"], stderr=DEVNULL)
        except CalledProcessError: pass
        else: time.sleep(2)
        if shouldYield: yield 15
        #check_output(["pulseaudio", "--start"])
        #time.sleep(2)
        print("Restarting services . . .\n")
        check_output("sudo service dbus restart".split(' '))
        check_output("sudo service bluetooth restart".split(' '))
        time.sleep(2)
        if shouldYield: yield 20
        print("Reviving PulseAudio . . .")
        check_output(["pulseaudio", "--start"])
        if shouldYield: yield 15
        if not shouldYield:
            stat = self.check_refusal()
            if not stat: return False
        else:
            for s in self.check_refusal(shouldYield=True): yield s
        print("Enabling bluetooth . . .\n")
        check_output("bluetoothctl power on".split(' '))
        if hack_only: 
            if shouldYield: yield 100
            else: return True
        else:
            # start looking for speaker connection
            print(f"Looking for speaker connection . . .")
            if self.look_for_speaker(4, 5):
                print("Bluetooth connected!")
                time.sleep(5)
                #self.play_tone('/home/pi/skip.wav', 2, 2)
                #return True
            else:
                try: check_output("bluetoothctl connect D8:37:3B:0E:9D:C5".split(' '))
                except CalledProcessError:
                    print(f"FAILED TO CONNECT")
                    return False
                else:
                    print("Bluetooth connected!")
                    time.sleep(5)
            if os.path.exists('/dev/input/event0'):
                print(f"Linked succesfully!")
                self.play_tone('/home/pi/skip.wav', 2, 2)
                return True
            else:
                print(f"Couldn't link, restart the device.")
                self.check_refusal()
                self.play_tone('/home/pi/restart.wav', 3, 3)
                time.sleep(10)
                con = self.look_for_speaker(6, 10)
                time.sleep(5)
                if con and os.path.exists('/dev/input/event0'):
                    print(f"Linked succesfully!")
                    self.play_tone('/home/pi/skip.wav', 2, 2)
                    return True
                else:
                    print(f"\nFAILED TO LINK")
                    return False
        #else: return True
    def check_bt_info(self, mac):
        for i in range(6):
            info = check_output(f'bluetoothctl info {mac}'.split(' ')).decode().replace('\t','').split('\n')
            if 'Connected: yes' in info: return True
            time.sleep(10)
        return False
    def look_for_speaker(self, times, pause):
        for i in range(times):
            try: result = check_output("pactl list cards short".split(' ')).decode()
            except CalledProcessError: return False
            else:
                if "bluez_card" in result: return True
                time.sleep(pause)
    def play_tone(self, tone, times, pause):
        for i in range(times):
            os.system(f"paplay {tone}")
            time.sleep(pause)
    def check_refusal(self, messy=False, shouldYield=False):
        maxAttempts = 3
        if messy:
            try: check_output(["pulseaudio", "-k"], stderr=DEVNULL)
            except CalledProcessError: pass
            else: time.sleep(2)
            check_output(["pulseaudio", "--start"], stderr=DEVNULL)
        else:
            while True:
                try: check_output("pactl list cards short".split(' '), stderr=DEVNULL).decode()
                except CalledProcessError:
                    maxAttempts -= 1
                    if maxAttempts <= 0: return False
                    # stupid initialization, restart
                    print("Killing PulseAudio . . .")
                    try: check_output(["pulseaudio", "-k"], stderr=DEVNULL)
                    except CalledProcessError: pass
                    else: time.sleep(2)
                    if shouldYield: yield 5
                    print("Reviving PulseAudio . . .")
                    check_output(["pulseaudio", "--start"])
                    time.sleep(2)
                    if shouldYield: yield 5
                else:
                    if not shouldYield: return True
                    else:
                        yield 10
                        break