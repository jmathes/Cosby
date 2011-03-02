
import random

# we need the constants from this file
from AscLevelConstants import *

class MonsterHistory:
    """
    Do a primitive form of monster tracking.
    If a square looks empty but is marked such that
    monster_sightings > 0 and 2^monster_sightings > (current_time - monster_sighting_time)
    then assume a monster is still on the square.
    If you move next to a square and see that it is not
    occupied by a monster, then set both of these values to zero.
    If a monster is not assumed to be on the square,
    but is observed on the square,
    the number of monster sightings is incremented
    and the monster sighting time is reset.

    TODO
    Three increasingly detailed levels of monster description could be provided:
    1) ansi representation
    2) monster type from ';' inspection
    3) individual monster name, for monsters named with 'C'
    """

    def __init__(self, current_level_time, ansi_square):
        # Assert that the monster symbol is valid.
        special_monster_symbols = ":;&@'"
        c = ansi_square.char
        assert (c.isalpha() or c in special_monster_symbols), c
        # Initialize the member variables.
        newansi = ansi_square.copy()
        self.ansi_square = newansi
        self.sighting_time = current_level_time
        self.sighting_count = 1
        self.update_etd()
        self.peaceful = False

    def __str__(self):
        """
        Get a reasonable ascii representation of the monster.
        """
        d = {True:'yes', False:'no'}
        return 'ascii:%s foreground:%d peaceful:%s' % (self.ansi_square.char, self.ansi_square.foreground, d[self.peaceful])

    def update(self, current_level_time):
        """
        Possibly reinforce the location of the monster if the ansi square is unchanged.
        This function can be called from outside of the class.
        """
        if not self.expect_presence(current_level_time):
            self.sighting_time = current_level_time
            self.sighting_count += 1
            self.update_etd()

    def update_etd(self):
        """
        Update the estimated time of departure.
        This should only be called by member functions of this class.
        The etd has this interpretation:
        If the current time is strictly less than the etd then we expect the monster to be present.
        """
        # The estimated time of departure is no earlier than the current time
        self.etd = self.sighting_time
        # Add a base delay that is a positive integer
        base_delay = (1 << (self.sighting_count - 1))
        self.etd += base_delay
        # Add a random delay that is a non-negative integer less than the base delay
        random_delay = random.randrange(base_delay)
        self.etd += random_delay

    def expect_presence(self, current_level_time):
        """
        False if we think the monster has left the square.
        """
        # compare the current level time to the estimated time of departure
        return current_level_time < self.etd

    def set_peaceful(self):
        self.peaceful = True

    def is_peaceful(self):
        return self.peaceful

    def is_pet(self):
        """
        Pets can be pushed out of the way during pathing.
        """
        s = self.ansi_square
        return (self.ansi_square.rev != 0)

    def is_ghost(self):
        s = self.ansi_square
        if s.char == 'X' and s.foreground == 0:
            return True
        return False

    def is_invisible(self):
        s = self.ansi_square
        if s.char == 'I' and s.foreground == 0:
            return True
        return False

    def is_wild_unicorn(self):
        """
        Throw a gem at a non-pet unicorn to make it go away.
        """
        s = self.ansi_square
        if not self.is_pet():
            if not self.is_wild_horse():
                if s.char == 'u':
                    return True
        return False

    def is_wild_horse(self):
        """
        Horses can be tamed by throwing lichen or vegetables to them.
        """
        s = self.ansi_square
        if not self.is_pet():
            if s.char == 'u' and s.foreground == 33:
                return True
        return False

    def is_wild_carnivore(self):
        """
        Dogs and cats are carnivores so you can tame them
        by throwing various meat based products to them.
        """
        s = self.ansi_square
        if not self.is_pet():
            if s.char in list('df') and s.foreground == 37:
                return True
        return False

    def is_untouchable(self):
        """
        Peaceful humans should not be touched.
        """
        if self.is_peaceful():
            if self.ansi_square.char == '@':
                return True
        return False

    def should_fight(self):
        """
        These monsters should be attacked or attack-tested for peacefulness when adjacent to the player.
        """
        s = self.ansi_square
        # do not fight the pet
        if self.is_pet():
            return False
        # do not fight an untouchable monster
        if self.is_untouchable():
            return False
        # do not fight a peaceful monster
        if self.is_peaceful():
            return False
        # brown mold
        if s.char == 'F' and s.foreground == 33:
            return False
        # jellies
        if s.char == 'j':
            return False
        # floating eye
        if s.char == 'e' and s.foreground == 34:
            return False
        return True

    def is_scary(self, levelmap):
        """
        @return: True when we should avoid moving next to the monster.
        In minetown the humans are not scary.
        Note that they should still be tested for peacefulness.
        """
        # we are not scared to be next to a monster that we should not fight
        if not self.should_fight():
            return False
        # we are not scared of any human in minetown
        if self.ansi_square.char == '@':
            if levelmap.level_special == LEVEL_SPECIAL_MINETOWN:
                return False
        return True




