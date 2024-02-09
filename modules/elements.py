from luma.core.render import canvas
import RPi.GPIO as GPIO
import time
import json
from PIL import ImageFont

KEY_UP_PIN = 6  # stick up
KEY_DOWN_PIN = 19  # stick down
KEY_LEFT_PIN = 5  # stick left // go back
KEY_RIGHT_PIN = 26  # stick right // go in // validate
KEY_PRESS_PIN = 13  # stick center button
KEY1_PIN = 21  # key 1 // up
KEY2_PIN = 20  # key 2
KEY3_PIN = 16  # key 3 // down

font = ImageFont.load_default()


class Element():
    def __init__(self):
        print("Initiated prototype...")


class Text(Element):
    """
    Non-interactable line of text

    Attributes:
        `text`          Text to display for the menu item\n
        `filler`        Optional callback function returning a string to append to the text"""
    def __init__(self, text, filler=None):
        self.text = text
        self.filler = filler

    def __repr__(self):
        if self.filler:
            return self.text + self.filler()
        else:
            return self.text

    def activate(self): return False


class Button(Element):
    """
    Interactable line of text executing a callback function.

    Attributes:
        `label`         Text to display for the menu item\n
        `action`        The callback function to execute\n
        `args`          Optional argument to provide the callback function.
    """

    def __init__(self, label, action=None, actionArgs=None):
        self.label = label
        self.action = action
        self.args = actionArgs

    def __repr__(self):
        return str(self.label)

    def activate(self):
        if not self.action:
            print(f"Activated button: {str(self.label)}")
        else:
            if self.args:
                if type(self.args) == dict:
                    self.action(**self.args)
                else:
                    self.action(self.args)
            else:
                self.action()
        return True


class Toggle(Element):
    """
    Toggle a feature on/off.

    Attributes:
        `name`          Label for the menu item\n
        `enabled`       Boolean value to set as default\n
        `action`        The callback function taking the boolean value
    """

    def __init__(self, name, enabled=False, action=None):
        self.name = name
        self.enabled = enabled
        self.action = action

    def __repr__(self):
        return f"{self.name}: {self.enabled}"

    def activate(self):
        self.enabled = not self.enabled
        if self.action:
            self.action(self.enabled)
        return True


class Feed(Element):
    """
    Progressively display lines of text from a callback function yielding string values.

    Attributes:
        `master`        Instance of ScreenMaster used to draw on the screen\n
        `title`         Text to display for the menu item\n
        `updater`       The callback function that yields strings\n
        `kwargs`        Optional argument for the callback function
    """

    def __init__(self, master, title, updater, args=None):
        self.master = master
        self.title = title
        self.updater = updater
        self.args = args

    def __repr__(self): return self.title

    def activate(self):
        print(f"Activated feed text: {self.title}")
        lines = []
        for u in self.updater(self.args):
            if isinstance(u, bool) and u:
                lines = []
            elif isinstance(u, tuple):
                for l in u:
                    lines.append(l)
            else:
                if lines and lines[0] != "":
                    lines.append(u)
                else:
                    lines.append(u)
            self.master.DisplayText([str(f) for f in lines if True])
        return True


class Slider(Element):
    """
    Renders a range slider for adjusting the screen's brightness.

    Attributes:
        `master`        Instance of ScreenMaster used to draw on the screen\n
        `title`         Text to display for the menu item\n
        `device`        Instance of the screen device's driver\n
        `value`         Integer value ranging from 0 to 100\n
        `onExit`        Optional callback function to execute upon closing
    """

    def __init__(self, master, title, screenDevice, default=0, onExit=None):
        self.master = master
        self.title = title
        self.device = screenDevice
        self.value = default
        self.onExit = onExit

    def __repr__(self) -> str:
        return self.title

    def activate(self):
        shouldRefresh = True
        # self.device.clear()
        while shouldRefresh:
            self.device.contrast(round(255 * (self.value/100)))
            time.sleep(0.5)
            while GPIO.input(KEY_PRESS_PIN):
                with canvas(self.device) as draw:
                    draw.text(
                        (0, -2), "Set the brightness",  font=font, fill=255)
                    draw.rectangle(((14, 36), (114, 28)), outline=255, fill=0)
                    if not GPIO.input(KEY_LEFT_PIN):
                        if self.value >= 5:
                            self.value -= 5
                            self.device.contrast(
                                round(255 * (self.value/100)))
                            print(f"Brightness: {self.value}%")
                            draw.polygon(
                                [(2, 32), (11, 27), (11, 37)], outline=255, fill=255)
                        shouldRefresh = True
                        # break
                    else:
                        if self.value > 0:
                            draw.polygon(
                                [(2, 32), (11, 27), (11, 37)], outline=255, fill=0)
                    if not GPIO.input(KEY_RIGHT_PIN):
                        if self.value < 100:
                            self.value += 5
                            self.device.contrast(
                                round(255 * (self.value/100)))
                            print(f"Brightness: {self.value}%")
                            draw.polygon(
                                [(117, 27), (117, 37), (126, 32)], outline=255, fill=255)
                        shouldRefresh = True
                        # break
                    else:
                        if self.value < 100:
                            draw.polygon(
                                [(117, 27), (117, 37), (126, 32)], outline=255, fill=0)
                    draw.rectangle(
                        ((14, 36), (14 + round(100 * (self.value/100)), 28)), outline=255, fill=255)
            shouldRefresh = False
        if self.value != self.master.settings["brightness"]:
            # save changes
            self.master.brightness = self.value
            with open("screen.json", 'w') as out:
                out.write(json.dumps(self.master.settings, indent=4))
            print("saved changes to settings!")
            print(self.master.settings)
        if self.onExit:
            self.onExit()
        return True


class Prompt(Element):
    """
    Display a dialogue box to confirm or cancel the execution of a callback function.

    Attributes:
        `master`        Instance of ScreenMaster used to draw on the screen\n
        `title`         Text to display for the menu item\n
        `confirmAction` The callback function to execute
    """

    def __init__(self, master, title, confirmAction):
        self.master = master
        self.title = title
        self.confirmAction = confirmAction
        self.select_range = (1,)

    def __repr__(self): return self.title

    def activate(self):
        optSelect = 2  # select the "No" cancel option by default

        shouldRefresh = True
        while shouldRefresh:
            self.master.DisplayText(
                ["Are you sure?", "  Yes", "  No"], optSelect)
            time.sleep(0.5)
            while True:
                if not GPIO.input(KEY_UP_PIN):
                    if optSelect == self.select_range[0]:
                        if len(self.select_range) > 1:
                            optSelect = self.select_range[1]
                        else:
                            optSelect = 1
                    else:
                        optSelect -= 1
                    break
                elif not GPIO.input(KEY_DOWN_PIN):
                    if optSelect == 2 or len(self.select_range) > 1 and optSelect == self.select_range[1]:
                        optSelect = self.select_range[0]
                    else:
                        optSelect += 1
                    break
                elif not GPIO.input(KEY_RIGHT_PIN):
                    if optSelect == 1 and self.confirmAction:
                        self.confirmAction()
                    return True
                elif not GPIO.input(KEY_LEFT_PIN):
                    shouldRefresh = False
                    break
        return True  # for Menu to close prompt


class Menu(Element):
    """
    Primary element for the main menu, can also be used to create nested submenus.

    Attributes:
        `master`        Instance of ScreenMaster used to draw on the screen\n
        `name`          Text to display for the menu item (if submenu)\n
        `options`       List of elements to show on the menu\n
        `select_range`  Tuple of indexes defining boundaries of menu list element selection\n
        `updater`       Optional callback function to dynamically load-in list of menu elements\n
        `update_again`  Whether or not `updater` should be called again after selecting a menu element\n
        `paginate`      Whether or not `updater` element list should be split into chunks for cyclable pages\n
        `sortable`      Whether or not the paginated element list can be sorted alphabetically by pressing key2/button2.\n
        `submenu`       Whether or not this menu exists inside of another menu\n
        `autoclose`     Whether or not this menu should close itself after selecting a menu element (if submenu)\n
        `btn1`          Optional callback function to execute when key1/button1 is pressed\n
        `btn2`          Optional callback function to execute when key2/button2 is pressed.
        Note: Overrides `sortable` behavior\n
        `btn3`          Optional callback function to execute when key3/button3 is pressed\n
    """

    def __init__(self, master, name: str, options: list, select_range: tuple = (0,),
                 updater=None, submenu: bool = False, updateAgain: bool = False, autoclose: bool = False,
                 btn1=None, btn2=None, btn3=None, paginate: bool = False, sortable: bool = False):
        self.master = master
        self.name = name
        self.options = options
        self.select_range = select_range
        self.updater = updater
        self.submenu = submenu
        self.update_again = updateAgain
        self.autoclose = autoclose
        self.btn1 = btn1
        self.btn2 = btn2
        self.btn3 = btn3
        self.paginate = paginate
        self.sortable = sortable

    def __repr__(self):
        return f"  {self.name}"

    def activate(self):
        if not self.options:
            if self.updater:
                self.options = self.updater()
            else:
                print("Menu Item is not setup correctly")
                return
        else:
            if self.updater:
                self.options.extend(self.updater())
        initialized = False
        optionIndex = self.select_range[0]

        shouldRefresh = True

        pageIndex = 0
        alphabetical = False
        resorted = True

        def refresh_pages():
            return [self.options[i * pageLength:(i + 1) * pageLength]
                    for i in range((len(self.options) + pageLength - 1) // pageLength)]
        if self.paginate:
            pageLength = 7  # number of songs to fit in one "page"
            pages = refresh_pages()
        while shouldRefresh:
            if self.update_again and initialized and not self.paginate:
                if self.updater:
                    self.options = self.updater()
                    initialized = False
                    print("refreshed menu list")
            if not self.paginate:
                self.master.DisplayText([str(option)
                                        for option in self.options], optionIndex)
            else:
                if not resorted:
                    if alphabetical:
                        opts = sorted(self.options, key=str)
                    else:
                        opts = self.options
                    pages = [opts[i * pageLength:(i + 1) * pageLength]
                             for i in range((len(self.options) + pageLength - 1) // pageLength)]
                    resorted = True
                self.master.DisplayText([str(f)
                                         for f in pages[pageIndex] if True], optionIndex)
            time.sleep(0.5)
            while True:
                if not GPIO.input(KEY_UP_PIN):
                    if optionIndex == self.select_range[0]:
                        if len(self.select_range) > 1:
                            optionIndex = self.select_range[1]
                        else:
                            if not self.paginate:
                                optionIndex = len(self.options) - 1
                            else:
                                optionIndex = len(pages[pageIndex]) - 1
                    else:
                        optionIndex -= 1
                    break
                elif not GPIO.input(KEY_DOWN_PIN):
                    if self.paginate and len(pages[pageIndex]) - 1 == optionIndex or optionIndex == (len(self.options) - 1) or len(self.select_range) > 1 and optionIndex == self.select_range[1]:
                        optionIndex = self.select_range[0]
                    else:
                        optionIndex += 1
                    break
                elif not GPIO.input(KEY_RIGHT_PIN):
                    if not self.paginate and self.options[optionIndex].activate() or pages[pageIndex][optionIndex].activate():
                        # if self.dismissable and self.submenu:
                        if self.submenu:
                            if not self.paginate and self.autoclose:
                                shouldRefresh = False  # automatically back out of this submenu
                            elif self.paginate and self.update_again and self.updater:
                                print("rerender queue")
                                self.options = self.updater()  # refresh menu list after selected element closes
                                pages = refresh_pages()
                        break
                elif not GPIO.input(KEY_LEFT_PIN):
                    if self.submenu:
                        shouldRefresh = False
                        break
                elif not GPIO.input(KEY1_PIN):
                    if self.btn1:
                        self.btn1()
                    elif self.paginate:
                        if pageIndex > 0:
                            pageIndex -= 1
                            break
                elif not GPIO.input(KEY2_PIN):
                    if self.btn2:
                        self.btn2()
                    elif self.paginate and self.sortable:
                        alphabetical = not alphabetical
                        resorted = False
                        break
                elif not GPIO.input(KEY3_PIN):
                    if self.btn3:
                        self.btn3()
                    elif self.paginate:
                        if pageIndex < len(pages) - 1:
                            pageIndex += 1
                        break
            initialized = True
        if self.updater:
            self.options = []
        if self.submenu:
            return True
