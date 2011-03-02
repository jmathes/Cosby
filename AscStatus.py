
# define burden levels
BURDEN_LEVEL_NONE = 0
BURDEN_LEVEL_BURDENED = 1
BURDEN_LEVEL_STRESSED = 2
BURDEN_LEVEL_STRAINED = 3
BURDEN_LEVEL_OVERTAXED = 4
BURDEN_LEVEL_OVERLOADED = 5

# define hunger levels
HUNGER_LEVEL_SATIATED = -1
HUNGER_LEVEL_NONE = 0
HUNGER_LEVEL_HUNGRY = 1
HUNGER_LEVEL_WEAK = 2
HUNGER_LEVEL_FAINTING = 3
HUNGER_LEVEL_FAINTED = 4
HUNGER_LEVEL_STARVED = 5


class BotStatus:
    """
    This has the information presented in the status line.
    These ten attributes should all be integers.
    """
    def __init__(self):
        # status line info
        self.dlvl = None
        self.gold = None
        self.hp = None
        self.hpmax = None
        self.power = None
        self.powermax = None
        self.ac = None
        self.clvl = None
        self.experience = None
        self.turns = None
        # afflictions
        self.conf = False
        self.foodpois = False
        self.ill = False
        self.blind = False
        self.stun = False
        self.hallu = False
        # virtual afflictions
        self.polymorphed = False
        # burden and hunger levels
        self.burden_level = BURDEN_LEVEL_NONE
        self.hunger_level = HUNGER_LEVEL_NONE

    def set_afflictions(self, status_line):
        self.conf = ('Conf' in status_line)
        self.foodpois = ('FoodPois' in status_line)
        self.ill = ('Ill' in status_line)
        self.blind = ('Blind' in status_line)
        self.stun = ('Stun' in status_line)
        self.hallu = ('Hallu' in status_line)

    def set_hunger_level(self, status_line):
        if 'Satiated' in status_line:
            self.hunger_level = HUNGER_LEVEL_SATIATED
        if 'Hungry' in status_line:
            self.hunger_level = HUNGER_LEVEL_HUNGRY
        if 'Weak' in status_line:
            self.hunger_level = HUNGER_LEVEL_WEAK
        if 'Fainting' in status_line:
            self.hunger_level = HUNGER_LEVEL_FAINTING
        if 'Fainted' in status_line:
            self.hunger_level = HUNGER_LEVEL_FAINTED
        if 'Starved' in status_line:
            self.hunger_level = HUNGER_LEVEL_STARVED

    def set_burden_level(self, status_line):
        if 'Burdened' in status_line:
            self.burden_level = BURDEN_LEVEL_BURDENED
        if 'Stressed' in status_line:
            self.burden_level = BURDEN_LEVEL_STRESSED
        if 'Strained' in status_line:
            self.burden_level = BURDEN_LEVEL_STRAINED
        if 'Overtaxed' in status_line:
            self.burden_level = BURDEN_LEVEL_OVERTAXED
        if 'Overloaded' in status_line:
            self.burden_level = BURDEN_LEVEL_OVERLOADED

    def set_game_status(self, status_line):
        arr = status_line.strip().split()
        word, value = arr[0].split(':')
        self.dlvl = int(value)
        word, value = arr[1].split(':')
        self.gold = int(value)
        arr[2] = arr[2].replace(':', ' ')
        arr[2] = arr[2].replace('(', ' ')
        arr[2] = arr[2].replace(')', ' ')
        word, v1, v2 = arr[2].strip().split()
        self.hp = int(v1)
        self.hpmax = int(v2)
        arr[3] = arr[3].replace(':', ' ')
        arr[3] = arr[3].replace('(', ' ')
        arr[3] = arr[3].replace(')', ' ')
        word, v1, v2 = arr[3].strip().split()
        self.power = int(v1)
        self.powermax = int(v2)
        word, ac = arr[4].split(':')
        self.ac = int(ac)
        if arr[5].startswith('HD'):
            # You are a monster with hit dice instead of experience points.
            self.polymorphed = True
            arr[5] = arr[5].replace(':', ' ')
            word, hd = arr[5].split()
        else:
            # you are a player with experience points
            arr[5] = arr[5].replace(':', ' ')
            arr[5] = arr[5].replace('/', ' ')
            word, v1, v2 = arr[5].strip().split()
            self.clvl = int(v1)
            self.experience = int(v2)
        word, turns = arr[6].split(':')
        self.turns = int(turns)

    def scrape(self, status_line):
        """
        This function returns false if the status line could not be parsed for some reason.
        One reason could by lycanthropy.
        """
        self.set_afflictions(status_line)
        self.set_burden_level(status_line)
        self.set_hunger_level(status_line)
        try:
            self.set_game_status(status_line)
            return True
        except:
            return False

