
"""
As the NetHack bot is able to go deeper into the dungeon,
it becomes important for it to be sure to know which level it is on.
This module provides a very high level view of the dungeon topology.

Here are some assumptions for the current bot:
    - The branch of each level is one of {BRANCH_MINES, BRANCH_DOOM, BRANCH_SOKOBAN}.
    - Going down a staircase always leads somewhere one level deeper.
    - Going up a staircase leads somewhere one level shallower except for the up staircase in the top level.

Here are some operations:
    - staircase descent (old level object, new ansi)
    - staircase ascent (old level object, new ansi)
    - uncontrolled level change (old level, new dlvl, new ansi)

Dungeon constraints:
    - doom fork is on dlvl {2, 3, 4}
    - oracle is on dlvl {5, 6, 7, 8, 9}
    - rogue is on dlvl {15, 16, 17, 18}
    - minetown is on doom fork + {3, 4}
    - mines end is on doom fork + {8, 9}
"""

from AscLevelInfoConstants import *

class FirstImpression:
    """
    This class has information that is known about a new level immediately after changing dlvls.
    This information is important for identifying the branch of the new level,
    and possibly for identifying the branch of the linking level.
    """
    def __init__(self, dlvl, location):
        self.dlvl = dlvl
        self.location = location
        self.sokoban = None
        self.doors = False
        self.cavern_walls = False

class TemporaryLevelData:
    """
    For a given (dlvl, branch) pair this information may be corrupted by an unrecognized visit.
    This includes the terrain and the items and monsters in the level.
    """
    def __init__(self):
        # This is just a link.
        # The permanent level data object may survive the destruction of the temporary level data.
        self.permanent_level_data = None


class PermanentLevelData:
    """
    For a given (dlvl, branch) pair this information never reverts.
    """
    def __init__(self, dungeon, first_impression):
        self.dungeon = dungeon
        self.staircases = []
        self.levelports = []
        self.dlvl = None
        self.branch = None
        self.special = None
        self.doors = False
        self.cavern_walls = False
        self.sink = False
        self.fountain = False
        self.read_first_impression(first_impression)

    def read_first_impression(self, first_impression):
        """
        @param first_impression: the data available immediately upon arriving at the target level
        """
        # Assert that the first impression is consistent with the current knowledge.
        if first_impression.dlvl and self.dlvl:
            assert first_impression.dlvl == self.dlvl
        if first_impression.sokoban == True:
            assert not self.special
            if self.branch:
                assert self.branch == BRANCH_SOKOBAN
        if first_impression.sokoban == FALSE:
            assert self.branch != BRANCH_SOKOBAN
        # Update the permanent level data using the first impression data.
        if not self.dlvl:
            self.dlvl = first_impression.dlvl
        if first_impression.sokoban == True:
            self.branch = BRANCH_SOKOBAN
        self.doors |= first_impression.doors
        self.cavern_walls |= first_impression.cavern_walls

    def update(self, other):
        """
        This function is analogous to the builtin set update which adds elements of the other set.
        The other PermanentLevelData object should not conflict with this object.
        @param other: another PermanentLevelData object
        """
        # Assert that the permanent level data is compatible with the other permanent level data source.
        if self.dlvl and other.dlvl:
            assert self.dlvl == other.dlvl
        if self.branch and other.branch:
            assert self.branch == other.branch
        if self.special and other.special:
            assert self.special == other.special
        # Update the permanent level data using the other permanent level data source.
        if not self.dlvl:
            self.dlvl = other.dlvl
        if not self.branch:
            self.branch = other.branch
        if not self.special:
            self.special = other.special
        self.doors |= other.doors
        self.cavern_walls |= other.cavern_walls

    def gen_down_staircases(self):
        for staircase in self.staircases:
            if staircase.dlvl > self.dlvl:
                yield staircase

    def gen_up_staircases(self):
        for staircase in self.staircases:
            if staircase.dlvl < self.dlvl:
                yield staircase

    def should_check_doorways(self):
        """
        @return: True when checking for doorways may resolve the branch or the level.
        """
        # always check an unknown branch for doorways
        if not self.branch:
            return True
        # never check a known special level for doorways
        if self.special:
            return False
        # check a level in the mines for doorways if it might be minetown
        if self.branch == BRANCH_MINES:
            if not self.dungeon.get_special_level(SPECIAL_MINETOWN):
                if self.dlvl in self.dungeon.get_possible_minetown_dlvls():
                    return True
        # do not check for doorways in any other situation
        return False

    def has_secret_doors(self):
        """
        @return: True when random secret doors may have been placed on the level.
        """
        if self.branch == BRANCH_UNKNOWN:
            return True
        elif self.branch == BRANCH_DOOM:
            return True
        elif self.branch == BRANCH_MINES:
            return not self.flag_cavern_walls
        elif self.branch == BRANCH_SOKOBAN:
            return False
        else:
            assert False

    def get_possible_up_staircase_count(self):
        """
        The structure of this function is to check the more-restricted levels before those less-restricted.
        @return: the greatest number of up staircases that this level could possibly have
        """
        # The last level of sokoban has no staircase up.
        if self.branch == BRANCH_SOKOBAN:
            sokoban_fork = self.dungeon.get_special_level(SPECIAL_SOKOBAN_FORK)
            if sokoban_fork:
                if self.dlvl == sokoban_fork.dlvl - 4:
                    return 0
        # For practical purposes the top level has no staircase up.
        if self.special == SPECIAL_TOP:
            return 0
        # Levels in the mines have at most one staircase up.
        if self.branch == BRANCH_MINES:
            return 1
        # Levels in the dungeons of doom have at most one staircase up except for the sokoban fork.
        if self.branch == BRANCH_DOOM:
            if self.dlvl not in self.dungeon.get_possible_sokoban_fork_dlvls():
                return 1
        # Levels in sokoban have at most one staircase up.
        if self.branch == BRANCH_SOKOBAN:
            return 1
        # Levels in the dungeons of doom have at most two staircases up.
        if self.branch == BRANCH_DOOM:
            return 2
        # That should cover all possible cases.
        assert False

    def get_possible_down_staircase_count(self):
        """
        The structure of this function is to check the more-restricted levels before those less-restricted.
        @return: the greatest number of down staircases that this level could possibly have
        """
        # The bottom of the mines has no staircase down.
        if self.special == SPECIAL_MINES_END:
            return 0
        # Levels in the mines have at most one staircase down.
        if self.branch == BRANCH_MINES:
            return 1
        # Levels in sokoban have at most one staircase down.
        if self.branch == BRANCH_SOKOBAN:
            return 1
        # Levels in the dungeons of doom have at most one staircase down except for the doom fork.
        if self.branch == BRANCH_DOOM:
            if self.dlvl not in self.dungeon.get_possible_doom_fork_dlvls():
                return 1
        # Levels in the dungeons of doom have at most two staircases down.
        if self.branch == BRANCH_DOOM:
            return 2
        # That should cover all possible cases.
        assert False

    def assert_valid(self):
        """
        Run some various assertions.
        This is called when the dungeon is updated.
        Inferences are allowed to be incomplete but they are not allowed to conflict.
        """
        # Assert that the number of up and down staircases on this level is valid.
        up_staircases = list(self.gen_up_staircases())
        down_staircases = list(self.gen_down_staircases())
        assert len(self.staircases) == len(up_staircases) + len(down_staircases)
        assert self.get_possible_up_staircase_count() <= len(up_staircases)
        assert self.get_possible_down_staircase_count() <= len(down_staircases)
        # Assert flag consistency.
        if self.branch == BRANCH_SOKOBAN:
            assert not self.flag_cavern_walls
            assert not self.flag_sink
            assert not self.flag_fountain
        if self.branch == BRANCH_DOOM:
            assert not self.flag_cavern_walls
        if self.branch == BRANCH_MINES:
            assert not self.flag_sink
        assert not (self.flag_sink and self.flag_cavern_walls)
        # If there are two staircases up or down then assert that they do not point to the same branch.
        for staircase_group in (up_staircases, down_staircases):
            if len(staircase_group) == 2:
                staircase_a, staircase_b = staircase_group
                target_level_a = staircase_a.target_level
                target_level_b = staircase_b.target_level
                if target_level_a and target_level_b:
                    branch_a = target_level_a.branch
                    branch_b = target_level_b.branch
                    if branch_a and branch_b:
                        assert branch_a == branch_b


        

class DirectedLink:
    """
    This is a base class for a directional link between levels.
    The link may be a stair.
    The link may be a uncontrolled fall through a hole or trap door.
    The link may be a levelport.
    """
    def __init__(self, dungeon, first_impression):
        """
        @param first_impression: the data available immediately upon arriving at the target level
        """
        # data known about the target level even if no temporary level data is known
        self.pdata = PermanentLevelData(dungeon, first_impression)
        # transient data about the target level that may be erased when the level is revisited via a different link
        self.tdata = None

    def read_first_impression(self, first_impression):
        self.pdata.read_first_impression(first_impression)


class Staircase(DirectedLink):
    def __init__(self, location, first_impression):
        """
        @param location: the location of the staircase on its host level
        @param first_impression: the data available immediately upon arriving at the target level
        """
        DirectedLink.__init__(self, first_impression)
        self.location = location
        self.target_location_multiset = {first_impression.location : 1}

    def read_first_impression(self, first_impression):
        DirectedLink.read_first_impression(self, first_impression)
        self.add_target_location(first_impression.location)

    def get_target_location(self):
        """
        Guess the target location using the multiset.
        @return: the best (row, col) location of the destination of the staircase, or None if unknown.
        """
        if self.target_location_multiset:
            count, target = max((count, loc) for loc, count in self.target_location_multiset.items())
            return target

    def add_target_location(self, target_location)
        """
        @param target_location: the (row, col) where the player landed after having followed this staircase
        """
        # Add the target location to the multiset of target locations.
        # The target locations may differ even for the same staircase if the player is displaced.
        if target_location not in self.target_location_multiset:
            self.target_location_multiset[target_location] = 0
        self.target_location_multiset[target_location] += 1


class Level:
    """
    This is the base class from which other level classes should be derived.
    """
    def __init__(self):
        """
        The levelport_target_levels list is not a set because I do not want to make level hashable.
        The redundancy among flags exists because I want all of the flags to only ever change state from False to True.
        """
        self.dungeon = None
        self.branch = BRANCH_UNKNOWN
        self.special = SPECIAL_UNKNOWN
        self.dlvl = None
        self.staircases = []
        self.levelport_target_levels = []
        # Once a flag is set to True it can never be reset to False.
        self.flag_doors = False
        self.flag_cavern_walls = False
        self.flag_sink = False
        self.flag_fountain = False
        self.flag_sokoban = False
        self.flag_not_sokoban = False

    def set_dungeon(self, dungeon):
        self.dungeon = dungeon
class Dungeon:
    def __init__(self, level_factory=Level):
        """
        @param level_factory: a callable that takes no parameters and returns an object with an interface compatible with Level.
        """
        self.levels = []
        self.current = None
        assert callable(level_factory)
        self.level_factory = level_factory

    def gen_mines_levels(self):
        for level in self.levels:
            if level.branch == BRANCH_MINES:
                yield level

    def gen_doom_levels(self):
        for level in self.levels:
            if level.branch == BRANCH_DOOM:
                yield level

    def add_level(self, level):
        self.levels.append(level)

    def get_special_level(self, special_level_constant):
        special_level_matches = [level for level in self.levels if level.special == special_level_constant]
        assert len(special_level_matches) in (0, 1)
        if special_level_matches:
            return special_level_matches[0]

    def get_possible_sokoban_fork_dlvls(self):
        level = self.get_special_level(SPECIAL_SOKOBAN_FORK)
        if level:
            return set([level.dlvl])
        dlvls = set()
        for dlvl in self.get_possible_oracle_dlvls():
            dlvls.add(dlvl + 1)
        return dlvls

    def get_possible_oracle_dlvls(self):
        level = self.get_special_level(SPECIAL_ORACLE)
        if level:
            return set([level.dlvl])
        return set([5, 6, 7, 8, 9])

    def get_possible_doom_fork_dlvls(self):
        level = self.get_special_level(SPECIAL_DOOM_FORK)
        if level:
            return set([level.dlvl])
        return set([2, 3, 4])

    def get_possible_minetown_dlvls(self):
        level = self.get_special_level(SPECIAL_MINETOWN)
        if level:
            return set([level.level_info.dlvl])
        dlvls = set()
        for dlvl in self.get_possible_doom_fork_dlvls():
            for delta in (3, 4):
                dlvls.add(dlvl + delta)
        return dlvls

    def get_possible_mines_end_dlvls(self):
        level = self.get_special_level(SPECIAL_MINES_END)
        if level:
            return set([level.dlvl])
        dlvls = set()
        for dlvl in self.get_possible_doom_fork_dlvls():
            for delta in (8, 9):
                dlvls.add(dlvl + delta)
        return dlvls

    def update_step(self):
        """
        Make inferences about the dungeon state if possible.
        @return: True if at least one inference was made.
        """
        # Identify the top level by its unique dlvl.
        if not self.get_special_level(SPECIAL_TOP):
            for level in self.levels:
                if level.dlvl == 1:
                    level.special = SPECIAL_TOP
                    level.branch = BRANCH_DOOM
                    return True
        # Identify the sokoban fork level.
        if not self.get_special_level(SPECIAL_SOKOBAN_FORK):
            for level in self.gen_doom_levels():
                # Identify the sokoban fork level by its staircase count.
                if len(level.get_up_staircases()) == 2:
                    level.special = SPECIAL_SOKOBAN_FORK
                    return True
                # Identify the sokoban fork level if it is on the doom branch and has stairs up to sokoban.
                for staircase in level.get_up_staircases():
                    if staircase.target_level:
                        if staircase.target_level.branch == BRANCH_SOKOBAN:
                            level.special = SPECIAL_SOKOBAN_FORK
                            return True
        # Identify the doom fork level.
        if not self.get_special_level(SPECIAL_DOOM_FORK):
            for level in self.gen_doom_levels():
                # Identify the doom fork level by its staircase count.
                if len(level.get_down_staircases()) == 2:
                    level.special = SPECIAL_DOOM_FORK
                    return True
                # Identify the doom fork level if it is on the doom branch and has stairs down to the mines.
                for staircase in level.get_down_staircases():
                    if staircase.target_level:
                        if staircase.target_level.branch == BRANCH_MINES:
                            level.special = SPECIAL_DOOM_FORK
                            return True
        # A down staircase on a doom level will lead to a doom level except from doom fork.
        for level in self.gen_doom_levels():
            if level.dlvl not in self.get_possible_doom_fork_levels():
                for staircase in level.get_down_staircases():
                    if staircase.target_level:
                        if staircase.target_level.branch == BRANCH_UNKNOWN:
                            staircase.target_level.branch = BRANCH_DOOM
                            return True
        # An up staircase on a doom level will lead to a doom level except from sokoban fork.
        for level in self.gen_doom_levels():
            if level.dlvl not in self.get_possible_sokoban_fork_levels():
                for staircase in level.get_up_staircases():
                    if staircase.target_level:
                        if staircase.target_level.branch == BRANCH_UNKNOWN:
                            staircase.target_level.branch = BRANCH_DOOM
                            return True
        # A down staircase on a mines level will lead to a mines level.
        for level in self.gen_mines_levels():
            for staircase in level.get_down_staircases():
                if staircase.target_level:
                    if staircase.target_level.branch == BRANCH_UNKNOWN:
                        staircase.target_level.branch = BRANCH_MINES
                        return True
        # An up staircase on a mines level will lead to a mines level except when it leads to doom fork.
        for level in self.gen_mines_levels():
            for staircase in level.get_up_staircases():
                if staircase.target_level:
                    if staircase.target_level.dlvl not in self.dungeon.get_possible_doom_fork_dlvls():
                        if staircase.target_level.branch == BRANCH_UNKNOWN:
                            staircase.target_level.branch = BRANCH_MINES
                            return True
        # An uncontrolled fall or levelport from a doom level always goes to a doom level.
        for level in self.gen_doom_levels():
            for target_level in level.levelport_target_levels:
                if target_level.branch == BRANCH_UNKNOWN:
                    target_level.branch = BRANCH_DOOM
                    return True
        # An uncontrolled fall or levelport from a mines level goes to a mines level or to a low dlvl doom level.
        for level in self.gen_mines_levels():
            for target_level in level.levelport_target_levels:
                doom_fork_dlvls = self.dungeon.get_possible_doom_fork_dlvls()
                if target_level.dlvl > max(doom_fork_dlvls):
                    if target_level.branch == BRANCH_UNKNOWN:
                        target_level.branch = BRANCH_MINES
                        return True
                elif target_level.dlvl < min(doom_fork_dlvls):
                    if target_level.branch == BRANCH_UNKNOWN:
                        target_level.branch = BRANCH_DOOM
                        return True
        # No inference was possible.
        return False

    def assert_valid(self):
        """
        Make assertions about the dungeon state.
        """
        # Assert that each level is in a valid state.
        for level in self.levels:
            level.assert_valid()
        # Assert that no special level is duplicated.
        special_levels = set()
        for level in levels:
            if level.special != SPECIAL_UNKNOWN:
                assert level.special not in special_levels
                special_levels.add(level.special)
        # Assert that for each branch there is at most one level for each dlvl.
        branch_dlvl_pairs = set()
        for level in self.levels:
            if level.branch != BRANCH_UNKNOWN:
                branch_dlvl_pair = (level.branch, level.dlvl)
                assert branch_dlvl_pair not in branch_dlvl_pairs
                branch_dlvl_pairs.add(branch_dlvl_pair)

    def update(self):
        """
        Repeatedly make inferences until no more can be made.
        This function is called to validate and propagate state changes.
        """
        while True:
            self.assert_valid()
            state_changed = self.update_step()
            if not state_changed:
                break
    
    def remove_level(self, dead_level):
        """
        A dead level is defined as one that the player departed before dungeon branch of the level was identified.
        Remove all references to the dead level.
        This behavior may throw away useful level information,
        but it avoids the problem of using incorrect level information.
        """
        for level in self.levels:
            for staircase in level.staircases:
                if staircase.target_level is dead_level:
                    staircase.target_level = None
            self.levelport_target_levels = [x for x in level.levelport_target_levels if x is not dead_level]

    def notify_controlled_level_change(self, old_stair_location, new_dlvl, new_location):
        """
        The player went up or down the stairs of his own volition.
        This function changes the current level.
        """
        # Find the staircase that was taken.
        matching_staircases = [x for x in self.staircases if x.location == old_stair_location]
        assert len(matching_staircases) in (0, 1)
        dlvl_delta = new_dlvl - self.current.dlvl
        assert dlvl_delta in (-1, 1)
        if matching_staircases:
            # If a matching staircase was found then follow it if it has a target level.
            staircase = matching_staircases[0]
            assert staircase.dlvl_delta == dlvl_delta
        else:
            # If a matching staircase was not found then
            # identify special levels that are determined by multiple staircases
            # and create the new staircase.
            if dlvl_delta == 1:
                # Try to identify the doom fork level by multiple down staircases if it is not already identified.
                down_staircases = [x for x in self.staircases if x.dlvl_delta == 1]
                assert len(down_staircases) in (0, 1)
                if len(down_staircases) == 1:
                    assert self.current.branch in (BRANCH_UNKNOWN, BRANCH_DOOM):
                    assert self.current.dlvl in self.get_possible_doom_fork_dlvls()
                    doom_fork_level = self.get_special_level(SPECIAL_DOOM_FORK)
                    if doom_fork_level:
                        assert self.current is doom_fork_level
                    else:
                        self.current.special = SPECIAL_DOOM_FORK
            elif dlvl_delta == -1:
                # Try to identify the sokoban fork level by multiple up staircases if it is not already identified.
                up_staircases = [x for x in self.staircases if x.dlvl_delta == -1]
                if len(up_staircases) == 1:
                    assert self.current.branch in (BRANCH_UNKNOWN, BRANCH_DOOM):
                    assert self.current.dlvl in self.get_possible_sokoban_fork_dlvls()
                    assert not self.get_special_level(SPECIAL_DOOM_FORK)
                    self.current.special = SPECIAL_DOOM_FORK
            if staircase.target_level:
                target_level = staircase.target_level
            staircase = Staircase(old_stair_location, dlvl_delta)
            self.current.staircases.append(staircase)
            # create and identify the new level if possible
            level = self.level_factory()
            level.set_dungeon(self)
            level.dlvl = new_dlvl
            self.identify_new_level_controlled(level)
            staircase.set_target_level(level)
        # Add the new location to the targets of the staircase that was taken.
        staircase.add_target_location(new_location)
        # If the dungeon branch of the original level was unknown then remove the original level.
        if self.current.branch == BRANCH_UNKNOWN:
            self.remove_level(self.current)
        # Set the current level to the new level.
        self.current = level

    def notify_uncontrolled_level_change(self, new_dlvl):
        """
        The player fell or was levelported between levels.
        This function changes the current level.
        """
        pass

    def notify_sokoban(self):
        """
        This level is a sokoban level.
        Identification of sokoban levels is very easy because they can be hard coded.
        """
        pass

    def notify_not_sokoban(self):
        """
        This level is not a sokoban level.
        Identification of sokoban levels is very easy because they can be hard coded.
        """
        pass

    def notify_door(self):
        """
        This is called when a door is observed on the current level.
        Some ways of observing a door include:
            - seeing the ansi symbol for an open or closed door
            - getting a message regarding actions performed involving door
            - identifying an empty doorway using ';'
            - hearing door related dungeon sounds
        """
        pass

    def notify_cavern_walls(self):
        """
        This is called when cavern walls are observed on the current level.
        This is determined by the ansi pattern.
        """
        pass

    def notify_oracle(self):
        """
        This is called when the oracle is seen or heard on the level.
        """
        pass

    def notify_vault(self):
        """
        This is called when a vault is found or heard on the level.
        """
        pass

    def notify_shop(self):
        """
        This is called when a shop is found or heard on the level.
        """
        pass

    def notify_sink(self):
        """
        This is called when a sink is found or heard on the level.
        """
        pass

    def notify_fountain(self):
        """
        This is called when a fountain is found or heard on the level.
        """
        pass

    def get_door_sounds(self, hallu):
        """
        @return: a list of door sounds
        """
        return ['You hear a door open']

    def get_oracle_sounds(self, hallu):
        """
        @param hallu: True if the player is hallu
        @return: a list of oracle sounds
        """
        if hallu:
            sounds = [
                    'You hear someone say "No more woodchucks!"',
                    'You hear a loud ZOT!'
                    ]
        else:
            sounds = [
                    'You hear a strange wind.',
                    'You hear convulsive ravings.',
                    'You hear snoring snakes.'
                    ]
        return sounds

    def get_vault_sounds(self, hallu):
        """
        There are no vaults in the mines branch.
        @param hallu: True if the player is hallu
        @return: a list of vault sounds
        """
        if hallu:
            sounds = [
                    'You hear Ebenezer Scrooge!',
                    'You hear the quarterback calling the play.'
                    ]
        else:
            sounds = [
                    'You hear the footsteps of a guard on patrol.',
                    'You hear someone searching.',
                    'You hear someone counting money.'
                    ]
        return sounds

    def get_shop_sounds(self, hallu):
        """
        There are no shops in the mines branch except in minetown.
        @param hallu: True if the player is hallu
        @return: a list of shop sounds
        """
        if hallu:
            sounds = [
                    'You hear Neiman and Marcus arguing!'
                    ]
        else:
            sounds = [
                    'You hear someone cursing shoplifters.',
                    'You hear the chime of a cash register.'
                    ]
        return sounds

    def get_sink_sounds(self, hallu):
        """
        There are no sinks in the mines.
        @param hallu: True if the player is hallu
        @return: a list of sink sounds
        """
        if hallu:
            sounds = [
                    'You hear dishes being washed!'
                    ]
        else:
            sounds = [
                    'You hear a slow drip.',
                    'You hear a gurgling noise.'
                    ]
        return sounds

    def get_fountain_sounds(self, hallu):
        """
        There are no fountains in the mines except for some minetowns.
        @param hallu: True if the player is hallu
        @return: a list of fountain sounds
        """
        if hallu:
            sounds = [
                    'You hear a soda fountain!'
                    ]
        else:
            sounds = [
                    'You hear bubbling water.',
                    'You hear water falling on coins.',
                    'You hear the splashing of a naiad.'
                    ]
        return sounds






def run():
    pass


if __name__ == '__main__':
    run()

