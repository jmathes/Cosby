"""
Connect to nethack.alt.org
and play some nethack.
"""

import profile
import socket
import select
import sys
import time
import random
import re

from AscTelnet import Telnet
from AscTelnet import STATE_WANT_TO_SEND_DATA
from AscTelnet import STATE_WAITING_FOR_DATA
from AscTelnet import STATE_WANT_TO_SEND_PING
from AscTelnet import STATE_WAITING_FOR_DATA_AND_PONG

from AscAnsi import Ansi, AnsiSquare

from AscSelect import ObjectPicker

from AscUtil import ascii_to_meta
from AscUtil import get_bounding_coordinates

from AscInventory import AscInventory
from AscInventory import gen_things_that_are_here, get_pick_up_what, gen_floor_items, item_selection_helper

from AscLore import AscLore, IdGenerator

import AscSokoban

# Some important constants are imported here:
# HM_*
# SM_*
# Also:
# LevelMap
# LevelSquare
from AscLevel import *

# Some important constants are imported here:
# BURDEN_LEVEL_*
# HUNGER_LEVEL_*
# Also:
# BotStatus
from AscStatus import *


class CidBot:
    def get_username(self):
        return '...'
    def get_password(self):
        return '...'
    def get_role(self):
        return 'Plunderer'


class GatherBot(CidBot):
    """
    This ball of mud constantly needs refactoring.
    """
    def __init__(self):
        self.id_generator = IdGenerator()
        self.dungeon = Dungeon()
        self.log = open('gatherer.log', 'a')
        print >> self.log, '__init__'
        self.message_log = open('messages.log', 'a')
        self.levelmap = None
        self.lore = AscLore()
        self.inventory = AscInventory(self.lore)
        # open adjacent doors
        self.last_door_opening_location = None
        self.last_door_opening_direction = None
        # identify adjacent traps
        self.unidentified_adjacent_trap_location = None
        self.unidentified_adjacent_trap_direction = None
        # vital stats of the bot; also turns and dlvl
        self.status = BotStatus()
        # this gathers messages across '--More--' screens.
        self.messages = []
        # where was the cursor last real turn?
        self.last_cursor_location = None
        # these variables are for keeping track of when and
        # where we started searching for traps or secret doors.
        self.search_location = None
        self.search_turn_begin = None
        # this is the location of an object we chose
        # using the remote object viewer
        self.pick_an_object_location = None
        # flag selection mode
        # the words "Pick an object." are not always at the top of the screen
        # while in this mode if symbols are used to move the cursor.
        self.moving_the_selection_cursor = False
        # did we read a message that indicates that we should look at the ground?
        self.should_look_at_ground = False
        # are we in the process of looking at the ground?
        self.ground_check = False
        # are we trapped in a pit?
        # if we are then we cannot reach over the edge of a pit to open a door.
        self.trapped_pit = False
        # which region is trying to link to another region?
        self.linking_region = None
        # this is only true before looking at the first square with ':'.
        self.checked_first_square = False
        # these variables help enforce the separation between
        # reading messages and taking actions.
        self.should_pray = False
        self.should_enhance = False
        self.should_quit = False
        # we should check our inventory when we start
        self.should_do_inventory = True
        # do we know if something on the ground is worth picking up?
        self.should_pick_up = False
        # the inventory-like screens provide annoyingly little context so we have to do this ourselves
        self.should_read_inventory = False
        self.should_continue_pick_up = False
        self.should_continue_drop = False
        self.should_continue_looting = False
        # which item to apply?
        self.apply_letter = None
        # which item to eat?
        self.eating_letter = None
        # what is the throwing state?
        self.missile_letter = None
        self.missile_direction = None
        # which location are we trying to attack?
        # this is important for distinguishing between friendly and hostile monsters
        self.attack_location = None
        # this is a list of letters remaining in the name of an item that is being named
        self.remaining_moniker_letters = None
        # this is to help keep track of where we are within the dungeon
        self.expecting_level_change = False
        # do we have lycanthropy?
        # this is not in the status object because its state is only known through messages
        self.lycanthropic = False
        # how much nutrition have we consumed since the last time we prayed?
        self.consumed_nutrition = 500
        # are we turning to stone?
        self.turning_to_stone = False
        # are we stuck?
        self.recent_initiative_commands = []
        self.recent_initiative_hashes = []
        # do we need to look at a square to see why we are stuck?
        self.stuck_target_location = None
        self.stuck_target_direction = None
        # if we have determined that the bot is stuck
        # and it is not because of something embedded in a dungeon feature
        # then try to open it in case it is something on an open door
        self.should_open_stuck_target = False
        # which way did we try to push the boulder and where do we expect to end up?
        self.last_sokoban_push_delta = None
        self.last_sokoban_push_target = None
        # did our last attempt to push the boulder fail?
        self.boulder_failure = False
        # which direction are we trying to untrap something?
        self.untrap_direction = None
        # what is the name of the large container we are trying to untrap?
        self.untrap_moniker = None
        # in what direction do we want to lock a container?
        self.container_unlocking_direction = None
        # what is the name of the large container we are trying to unlock?
        # this is relevant for interpreting a message that something seems to be locked
        self.unlock_moniker = None
        # what is the name of the large container we are trying to loot?
        # this is relevant for interpreting a message that something seems to be locked
        self.loot_moniker = None

    def loops_forever(self):
        return True

    def invalidate_inventory(self):
        self.should_do_inventory = True

    def notify_dropped_letter(self, letter):
        """
        This is called just before the drop of a letter from inventory is committed.
        Use this to update the names of large containers on the square.
        """
        item = self.inventory.letter_to_item.get(letter, None)
        if not item:
            print >> self.log, 'ERROR: the dropped letter', letter, 'does not correspond to anything in inventory'
            return
        if item.is_large_container():
            moniker = item.get_moniker()
            if moniker:
                level_square = self.levelmap.level[self.last_cursor_location]
                if moniker in level_square.large_container_names:
                    print >> self.log, 'ERROR: the large container named', moniker, 'has been dropped here before'
                else:
                    print >> self.log, 'dropping a large container named', moniker, 'on the last known player location', self.last_cursor_location
                    level_square.large_container_names.append(moniker)
                    self.lore.get_or_create_item(moniker).untrap_attempt_count = 0

    def process_incoming_message(self, ansi, incoming_ascii_strings, bloated_string):
        """
        Add messages to the message buffer.
        This deals with stuff like notifications of cheese on the floor
        or when multiple messages arrive at once.
        Return values:
            a return value if this is a --More-- message or an (end) message.
            None otherwise (i.e. we need to do something more sophisticated than hit return)
        """
        # read the message bar at the top of the screen
        top_string = incoming_ascii_strings[0]
        # if there is a handful of items on the floor then see if anything is worth picking up
        if 'Things that are here' in bloated_string:
            items = list(gen_things_that_are_here(incoming_ascii_strings, bloated_string))
            if items:
                print >> self.log, 'found a pile of items on the floor:'
                for item in items:
                    print >> self.log, '\t', item
                if self.inventory.should_pick_up_something(items):
                    print >> self.log, 'something seems interesting'
                    self.should_pick_up = True
                else:
                    print >> self.log, 'nothing seems interesting'
        # see if we're supposed to press a key
        # otherwise print all messages since the last real move
        if '--More--' in bloated_string:
            line_index = 0
            while True:
                line = ''.join(x.to_ascii_char() for x in ansi.lines[line_index])
                index = line.find('--More--')
                if index >= 0:
                    message = line[:index]
                    if message:
                        self.messages.append(message)
                    break
                else:
                    self.messages.append(line)
                line_index += 1
            print >> self.log, 'Responding to --More--'
            return '\n'
        else:
            if top_string.strip():
                self.messages.append(top_string)
            for message in self.messages:
                print >> self.message_log, message
        return None

    def process_incoming_special(self, incoming_ascii_strings, bloated_string):
        """
        Process only a few well defined screens.
        All of the screens processed here have been immediately requested the prior bot turn.
        This includes:
            'i'         : single or multi-page showing inventory
            ','         : single or multi-page picking stuff up
            'D'         : single or multi-page dropping stuff
            '#loot in'  : single or multi-page putting stuff in a container
            '#loot out' : single or multi-page getting stuff out of a container
        """
        top_string = incoming_ascii_strings[0]
        # Respond to the inventory screen if we are expecting one.
        if self.should_read_inventory:
            self.should_read_inventory = False
            if 'Not carrying anything' in bloated_string:
                # We are carrying nothing except possibly gold
                print >> self.log, 'the bot has been completely robbed'
                self.inventory = AscInventory(self.lore)
            elif '(end)' in bloated_string:
                # We are carrying a single page of inventory
                self.inventory.add_inventory(incoming_ascii_strings, bloated_string)
                print >> self.log, 'finished reading the single page of inventory'
                print >> self.log, self.inventory
                return '\n'
            else:
                # We are carrying multiple pages of inventory
                pattern = r'\((\d+) of (\d+)\)'
                m = re.search(pattern, bloated_string)
                if m:
                    self.inventory.add_inventory(incoming_ascii_strings, bloated_string)
                    first, last = m.groups()
                    if first == last:
                        print >> self.log, 'finished reading the last page of a multi-page inventory'
                        print >> self.log, self.inventory
                        return '\n'
                    else:
                        print >> self.log, 'finished reading inventory page', first, 'of', last
                        self.should_read_inventory = True
                        return ' '
                else:
                    print >> self.log, 'ERROR: expected an inventory message but none was found'
        # Respond to the pick up screen if we see one or are expecting one.
        if self.should_continue_pick_up or 'Pick up what' in top_string:
            # When we get this prompt it means we are on the first page.
            # Reset the inventory reading flag so that if we end up not picking anything up
            # then we do not check our inventory unnecessarily.
            if 'Pick up what' in top_string:
                print >> self.log, 'we do not need to check our inventory if nothing is selected'
                self.should_do_inventory = False
            # This is set to true if we discover that more pages remain.
            self.should_continue_pick_up = False
            response = get_pick_up_what(incoming_ascii_strings, bloated_string)
            if response:
                unselected_letter_item_pairs, selected_letter_item_pairs = response
                selected_items = [item for (letter, item) in selected_letter_item_pairs]
                if selected_items:
                    print >> self.log, 'something was selected so we need to check our inventory when we are finished'
                    self.invalidate_inventory()
                letters = list(self.inventory.gen_letter_acquisition_selection(unselected_letter_item_pairs, selected_items))
                if letters:
                    letter = letters[0]
                    self.should_continue_pick_up = True
                    print >> self.log, 'selecting letter', letter
                    return letter
                pattern = r'\((\d+) of (\d+)\)'
                m = re.search(pattern, bloated_string)
                if m:
                    first, last = m.groups()
                    if first == last:
                        print >> self.log, 'committing the last page of a multi-page pick up action'
                        return '\n'
                    else:
                        self.should_continue_pick_up = True
                        print >> self.log, 'committing a page of a multi-page pick up action'
                        return ' '
                elif '(end)' in bloated_string:
                    print >> self.log, 'committing the single page pick up action'
                    return '\n'
                else:
                    print >> self.log, 'WARNING: the selection screen for picking up an item was not well terminated'
            else:
                print >> self.log, 'WARNING: tried to pick up something but nothing could be read'
        # Respond to a looting screen if we are expecting one.
        if self.should_continue_looting or 'Take out what?' in top_string:
            # When we get this prompt it means we are on the first page.
            # Reset the inventory reading flag so that if we end up not picking anything up
            # then we do not check our inventory unnecessarily.
            if 'Take out what?' in top_string:
                self.should_do_inventory = False
            # This is set to true if we discover that more pages remain.
            self.should_continue_looting = False
            response = get_pick_up_what(incoming_ascii_strings, bloated_string)
            if response:
                unselected_letter_item_pairs, selected_letter_item_pairs = response
                selected_items = [item for (letter, item) in selected_letter_item_pairs]
                if selected_items:
                    print >> self.log, 'something was selected so we need to check our inventory when we are finished'
                letters = list(self.inventory.gen_letter_acquisition_selection(unselected_letter_item_pairs, selected_items))
                if letters:
                    letter = letters[0]
                    self.should_continue_looting = True
                    self.invalidate_inventory()
                    print >> self.log, 'selecting letter', letter
                    return letter
                pattern = r'\((\d+) of (\d+)\)'
                m = re.search(pattern, bloated_string)
                if m:
                    first, last = m.groups()
                    if first == last:
                        print >> self.log, 'committing the last page of a multi-page looting action'
                        return '\n'
                    else:
                        self.should_continue_looting = True
                        print >> self.log, 'committing a page of a multi-page looting action'
                        return ' '
                elif '(end)' in bloated_string:
                    print >> self.log, 'committing the single page looting action'
                    return '\n'
                else:
                    print >> self.log, 'WARNING: the selection screen for looting was not well terminated'
            else:
                print >> self.log, 'WARNING: tried to take something out of a container but nothing could be read'
        # Respond to the drop screen if we see one or are expecting one.
        if self.should_continue_drop or 'What would you like to drop' in top_string:
            self.should_continue_drop = False
            response = item_selection_helper(incoming_ascii_strings, bloated_string)
            if response:
                unselected_letter_item_pairs, selected_letter_item_pairs = response
                cursor_square = self.levelmap.level[self.last_cursor_location]
                total_drop_letters = set(self.inventory.gen_letter_drop_selection(cursor_square))
                current_page_drop_letters = (total_drop_letters & set(unselected_letter_item_pairs))
                if current_page_drop_letters:
                    letter = current_page_drop_letters[0]
                    self.should_continue_drop = True
                    self.invalidate_inventory()
                    self.notify_dropped_letter(letter)
                    print >> self.log, 'selecting letter', letter
                    return letter
                pattern = r'\((\d+) of (\d+)\)'
                m = re.search(pattern, bloated_string)
                if m:
                    first, last = m.groups()
                    if first == last:
                        print >> self.log, 'committing the last page of a multi-page drop action'
                        return '\n'
                    else:
                        self.should_continue_drop = True
                        print >> self.log, 'committing a page of a multi-page drop action'
                        return ' '
                elif '(end)' in bloated_string:
                    print >> self.log, 'committing the single page drop action'
                    return '\n'
                else:
                    print >> self.log, 'WARNING: the selection screen for dropping an item was not well terminated'
            else:
                print >> self.log, 'WARNING: tried to drop something but nothing could be read'
        # no special messages
        return None

    def process_incoming_request(self, ansi, incoming_ascii_strings, bloated_string):
        """
        Process requests that use only the top line.
        Also process requests for which the cursor is not in the map region.
        """
        top_string = incoming_ascii_strings[0]
        # get a request from the top line of the screen
        print >> self.log, top_string
        # enhance the first available skill
        if 'Pick a skill to enhance' in top_string:
            print >> self.log, 'enhancing a skill'
            return 'a'
        # respond to a loot confirmation request
        if 'loot it?' in top_string:
            print >> self.log, 'got a nethack loot confirmation request'
            if self.loot_moniker:
                lore_item = self.lore.get_existing_item(self.loot_moniker)
                if lore_item:
                    pattern = r'There is (.+) named ([\da-zA-Z]+) here, loot it'
                    m = re.search(pattern, top_string)
                    if m:
                        description, moniker = m.groups()
                        if moniker == self.loot_moniker:
                            lore_item.locked = False
                            if not lore_item.looted:
                                print >> self.log, 'confirmed the request to loot the unlooted container named', self.loot_moniker
                                return 'y'
                            else:
                                print >> self.log, 'declined the request to loot the previously looted container named', self.loot_moniker
                                return 'n'
                        else:
                            print >> self.log, 'WARNING: the expected moniker', self.loot_moniker, 'did not match the observed moniker', moniker
                    else:
                        print >> self.log, 'WARNING: no named container was visible here'
                else:
                    print >> self.log, 'WARNING: no existing lore item could be found for the name', self.loot_moniker
            else:
                print >> self.log, 'WARNING: self.loot_moniker was not present'
        # unlock or pick the lock of a locked large container
        if 'unlock it?' in top_string or 'pick its lock?' in top_string:
            if self.unlock_moniker:
                lore_item = self.lore.get_existing_item(self.unlock_moniker)
                if lore_item:
                    return 'y'
            return 'n'
        # do not put anything into a looted container
        # TODO stash something in the container
        # TODO reset self.loot_moniker to None when looting has finished
        if 'Do you wish to put something in' in top_string:
            if self.loot_moniker:
                lore_item = self.lore.get_existing_item(self.loot_moniker)
                if lore_item:
                    lore_item.looted = True
                    lore_item.locked = False
            return 'n'
        # do not take anything out of a looted container
        # TODO reset self.loot_moniker to None when looting has finished
        if 'Do you want to take something out of' in top_string:
            if self.loot_moniker:
                lore_item = self.lore.get_existing_item(self.loot_moniker)
                if lore_item:
                    lore_item.locked = False
                    if not lore_item.looted:
                        lore_item.looted = True
                        lore_item.locked = False
                        return 'y'
            return 'n'
        # untrap a large container, door, or floor trap
        if 'Check it for traps' in top_string:
            pattern = r'named ([\da-zA-Z]+)'
            m = re.search(pattern, top_string)
            if m:
                moniker = m.groups()[0]
                lore_item = self.lore.get_existing_item(moniker)
                if lore_item:
                    if lore_item.untrap_attempt_count < 3:
                        print >> self.log, 'untrapping large container', moniker
                        lore_item.untrap_attempt_count += 1
                        self.untrap_moniker = moniker
                        return 'y'
                else:
                    print >> self.log, 'the name of the large container to untrap was not found in memory'
                    print >> self.log, 'strange name:', moniker
                    return 'n'
            else:
                print >> self.log, 'the large container to untrap was unnamed'
                return 'n'
        # do not try to remove a spider web
        if 'Remove the web?' in top_string:
            return 'n'
        # do not try to disarm a trap on a chest
        if 'Disarm it?' in top_string:
            if self.untrap_moniker:
                moniker = self.untrap_moniker
                self.untrap_moniker = None
                print >> self.log, 'found a trap on the item named', moniker
                lore_item = self.lore.get_existing_item(moniker)
                lore_item.trapped = True
            else:
                print >> self.log, 'ERROR: we were asked to disarm an unknown item'
            return 'n'
        # begin, continue, or finish naming an object
        # invalidate the inventory when the moniker is committed
        if 'What do you want to name this' in top_string or 'What do you want to name these' in top_string:
            if self.remaining_moniker_letters is None:
                name = self.id_generator.get_next_id()
                if not name:
                    print >> self.log, 'ERROR: no id was generated'
                elif len(name) == 1:
                    self.remaining_moniker_letters = [name]
                else:
                    self.remaining_moniker_letters = list(name)
            if self.remaining_moniker_letters:
                letter = self.remaining_moniker_letters.pop(0)
                return letter
            else:
                self.remaining_moniker_letters = None
                self.invalidate_inventory()
                return '\n'
        # No we do not want to eat carrion.
        if 'eat it?' in top_string:
            return 'n'
        # yes I want to name an individual object
        if 'Name an individual object' in top_string:
            return 'y'
        # We want to eat the item that we have chosen previously.
        # Request that the inventory be checked after eating.
        if 'What do you want to eat' in top_string:
            eating_letter = self.eating_letter
            self.eating_letter = None
            if eating_letter:
                self.invalidate_inventory()
                return eating_letter
            else:
                print >> self.log, 'WARNING: expected an item to eat'
        # We want to throw the item that we have chosen previously
        # in the direction that was chosen previously.
        # Request that the inventory be checked after throwing.
        if 'What do you want to throw' in top_string:
            missile_letter = self.missile_letter
            self.missile_letter = None
            if missile_letter:
                self.invalidate_inventory()
                return missile_letter
            else:
                print >> self.log, 'WARNING: expected an item to throw'
        # Decide which object to name.
        # Request that the inventory be checked after naming.
        if 'What do you want to name?' in top_string:
            letters = tuple(self.inventory.gen_letter_naming_selection())
            if letters:
                self.invalidate_inventory()
                return letters[0]
            else:
                print >> self.log, 'WARNING: expected an item to name'
        # decide what to drop using the single item drop menu
        if 'What do you want to drop' in top_string:
            cursor_square = self.levelmap.level[self.last_cursor_location]
            letters = tuple(self.inventory.gen_letter_drop_selection(cursor_square))
            if len(letters) == 1:
                letter = letters[0]
                self.invalidate_inventory()
                self.notify_dropped_letter(letter)
                return letter
            else:
                print >> self.log, 'WARNING: expected to choose a single item to drop but found %d items: %s' % (len(letters), str(letters))
        # decide what to take off
        if 'What do you want to take off' in top_string:
            take_letter = self.inventory.get_take_letter()
            if take_letter:
                self.invalidate_inventory()
                return take_letter
            return '\x1b'
        # decide what to wear
        if 'What do you want to wear' in top_string:
            wear_letter = self.inventory.get_wear_letter()
            if wear_letter:
                self.invalidate_inventory()
                return wear_letter
            return '\x1b'
        # confirm that we want to unlock the door
        if 'Unlock it?' in top_string:
            return 'y'
        # look for the 'Pick an object.' prompt and respond appropriately
        if 'Pick an object.' in top_string or self.moving_the_selection_cursor:
            return self.pick_an_object(ansi)
        # handle a potential attack on a peaceful monster
        if 'Really attack' in top_string:
            if self.attack_location:
                # get the target square and reset the attack location
                target_square = self.levelmap.level[self.attack_location]
                self.attack_location = None
                monster = target_square.monster
                if monster:
                    if monster.is_peaceful():
                        # if it is already known to be peaceful then we must be attacking it for a reason
                        print >> self.log, 'deliberately attacking a peaceful monster'
                        return 'y'
                    elif self.levelmap.level_branch == LEVEL_BRANCH_SOKOBAN and self.levelmap.sokoban_queue:
                        # if we are in sokoban and have not finished the puzzle then attack a peaceful monster so it does not get in the way
                        print >> self.log, 'deliberately attacking a peaceful monster because we are not finished with this sokoban puzzle yet'
                        return 'y'
                    else:
                        # if it is not known to be peaceful then mark it as peaceful and leave it alone for now
                        monster.set_peaceful()
                        print >> self.log, 'refraining from attacking a peaceful monster'
                        return 'n'
                else:
                    print >> self.log, 'ERROR: we are attacking or moving onto a square that unexpectedly has a monster, and it is peaceful'
            else:
                print >> self.log, 'ERROR: we are unexpectedly attacking or moving onto a monster, and it is peaceful'
        # apply an item for unlocking a door for example
        if 'What do you want to use or apply' in top_string:
            if self.apply_letter:
                letter = self.apply_letter
                self.apply_letter = None
                return letter
            else:
                print >> self.log, 'ERROR: no item was selected for application'
        # do something in some direction
        if 'In what direction?' in top_string:
            if self.unidentified_adjacent_trap_direction:
                # identify an adjacent trap
                direction = self.unidentified_adjacent_trap_direction
                self.unidentified_adjacent_trap_direction = None
                return direction
            elif self.last_door_opening_direction:
                # open, kick, pick, or unlock a door
                direction = self.last_door_opening_direction
                self.last_door_opening_direction = None
                return direction
            elif self.missile_direction:
                # throw something and look at the inventory afterwards
                # this is for throwing food to tame pets,
                # for throwing gems to teleport unicorns,
                # and for throwing weapons at monsters behind boulders in sokoban.
                direction = self.missile_direction
                self.missile_direction = None
                self.missile_letter = None
                self.invalidate_inventory()
                return direction
            elif self.untrap_direction:
                # untrap a large container, door, or floor trap.
                direction = self.untrap_direction
                self.untrap_direction = None
                return direction
            elif self.container_unlocking_direction:
                # unlock a container
                direction = self.container_unlocking_direction
                self.container_unlocking_direction
                return direction
        # use the default value for whatever unknown request is putting
        # the cursor outside the map region.
        if self.levelmap:
            loc = (ansi.row, ansi.col)
            if loc not in self.levelmap.level:
                print >> self.log, 'unknown request such that the cursor is outside the map region'
                return '\n'
        # if we did not find anything useful to do then return None
        return None

    def pick_an_object(self, ansi):
        """
        Generate a response to the 'Pick an object.' prompt.
        This involves pathing the semicolon to a target.
        The target could be an unknown trap or a square that is causing the bot to be stuck.
        """
        # TODO do not create a new ObjectPicker for each sub-move
        self.moving_the_selection_cursor = True
        # first determine the set of interesting locations
        if self.stuck_target_location:
            # we are trying to figure out why we are stuck
            interesting_set = set([self.stuck_target_location])
        else:
            # we are trying to figure out the identity of some traps
            interesting_set = set(self.levelmap.gen_unidentified_trap_locations(ansi))
        # make sure we have an interesting set
        if not interesting_set:
            print >> self.log, 'there was nothing interesting for the "Pick an object." prompt'
            return '\x1b'
        # note the location of the cursor
        current_location = (ansi.row, ansi.col)
        # if we are at an interesting location then remember it and press the semicolon
        if current_location in interesting_set:
            self.pick_an_object_location = current_location
            self.moving_the_selection_cursor = False
            print >> self.log, 'selecting the target square'
            return ';'
        # otherwise return the command that goes towards an interesting object
        location_to_ascii = {}
        for row, line in enumerate(ansi.lines):
            for col, ansi_square in enumerate(line):
                location_to_ascii[(row, col)] = ansi_square.char
        picker = ObjectPicker(location_to_ascii, interesting_set)
        result = picker.get_best_move(current_location)
        if not result:
            print >> self.log, 'the picker thinks we are already at the location'
            assert False
        else:
            print >> self.log, 'moving the selection cursor towards the target square with this command:', result
            return result

    def detect_sokoban_level(self, ansi):
        """
        Look through the eight or so levels of sokoban that are hardcoded in AscSokoban.
        If any have an identical wall pattern to the current level then return the name of the level.
        If no sokoban level was detected then return None.
        For detection purposes any ascii '-' or '|' is a wall.
        The match must be bidirectional.
        """
        # Define wall ascii symbols for the purpose of sokoban level detection.
        sokoban_wall_characters = ('-', '|')
        # Get the set of wall locations on the observed ansi map.
        raw_wall_locations = set()
        for loc in self.levelmap.level:
            row, col = loc
            ansi_square = ansi.lines[row][col]
            if ansi_square.char in sokoban_wall_characters:
                raw_wall_locations.add(loc)
        # If no walls were observed then the level was not detected.
        # TODO what about engulfing?
        if not raw_wall_locations:
            print >> self.log, 'no matching sokoban level was found (no walls were seen)'
            return None
        # Get the bounding wall rectangle of the observed ansi map on the screen.
        row_min, col_min, row_max, col_max = get_bounding_coordinates(raw_wall_locations)
        # Spacially translate wall locations to the upper left.
        translated_wall_locations = set()
        for loc in raw_wall_locations:
            row, col = loc
            translated_location = (row - row_min, col - col_min)
            translated_wall_locations.add(translated_location)
        # See if the wall pattern matches that of a hard coded Sokoban level.
        matching_level_names = []
        for level_string, level_name in AscSokoban.all_level_strings_and_names:
            level = AscSokoban.sokoban_string_to_map(level_string)
            sokoban_wall_locations = set(loc for loc, c in level.items() if c in sokoban_wall_characters)
            if sokoban_wall_locations == translated_wall_locations:
                matching_level_names.append(level_name)
        # If we got no matches or more than one match then fail.
        if not matching_level_names:
            print >> self.log, 'no matching sokoban level was found'
            return None
        elif len(matching_level_names) > 1:
            print >> self.log, 'ERROR: multiple matching sokoban levels were found'
            return None
        else:
            level_name = matching_level_names[0]
            print >> self.log, 'found a unique matching sokoban level:', level_name
            return level_name

    def process_dlvl_change(self, new_ansi, old_dlvl, new_dlvl, old_cursor_location, new_cursor_location):
        """
        """
        # Was the dlvl change degenerate?
        if old_dlvl is None:
            print >> self.log, 'descending to the starting location'
            return
        # Decide if the level change was a descent or an ascent.
        if old_dlvl < new_dlvl:
            change_string = 'descent'
        else:
            change_string = 'ascent'
        # See if the new level matches a sokoban level.
        sokoban_name = self.detect_sokoban_level(new_ansi)
        # Remove the player region from the old level.
        old_player_region = self.levelmap.get_player_region()
        self.levelmap.regions = [r for r in self.levelmap.regions if r is not old_player_region]
        # Remove links from the old level that include the player region.
        self.levelmap.region_links = [link for link in self.levelmap.region_links if old_player_region not in link.region_pair]
        # Can we find a linking region from the old level?
        self.linking_region = None
        if self.expecting_level_change:
            self.expecting_level_change = False
            if abs(old_dlvl - new_dlvl) == 1:
                matching_regions = []
                for region in self.levelmap.regions:
                    if region.location == old_cursor_location:
                        if old_dlvl < new_dlvl:
                            if region.region_type == REGION_DOWN:
                                matching_regions.append(region)
                        else:
                            if region.region_type == REGION_UP:
                                matching_regions.append(region)
                if matching_regions:
                    if len(matching_regions) > 1:
                        print >> self.log, 'ERROR: %d potentially linking regions' % len(matching_regions)
                    self.linking_region = matching_regions[0]
        # If the level change was controlled and known, then update the level.
        taboo_levels = []
        if self.linking_region:
            print >> self.log, 'presumably controlled %s from dlvl %d to dlvl %d' % (change_string, old_dlvl, new_dlvl)
            if self.linking_region.target_region:
                print >> self.log, 'the target region was known:'
                print >> self.log, self.linking_region.target_region
                print >> self.log, 'loading the target level'
                self.levelmap = self.linking_region.target_region.level
                return
            else:
                print >> self.log, 'the target region was unknown'
                # Exclude levels that are already accessible from the linking region.
                taboo_regions = self.linking_region.get_connected_regions()
                taboo_levels = [region.level for region in taboo_regions]
        else:
            print >> self.log, 'uncontrolled %s from dlvl %d to dlvl %d' % (change_string, old_dlvl, new_dlvl)
        print >> self.log, 'looking for a matching level'
        # If we are descending from the mines branch then stay in the mines branch.
        # If we are descending in an uncontrolled manner from the doom branch then stay in the doom branch.
        forced_branch = None
        fork_level = self.levelmap.dungeon.get_doom_fork_level()
        if old_dlvl < new_dlvl:
            # Descent from a mines branch level always goes to a mines branch level.
            if self.levelmap.level_branch == LEVEL_BRANCH_MINES:
                forced_branch = LEVEL_BRANCH_MINES
            # Uncontrolled descent from a doom branch level always goes to a doom branch level.
            if not self.linking_region:
                if self.levelmap.level_branch == LEVEL_BRANCH_DOOM:
                    forced_branch = LEVEL_BRANCH_DOOM
            # Controlled descent from a doom branch level deeper than the fork level always goes to a doom branch level.
            if fork_level:
                if old_dlvl > fork_level.level_dlvl:
                    if self.levelmap.level_branch == LEVEL_BRANCH_DOOM:
                        forced_branch = LEVEL_BRANCH_DOOM
        # If we are ascending to a level deeper than the doom fork then stay in the same branch.
        if fork_level:
            if new_dlvl < old_dlvl:
                if new_dlvl > fork_level.level_dlvl:
                    if self.levelmap.level_branch == LEVEL_BRANCH_MINES:
                        forced_branch = LEVEL_BRANCH_MINES
                    if self.levelmap.level_branch == LEVEL_BRANCH_DOOM:
                        forced_branch = LEVEL_BRANCH_DOOM
        # If we are at a named sokoban level then the forced branch should be sokoban
        if sokoban_name:
            print >> self.log, 'forcing a sokoban branch'
            forced_branch = LEVEL_BRANCH_SOKOBAN
        # Look for existing matching levels.
        matching_levels = []
        for level in self.dungeon.levels:
            if level.level_dlvl != new_dlvl:
                # if the target level is the wrong dlvl then we know it cannot be a match
                continue
            if forced_branch == LEVEL_BRANCH_SOKOBAN:
                # if we know the target is a sokoban level then do not accept levels with an uncertain branch
                if level.level_branch != LEVEL_BRANCH_SOKOBAN:
                    continue
            elif forced_branch is not None:
                # if the target branch is forced but is not a sokoban level then accept levels with an uncertain branch
                if level.level_branch not in (forced_branch, LEVEL_BRANCH_UNKNOWN):
                    continue
            matching_levels.append(level)
        print >> self.log, 'found %d raw matching levels' % len(matching_levels)
        # Exclude taboo levels.
        if taboo_levels:
            new_matching_levels = [level for level in matching_levels if level not in taboo_levels]
            if len(new_matching_levels) < len(matching_levels):
                print >> self.log, 'removed %d taboo levels from the list of matching levels' % (len(matching_levels) - len(new_matching_levels))
                matching_levels = new_matching_levels
            else:
                print >> self.log, 'taboo levels exist but none was found in the list of matching levels'
        else:
            print >> self.log, 'no taboo levels were available'
        # Load the matching level or create a new level
        if len(matching_levels) == 1:
            print >> self.log, 'a unique matching level was found and loaded'
            self.levelmap = matching_levels[0]
        elif len(matching_levels) > 1:
            print >> self.log, 'WARNING: multiple matching levels were found and an arbitrary one was loaded'
            self.levelmap = matching_levels[0]
        else:
            print >> self.log, 'no matching level was found so one was created and loaded'
            newlevel = LevelMap(self.dungeon)
            newlevel.level_dlvl = new_dlvl
            if forced_branch:
                newlevel.level_branch = forced_branch
            if forced_branch == LEVEL_BRANCH_SOKOBAN:
                # initialize the sokoban level
                print >> self.log, 'initializing a sokoban level'
                newlevel.init_sokoban(new_ansi, sokoban_name)
            self.levelmap = newlevel
            self.dungeon.levels.append(newlevel)


    def process_incoming_status(self, ansi):
        """
        This function processes controlled and uncontrolled dlvl changes.
        This is where new LevelMap objects are created.
        """
        # Initialize the top level.
        if not self.levelmap:
            self.levelmap = LevelMap(self.dungeon)
            self.levelmap.level_dlvl = 1
            self.levelmap.level_branch = LEVEL_BRANCH_DOOM
            self.levelmap.level_special = LEVEL_SPECIAL_TOP
            self.levelmap.exploration_status = EXP_UNEXPLORED
            self.dungeon.levels.append(self.levelmap)
        cursor_location = (ansi.row, ansi.col)
        status_string = ''.join(x.to_ascii_char() for x in ansi.lines[23])
        newstatus = BotStatus()
        if newstatus.scrape(status_string):
            # log blinding and unblinding events
            if newstatus.blind and (not self.status.blind):
                print >> self.log, 'blinded'
            if (not newstatus.blind) and self.status.blind:
                print >> self.log, 'unblinded'
            # log hunger level changes
            if newstatus.hunger_level > self.status.hunger_level:
                print >> self.log, 'hunger level increased'
            elif newstatus.hunger_level < self.status.hunger_level:
                print >> self.log, 'hunger level decreased'
            # log polymorph events and have them trigger an inventory check
            if newstatus.polymorphed and (not self.status.polymorphed):
                print >> self.log, 'polymorphed'
                self.invalidate_inventory()
            if (not newstatus.polymorphed) and self.status.polymorphed:
                print >> self.log, 'returned to normal form'
                self.invalidate_inventory()
            # if we just got weak from hunger then pray
            if newstatus.hunger_level >= HUNGER_LEVEL_WEAK and self.status.hunger_level < HUNGER_LEVEL_WEAK:
                print >> self.log, 'we just got weak, so praying for food'
                self.should_pray = True
            # process a dlvl change
            if newstatus.dlvl != self.status.dlvl:
                self.process_dlvl_change(ansi, self.status.dlvl, newstatus.dlvl, self.last_cursor_location, cursor_location)
            # update the level time
            if self.levelmap.level_time is None:
                self.levelmap.level_time = 0
            if not self.status.turns:
                self.levelmap.level_time += newstatus.turns
            else:
                self.levelmap.level_time += (newstatus.turns - self.status.turns)
            # do not forget to update the status
            self.status = newstatus
        else:
            print >> self.log, 'this status string could not be processed:', status_string

    def create_region(self, region_type, cursor_location):
        """
        The created region will be refined when the level is updated.
        For example, its branch and type will be defined.
        """
        # create a region
        region = Region()
        region.level = self.levelmap
        region.location = cursor_location
        region.region_type = region_type
        self.levelmap.regions.append(region)
        # possibly link the region
        if self.linking_region:
            region.target_region = self.linking_region
            self.linking_region.target_region = region
            print >> self.log, 'created region:', str(region)
            print >> self.log, 'linking with region:', str(self.linking_region)
        else:
            print >> self.log, 'created unlinked region:', str(region)
        self.linking_region = None

    def read_post_status_messages(self, ansi):
        """
        Read messages that should be processed after processing the status.
        """
        # concatenate all of the messages
        s = ''.join(self.messages)
        # get the cursor location and the corresponding square
        cursor_location = (ansi.row, ansi.col)
        cursor_square = self.levelmap.level[cursor_location]
        # if we just finished searching then mark the square as having
        # been searched for some number of turns
        if self.search_location:
            if cursor_location != self.search_location:
                print >> self.log, 'we stopped searching on a different square than we started'
            else:
                search_turns = self.status.turns - self.search_turn_begin
                self.levelmap.level[self.search_location].search_count_from += search_turns
                for neighbor_location in self.levelmap.cached_neighbor_locations[self.search_location]:
                    self.levelmap.level[neighbor_location].search_count_to += search_turns
            self.search_location = None
            self.search_turn_begin = None
        # we succeeded in unlocking a large container
        if self.unlock_moniker:
            lore_item = self.lore.get_existing_item(self.unlock_moniker)
            if lore_item:
                container_unlocking_messages = (
                        'You succeed in unlocking the box',
                        'You succeed in unlocking the chest',
                        'You succeed in picking the lock',
                        )
                for message in container_unlocking_messages:
                    if message in s:
                        lore_item.locked = False
                self.unlock_moniker = None
        # we tried to loot a large container but it was locked
        if 'Hmmm, it seems to be locked' in s:
            if self.loot_moniker:
                lore_item = self.lore.get_existing_item(self.loot_moniker)
                if lore_item:
                    print >> self.log, 'the large container assumed to be named', self.loot_moniker, 'was discovered to be locked'
                    lore_item.locked = True
                else:
                    print >> self.log, 'WARNING: the assumed name of a container that seems to be locked was unrecognized'
                    print >> self.log, 'the assumed name was', self.loot_moniker
                self.loot_moniker = None
            else:
                print >> self.log, 'WARNING: something seems to be locked but we do not know what it is'
        # see if moving the boulder failed because there is a monster behind it
        boulder_failure_messages = (
                'You hear a monster behind the boulder',
                "Perhaps that's why you cannot move it",
                'You try to move the boulder, but in vain'
                )
        for message in boulder_failure_messages:
            if message in s:
                print >> self.log, 'boulder failure:', message
                self.boulder_failure = True
        # see if we are turning to stone
        if 'You are slowing down' in s or 'Your limbs are stiffening' in s:
            print >> self.log, 'turning to stone'
            self.turning_to_stone = True
        # see if we have become lycanthropic
        if 'You feel feverish' in s:
            print >> self.log, 'afflicted with lycanthropy'
            self.lycanthropic = True
        # see if we have been cured of lycanthropy
        if 'You feel purified' in s:
            print >> self.log, 'cured of lycanthropy'
            self.lycanthropic = False
        # if we get any of these messages then check our inventory
        inventory_change_messages = (
                ' stole ',
                ' steals ',
                'You finish taking off',
                'You finish your dressing',
                'You are now wearing',
                'You were wearing',
                'You find you must drop your weapon',
                'You break out of your armor',
                'You drop'
                )
        for message in inventory_change_messages:
            if message in s:
                print >> self.log, 'we received a message that indicates our inventory status has changed'
                self.invalidate_inventory()
        # if our light source was temporarily extinguished then refresh the inventory to try to relight it.
        temporary_extinguish_messages = (
                'extinguished',
                'goes out'
                )
        for temporary_extinguish_message in temporary_extinguish_messages:
            if temporary_extinguish_message in s:
                print >> self.log, 'a light source has been temporarily extinguished'
                self.invalidate_inventory()
        # if our light source has run out then mark it as empty and check inventory to refresh lit state
        permanent_extinguish_messages = (
            'lantern has run out of power',
            'lamp has run out of power',
            'has gone out',
            'is consumed!',
            'are consumed!',
            'has no oil'
            )
        for permanent_extinguish_message in permanent_extinguish_messages:
            light_source_moniker = self.inventory.get_light_source_moniker()
            if permanent_extinguish_message in s:
                print >> self.log, 'a light source was permanently extinguished'
                self.invalidate_inventory()
                if light_source_moniker:
                    print >> self.log, 'the light source was found in inventory'
                    self.lore.get_or_create_item(light_source_moniker).empty = True
                else:
                    print >> self.log, 'the light source was not found in inventory so maybe it was a candle'
        # look for big piles of stuff on the floor
        if 'There are several objects here' in s or 'There are many objects here' in s:
            print >> self.log, 'found a big opaque pile of stuff on the ground so try picking something up'
            self.should_pick_up = True
        # look for interesting stuff on the floor
        if 'You see here' in s:
            items = list(gen_floor_items(s))
            if items:
                if len(items) > 1:
                    print >> self.log, 'WARNING: more than one item was found on the floor using the single item format:'
                elif len(items) == 1:
                    print >> self.log, 'found an item on the floor:'
                for item in items:
                    print >> self.log, '\t', item
                if self.inventory.should_pick_up_something(items):
                    print >> self.log, 'we want to pick up something'
                    self.should_pick_up = True
                else:
                    print >> self.log, 'nothing seems worth picking up'
            else:
                print >> self.log, 'WARNING: nothing on the floor was recognized as an item'
        # enhance a skill
        # this takes no game turns
        if 'more confident' in s:
            self.should_enhance = True
        # assume that graffiti means we are closed for inventory
        engraving_messages = (
                "Something is written here in the dust.",
                "Something is engraved here on the floor.",
                "Some text has been burned here in the floor.",
                "There's graffiti here on the floor.",
                "Something is written in a very strange way."
                )
        for message in engraving_messages:
            if message in s:
                print >> self.log, 'detected graffiti at this location:', cursor_location
                self.levelmap.notify_graffiti(cursor_location)
                break
        # check for stairs up
        if 'There is a staircase up here.' in s:
            if cursor_square.hard == HM_UP_UNCONFIRMED:
                print >> self.log, 'confirmed an up staircase at', cursor_location
            elif cursor_square.hard != HM_UP_CONFIRMED:
                print >> self.log, 'discovered and confirmed an up staircase at', cursor_location
            cursor_square.hard = HM_UP_CONFIRMED
            if cursor_location not in [r.location for r in self.levelmap.regions]:
                print >> self.log, 'found an up staircase that is not affiliated with a region on this level'
                self.create_region(REGION_UP, cursor_location)
        # check for stairs down
        if 'There is a staircase down here.' in s:
            if cursor_square.hard == HM_DOWN_UNCONFIRMED:
                print >> self.log, 'confirmed a down staircase at', cursor_location
            elif cursor_square.hard != HM_DOWN_CONFIRMED:
                print >> self.log, 'discovered and confirmed a down staircase at', cursor_location
            cursor_square.hard = HM_DOWN_CONFIRMED
            if cursor_location not in [r.location for r in self.levelmap.regions]:
                print >> self.log, 'found a down staircase that is not affilitated with a region on this level'
                self.create_region(REGION_DOWN, cursor_location)
        # if we looked at the ground and saw no staircase then there must not be one there.
        # TODO add dungeon features to check for with a ground check (e.g. altar, sink).
        if self.ground_check:
            if not self.linking_region:
                print >> self.log, 'WARNING: ground check without a linking region'
            self.ground_check = False
            if 'There is a staircase' not in s:
                print >> self.log, 'failed to find a staircase that links the regions'
                self.linking_region = None
                cursor_square.hard = HM_OCCUPIABLE
        # identify an adjacent trap
        if self.unidentified_adjacent_trap_location:
            pattern = r"That is an? (.*?)\."
            m = re.search(pattern, s)
            if m:
                trapname = m.groups()[0]
                self.levelmap.identify_trap(self.unidentified_adjacent_trap_location, trapname)
                print >> self.log, 'got the adjacent trap name: {%s}' % trapname
            else:
                print >> self.log, 'did not get the adjacent trap name'
            self.unidentified_adjacent_trap_location = None
        # identify a non-adjacent trap or something that is blocking movement
        if self.pick_an_object_location:
            if self.stuck_target_location:
                # look at the square that is inexplicably blocking movement
                is_embedded = False
                embedded_messages = (
                    'embedded in stone',
                    'embedded in a door',
                    'embedded in a wall'
                    )
                for message in embedded_messages:
                    if message in s:
                        is_embedded = True
                if is_embedded:
                    print >> self.log, 'the bot is stuck trying to get something that is embedded in a dungeon feature'
                    self.levelmap.identify_embedded(ansi, self.stuck_target_location)
                    self.stuck_target_location = None
                    self.stuck_target_direction = None
                else:
                    print >> self.log, 'try opening the square that caused the bot to get stuck'
                    self.should_open_stuck_target = True
            else:
                # look for a remote trap
                pattern = r'a trap \((.*)\)'
                m = re.search(pattern, s)
                if m:
                    trapname = m.groups()[0]
                    self.levelmap.identify_trap(self.pick_an_object_location, trapname)
                    print >> self.log, 'got the non-adjacent trap name: {%s}' % trapname
                else:
                    print >> self.log, 'did not get the non-adjacent trap name'
            self.pick_an_object_location = None
        # enumerate store types
        store_names = (
                'general store',
                'used armor dealership',
                'second-hand bookstore',
                'liquor emporium',
                'antique weapons outlet',
                'delicatessen',
                'jewelers',
                'quality apparel and accessories',
                'hardware store',
                'rare books',
                'lighting store'
                )
        # did we step on a shop door?
        if 'Welcome to' in s:
            for store_name in store_names:
                if store_name in s:
                    debugging_message = self.levelmap.notify_store_door(self.last_cursor_location, cursor_location)
                    print >> self.log, debugging_message
                    print >> self.log, ansi.to_ansi_string()
        # did we step on an open door?
        if 'There is an open door here' in s:
            self.levelmap.level[cursor_location].hard = HM_OPEN
        # did we step on a broken door?
        if 'There is a broken door here' in s:
            self.levelmap.level[cursor_location].hard = HM_OCCUPIABLE
        # did we affect the status of a door?
        if self.last_door_opening_location:
            current_state = self.levelmap.level[self.last_door_opening_location].hard
            next_state = None
            # see which normal effect is applicable
            # TODO give an error message if the current state was not expected.
            if 'The door resists!' in s:
                #if current_state in (HM_CLOSED, HM_UNLOCKED):
                next_state = HM_UNLOCKED
            elif 'This door is locked.' in s:
                #if current_state in (HM_CLOSED, HM_LOCKED):
                next_state = HM_LOCKED
            #elif 'You see no door there.' in s:
                #if current_state == HM_CLOSED:
                    #next_state = HM_OCCUPIABLE
            elif 'This door is broken' in s:
                #if current_state == HM_CLOSED:
                next_state = HM_FLOOR
            elif 'The door opens.' in s:
                #if current_state in (HM_CLOSED, HM_UNLOCKED):
                next_state = HM_OPEN
            elif 'This door is already open.' in s:
                #if current_state in (HM_CLOSED, HM_LOCKED, HM_UNLOCKED):
                next_state = HM_OPEN
            elif 'As you kick the door, it crashes open!' in s:
                #if current_state in (HM_CLOSED, HM_LOCKED):
                next_state = HM_FLOOR
            elif 'As you kick the door, it shatters to pieces!' in s:
                #if current_state in (HM_CLOSED, HM_LOCKED):
                next_state = HM_FLOOR
            elif 'You succeed in picking the lock' in s:
                #if current_state == HM_LOCKED:
                next_state = HM_UNLOCKED
            elif 'You succeed in unlocking the door' in s:
                #if current_state == HM_LOCKED:
                next_state = HM_UNLOCKED
            elif 'This doorway has no door' in s:
                next_state = HM_FLOOR
            # see if the door was trapped and exploded
            if 'The door was booby-trapped' in s:
                next_state = HM_FLOOR
            # update the door state
            if next_state is not None:
                self.levelmap.level[self.last_door_opening_location].hard = next_state
                self.last_door_opening_location = None
        # it is important to know whether or not we are in a pit
        # because you cannot reach out of it to open a door
        if 'You fall into a pit' in s:
            trapname = 'pit'
            if 'You land on a set of sharp iron spikes!' in s:
                trapname = 'spiked pit'
            self.trapped_pit = True
            self.levelmap.identify_trap(cursor_location, trapname)
        if 'You crawl to the edge of the pit' in s:
            self.trapped_pit = False
        # did we step in a trap?
        # some of these are important to recognize because they leave cheese
        # that covers the trap.
        # TODO this list is incomplete
        # The trap names are from drawing.c in the nethack source,
        # and are the names you get by querying the trap remotely.
        trap_descriptions = (
            ('An arrow shoots out at you', 'arrow trap'),
            ('A little dart shoots out at you', 'dart trap'),
            ('A trap door in the ceiling opens and a rock falls on your head!', 'falling rock trap'),
            ('You escape a falling rock trap', 'falling rock trap'),
            ('There is a falling rock trap here', 'falling rock trap'),
            ('A board beneath you squeaks loudly', 'squeaky board'),
            ('A bear trap closes on your foot', 'bear trap'),
            #('', 'land mine'),
            #('', 'rolling boulder trap'),
            ('You are enveloped in a cloud of gas', 'sleeping gas trap'),
            ('A cloud of gas puts you to sleep', 'sleeping gas trap'),
            ('A gush of water hits you', 'rust trap'),
            #('', 'fire trap'),
            #('', 'pit'),
            #('', 'spiked pit'),
            #('', 'hole'),
            #('', 'trap door'),
            #('', 'teleportation trap'),
            #('', 'level teleporter'),
            #('', 'magic portal'),
            ('You stumble into a spider web', 'web'),
            ('You are caught in a magical explosion', 'magic trap'),
            ('You are momentarily blinded by a flash of light', 'magic trap'),
            ('Your pack shakes violently', 'magic trap'),
            ('You feel your magical energy drain away', 'anti-magic trap'),
            ('You step onto a polymorph trap', 'polymorph trap')
            )
        for description, trapname in trap_descriptions:
            if description in s:
                self.levelmap.identify_trap(cursor_location, trapname)
        # Some traps leave some cheese on the ground when they activate.
        # If this happens then update the item history of the square and look at the ground.
        if 'An arrow shoots out at you' in s or 'A little dart shoots out at you' in s:
            self.levelmap.add_missile(cursor_location)
            self.levelmap.level[cursor_location].item.set_explored()
            self.should_look_at_ground = True
        if 'A trap door in the ceiling opens and a rock falls on your head!' in s:
            self.levelmap.add_rock(cursor_location)
            self.levelmap.level[cursor_location].item.set_explored()
            self.should_look_at_ground = True


    def process_incoming_misc(self, ansi):
        """
        The cursor should be at the player character.
        Do a normal move.
        @param ansi: visual screen representation, including cursor location
        """
        # get the cursor location and the corresponding square
        cursor_location = (ansi.row, ansi.col)
        cursor_square = self.levelmap.level[cursor_location]
        # consider linking existing regions
        if self.linking_region:
            # do we know of a region at the current square?
            square_region = None
            for region in self.levelmap.regions:
                if region.location == cursor_location:
                    square_region = region
            # if so link it
            # otherwise look at the ground
            if square_region:
                print >> self.log, 'linking existing regions'
                self.linking_region.target_region = square_region
                square_region.target_region = self.linking_region
                self.linking_region = None
            else:
                if not self.status.blind:
                    self.ground_check = True
                    return ':'
        # if we tried to push a boulder and ended up on the expected square then it was a success
        # otherwise it was a failure and we should have gotten a message anyway
        if self.last_sokoban_push_target:
            if cursor_location == self.last_sokoban_push_target:
                print >> self.log, 'we appear to have successfully pushed the boulder'
                # Remove the boulder state from the cursor location.
                current_square = self.levelmap.level[cursor_location]
                current_square.boulder = False
                # Modify the square where the boulder landed.
                drow, dcol = self.last_sokoban_push_delta
                row, col = cursor_location
                boulder_target = (row + drow, col + dcol)
                boulder_target_square = self.levelmap.level[boulder_target]
                if boulder_target_square.trap not in (TRAP_NONE, TRAP_UNKNOWN):
                    # If we pushed the boulder into a hole or a pit then fill the hole or pit.
                    print >> self.log, 'the boulder filled a hole or a pit'
                    boulder_target_square.trap = TRAP_NONE
                else:
                    # If we did not push the boulder into a hole or a pit then update the new boulder location.
                    print >> self.log, 'the boulder was pushed across the floor'
                    boulder_target_square.boulder = True
                # Reset the internal boulder pushing state.
                self.boulder_failure = False
                self.last_sokoban_push_delta = None
                self.last_sokoban_push_target = None
                # Go to the next position in the boulder pushing sequence.
                self.levelmap.sokoban_queue.pop(0)
            else:
                print >> self.log, 'after having tried to push the boulder we did not end up where we expected'
                self.boulder_failure = True
        # this is set when the bot is initialized
        # and when the bot sees a message that makes it suspect that the inventory has changed
        if self.should_do_inventory:
            self.should_do_inventory = False
            self.should_read_inventory = True
            # prepare to read the inventory
            self.inventory = AscInventory(self.lore)
            return 'i'
        # if we should look at the ground and we are not blind then look at the ground
        if self.should_look_at_ground and not self.status.blind:
            self.should_look_at_ground = False
            self.ground_check = True
            return ':'
        # this is set when the messages are read
        if self.should_enhance:
            self.should_enhance = False
            return ascii_to_meta('e')
        # eat a lizard corpse if we are turning to stone
        # do not care about hunger level at this point
        if self.turning_to_stone:
            for letter, item in self.inventory.letter_to_item.items():
                self.turning_to_stone = False
                if item.includes_one_of(['lizard corpse']):
                    print >> self.log, 'eating a lizard corpse to prevent stoning'
                    self.eating_letter = letter
                    return 'e'
            print >> self.log, 'no lizard corpse is available to keep us from turning to stone'
        # this is set when the messages are read
        if self.should_pray:
            self.should_pray = False
            self.consumed_nutrition = 0
            return ascii_to_meta('p')
        # this is set when the messages are read
        if self.should_quit:
            self.should_quit = False
            return ascii_to_meta('q')
        # respond to engulfing
        engulfing_pattern = r'/-\||\-/'
        offsets = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
        arr = []
        for drow, dcol in offsets:
            nloc = (ansi.row + drow, ansi.col + dcol)
            if self.levelmap.is_inbounds(nloc):
                arr.append(ansi.lines[ansi.row + drow][ansi.col + dcol].char)
        detected_pattern = ''.join(arr)
        if detected_pattern == engulfing_pattern:
            print >> self.log, 'detected engulfing so moving in an arbitrary direction to attack'
            return 'l'
        # read the map accounting for blindness if necessary
        self.levelmap.process_incoming(ansi, self.status)
        # look for non-adjacent (remote) trap symbols and identify them if they are unidentified
        remote_trap_locations = list(self.levelmap.gen_unidentified_remote_trap_locations(ansi))
        if remote_trap_locations:
            print >> self.log, 'found unidentified traps at these remote locations:', str(remote_trap_locations)
            return ';'
        # now consider moves that require a direction
        movement = (
                (-1, 0, 'k'),
                (1, 0, 'j'),
                (0, -1, 'h'),
                (0, 1, 'l'),
                (-1, -1, 'y'),
                (-1, 1, 'u'),
                (1, -1, 'b'),
                (1, 1, 'n')
                )
        # find the neighboring squares and corresponding commands
        # that represent locations within the map bounds
        nloc_and_command = []
        for drow, dcol, command in movement:
            nloc = (ansi.row + drow, ansi.col + dcol)
            if self.levelmap.is_inbounds(nloc):
                nloc_and_command.append((nloc, command))
        # look for the stairs on the first turn
        # this takes no game turns
        if not self.checked_first_square:
            if not self.status.blind:
                f = open('initial-screenshot.ansi', 'wb')
                f.write(ansi.to_ansi_string())
                f.close()
                self.checked_first_square = True
                self.ground_check = True
                return ':'
        # look for an unidentified trap next to us
        # this takes no game turns
        for nloc, command in nloc_and_command:
            row, col = nloc
            ansi_neighbor = ansi.lines[row][col]
            level_neighbor = self.levelmap.level[nloc]
            if ansi_neighbor.char == '^':
                if level_neighbor.trap == TRAP_UNKNOWN:
                    self.unidentified_adjacent_trap_location = nloc
                    self.unidentified_adjacent_trap_direction = command
                    return '^'
        # name an item in inventory
        # this takes no game turns
        letters = tuple(self.inventory.gen_letter_naming_selection())
        if letters:
            return ascii_to_meta('n')
        # try to throw a gem at an adjacent unicorn
        # do not try to throw a gem if hallu
        if not self.status.hallu:
            for nloc, command in nloc_and_command:
                monster = self.levelmap.level[nloc].monster
                if monster:
                    if monster.is_wild_unicorn():
                        for letter, item in self.inventory.letter_to_item.items():
                            if item.is_gem():
                                self.missile_letter = letter
                                self.missile_direction = command
                                return 't'
        # try to tame an adjacent animal
        # do not tame an animal in sokoban regardless of whether we have finished the puzzle
        # do not try to tame if hallu
        if not self.status.hallu:
            if self.levelmap.level_branch != LEVEL_BRANCH_SOKOBAN:
                for nloc, command in nloc_and_command:
                    monster = self.levelmap.level[nloc].monster
                    if monster:
                        letter = None
                        if monster.is_wild_carnivore():
                            letter = self.inventory.get_carnivore_letter()
                        elif monster.is_wild_horse():
                            letter = self.inventory.get_herbivore_letter()
                        if letter:
                            self.missile_letter = letter
                            self.missile_direction = command
                            return 't'
        # if we are weighed down by our inventory
        # and if we have things to drop
        # then dropping them is a high priority
        if self.status.burden_level > BURDEN_LEVEL_NONE:
            drop_letters = set(self.inventory.gen_letter_drop_selection(cursor_square))
            if len(drop_letters) > 1:
                return 'D'
            elif len(drop_letters) == 1:
                return 'd'
        # wear a good armor if we are not polymorphed
        if not self.status.polymorphed:
            if self.inventory.get_wear_letter():
                return 'W'
        # try to get out of being stuck by opening the target square
        if self.should_open_stuck_target:
            self.should_open_stuck_target = False
            self.last_door_opening_location = self.stuck_target_location
            self.last_door_opening_direction = self.stuck_target_direction
            self.stuck_target_location = None
            self.stuck_target_direction = None
            print >> self.log, 'trying to open a stuck target square'
            return 'o'
        # fight an adjacent monster that is not a ghost or an aggressive invisible monster
        for nloc, command in nloc_and_command:
            monster = self.levelmap.level[nloc].monster
            if monster:
                if monster.should_fight():
                    if (not monster.is_ghost()) and (not monster.is_invisible()):
                        print >> self.log, 'trying to fight an adjacent monster that is not a ghost or an aggressive invisible monster'
                        print >> self.log, 'the target monster is "%s"' % str(monster)
                        return command
        # cure yourself of blindness by eating a carrot
        if self.status.blind:
            if self.status.hunger_level >= HUNGER_LEVEL_NONE:
                for letter, item in self.inventory.letter_to_item.items():
                    if item.includes_one_of(['carrot']):
                        self.eating_letter = letter
                        return 'e'
        # fight an adjacent monster that is not a ghost
        for nloc, command in nloc_and_command:
            monster = self.levelmap.level[nloc].monster
            if monster:
                if monster.should_fight():
                    if not monster.is_ghost():
                        print >> self.log, 'trying to fight an adjacent monster that is not a ghost'
                        print >> self.log, 'the target monster is "%s"' % str(monster)
                        return command
        # cure yourself of lycanthropy by eating wolfsbane
        if self.lycanthropic:
            if self.status.hunger_level >= HUNGER_LEVEL_NONE:
                for letter, item in self.inventory.letter_to_item.items():
                    if item.includes_one_of(['wolfsbane']):
                        self.eating_letter = letter
                        return 'e'
        # fight an adjacent ghost
        for nloc, command in nloc_and_command:
            monster = self.levelmap.level[nloc].monster
            if monster:
                if monster.should_fight():
                    if monster.is_ghost():
                        print >> self.log, 'trying to fight an adjacent ghost'
                        print >> self.log, 'the target monster is "%s"' % str(monster)
                        return command
        # Eat partly eaten food.
        for letter, item in self.inventory.letter_to_item.items():
            if 'partly eaten' in item.name:
                self.eating_letter = letter
                return 'e'
        # Eat food if we are hungry and have not eaten much since last time we prayed.
        if self.status.hunger_level >= HUNGER_LEVEL_HUNGRY:
            if self.consumed_nutrition < 500:
                response = self.inventory.get_food_letter_and_nutrition()
                if response:
                    letter, nutrition = response
                    self.consumed_nutrition += nutrition
                    self.eating_letter = letter
                    return 'e'
        # drop something when we are unburdened
        drop_letters = set(self.inventory.gen_letter_drop_selection(cursor_square))
        if len(drop_letters) > 1:
            return 'D'
        elif len(drop_letters) == 1:
            return 'd'
        # pick up something off the ground if we know something interesting is there
        if self.should_pick_up:
            self.should_pick_up = False
            self.should_do_inventory = True
            return ','
        # take off a bad armor
        if self.inventory.get_take_letter():
            return 'T'
        # turn on a light if appropriate
        if not self.inventory.is_lit():
            light_source_letter = self.inventory.get_light_source_letter()
            if light_source_letter:
                self.apply_letter = light_source_letter
                self.invalidate_inventory()
                return 'a'
        # Fiddle with a named large container on the floor.
        # Here is a state transition diagram for large containers.
        #
        #                    unnamed -> named -> trapped
        #                                     -> untrapped -> locked -> unlocked -> looted
        #                                                  -> looted 
        if (not self.status.blind) and (not self.status.conf) and (not self.status.stun) and (not self.status.hallu):
            for moniker in cursor_square.large_container_names:
                lore_item = self.lore.get_existing_item(moniker)
                if lore_item:
                    print >> self.log, 'we are assuming that there is a large container named', moniker, 'here'
                    if lore_item.trapped:
                        print >> self.log, 'the container is trapped so we are ignoring it'
                    elif lore_item.untrap_attempt_count < 3:
                        if lore_item.untrap_attempt_count:
                            print >> self.log, 'the container has been checked for traps only', lore_item.untrap_attempt_count, 'times'
                            print >> self.log, 'checking for traps again'
                        else:
                            print >> self.log, 'the container has not yet been checked for traps'
                            print >> self.log, 'checking for traps for the first time'
                        self.untrap_direction = '.'
                        return ascii_to_meta('u')
                    elif lore_item.locked is None:
                        print >> self.log, 'the lock state of the container is unknown so we will attempt to loot it'
                        self.loot_moniker = moniker
                        return ascii_to_meta('l')
                    elif lore_item.locked == True:
                        print >> self.log, 'the container is locked'
                        # our first choice is a key and our second choice is a lock pick
                        unlocking_letter = None
                        for letter, item in self.inventory.letter_to_item.items():
                            if item.is_skeleton_key():
                                unlocking_letter = letter
                        if not unlocking_letter:
                            for letter, item in self.inventory.letter_to_item.items():
                                if item.can_unlock_containers():
                                    unlocking_letter = letter
                        if unlocking_letter:
                            print >> self.log, 'attempting to unlock the locked container'
                            self.container_unlocking_direction = '.'
                            self.apply_letter = unlocking_letter
                            self.unlock_moniker = moniker
                            return 'a'
                        else:
                            print >> self.log, 'we have no key or lock pick so we are ignoring the locked container'
                    elif not lore_item.looted:
                        print >> self.log, 'looting the unlooted container'
                        self.loot_moniker = moniker
                        return ascii_to_meta('l')
                else:
                    print >> self.log, 'the large container named', moniker, 'was not found in our records'
        # do some high priority movement if normal status
        if (not self.status.blind) and (not self.status.conf) and (not self.status.stun) and (not self.status.hallu):
            # go to a stairway that is not yet confirmed and associated with a region
            command = self.levelmap.explore_stairway()
            if command:
                return command
            # see if traveling to another region would be good
            command = self.levelmap.explore_travel()
            if command:
                return command
        # Search a dead end if the level might have secret doors.
        # Searching while blind is not a good idea because you can make friendly monsters show up as "I".
        if not self.status.blind:
            if self.levelmap.is_dead_end(cursor_location):
                if self.levelmap.has_secret_doors():
                    target_search_turns = min(9, 27 - self.levelmap.level[cursor_location].search_count_from)
                    if target_search_turns > 0:
                        self.search_location = cursor_location
                        self.search_turn_begin = self.status.turns
                        return '%ds' % target_search_turns
        # If we failed to push a boulder then throw something in the direction of the boulder.
        if self.boulder_failure:
            self.boulder_failure = False
            delta = self.last_sokoban_push_delta
            self.last_sokoban_push_delta = None
            self.last_sokoban_push_target = None
            # Find a dagger or a dart.
            missile_letter = None
            for letter, item in self.inventory.letter_to_item.items():
                if item.is_dart() or item.is_dagger():
                    missile_letter = letter
            # Take some action to pass a turn until we try pushing the boulder again.
            if missile_letter:
                # Throw the dagger or dart if we have one.
                print >> self.log, 'to reset the boulder failure we are throwing something through the boulder'
                self.missile_letter = missile_letter
                self.missile_direction = delta_to_vi(delta)
                return 't'
            else:
                # Skip a turn and try again next time.
                print >> self.log, 'to reset the boulder failure we are waiting a turn'
                return '.'
        # Push a boulder if we are in sokoban and are in the right position and we didn't just fail.
        if not self.boulder_failure:
            if (not self.status.conf) and (not self.status.stun) and (not self.status.hallu):
                delta = self.levelmap.get_sokoban_push_delta(cursor_location)
                if delta:
                    print >> self.log, 'we are reflexively pushing the boulder and saving the direction and target location'
                    # save the direction in case we need to throw something
                    self.last_sokoban_push_delta = delta
                    # save the target so we know when we got there
                    drow, dcol = delta
                    row, col = cursor_location
                    target_location = (row + drow, col + dcol)
                    self.last_sokoban_push_target = target_location
                    return delta_to_vi(delta)
        # try to open a door nicely or by kicking
        # avoid kicking shopkeeper doors
        # doors cannot be opened if you are in a pit; instead, try to move out of the pit.
        # all doors in minetown are marked unkickable.
        # make sure the bot has his wits about him before he starts kicking things
        # do not try to open a door while polymorphed
        if (not self.status.blind) and (not self.status.conf) and (not self.status.stun) and (not self.status.hallu) and (not self.status.polymorphed):
            for nloc, command in nloc_and_command:
                nlevel_square = self.levelmap.level[nloc]
                if nlevel_square.hard in (HM_CLOSED, HM_UNLOCKED, HM_LOCKED):
                    if self.trapped_pit:
                        print >> self.log, 'avoiding trying to open a door because we are trapped in a pit'
                        return command
                    elif nlevel_square.hard == HM_CLOSED:
                        self.last_door_opening_location = nloc
                        self.last_door_opening_direction = command
                        print >> self.log, 'trying to open the door which we do not know whether it is locked or not'
                        return 'o'
                    elif nlevel_square.hard == HM_UNLOCKED:
                        self.last_door_opening_location = nloc
                        self.last_door_opening_direction = command
                        print >> self.log, 'trying to open the unlocked door'
                        return 'o'
                    elif nlevel_square.hard == HM_LOCKED:
                        # try to unlock the door with a key
                        unlock_letter = self.inventory.get_skeleton_key_letter()
                        # if we do not have a key then pick the lock if it is safe
                        if not unlock_letter:
                            pickability = self.levelmap.get_pickable_status(nloc)
                            print >> self.log, 'the pickability of the adjacent locked door is:', pickability
                            if pickability == 'pickable':
                                # try to pick the lock with a lockpick or credit card
                                unlock_letter = self.inventory.get_unlock_letter()
                        if unlock_letter:
                            self.apply_letter = unlock_letter
                            self.last_door_opening_location = nloc
                            self.last_door_opening_direction = command
                            print >> self.log, 'trying to unlock the door or pick its lock'
                            return 'a'
                        # try to kick the door open
                        kickability = self.levelmap.get_kickable_status(nloc)
                        print >> self.log, 'the kickability of the adjacent locked door is:', kickability
                        if kickability == 'kickable':
                            self.last_door_opening_location = nloc
                            self.last_door_opening_direction = command
                            print >> self.log, 'trying to kick down the door'
                            return '\x04'
                        else:
                            print >> self.log, 'adjacent to a door that should not be kicked for some reason'
        # do low priority movement if the bot is healthy
        if (not self.status.blind) and (not self.status.conf) and (not self.status.stun) and (not self.status.hallu):
            # explore a square on the current level
            command = self.levelmap.explore_square()
            if command:
                return command
            # go to a level where we can desperately search for a staircase down
            command = self.levelmap.explore_travel_desperate()
            if command:
                return command
            # go to a square where we can search a wall
            command = self.levelmap.explore_square_desperate()
            if command:
                return command
        # if all else fails try to search unless the bot is blind.
        # searching while blind is not a good idea because you can make friendly monsters show up as "I".
        self.search_location = cursor_location
        self.search_turn_begin = self.status.turns
        if not self.status.blind:
            print >> self.log, 'searching desperately'
            return '9s'
        else:
            print >> self.log, 'waiting in blind desperation'
            return '9.'

    def process_incoming(self, ansi, incoming_ascii_strings, bloated_string):
        # deal separately with special requested screens such as inventory, pick up, drop, and loot screens
        value = self.process_incoming_special(incoming_ascii_strings, bloated_string)
        if value:
            return value
        # stash incoming '--More--' messages in a buffer to read when the actual turn starts.
        value = self.process_incoming_message(ansi, incoming_ascii_strings, bloated_string)
        if value:
            return value
        # respond to direct requests
        # TODO
        # perhaps don't always clear messages after a request?
        # clearing could be a mistake when there are messages that precede a request,
        # for example when the request is an unprovoked request such as being hit by a potion.
        value = self.process_incoming_request(ansi, incoming_ascii_strings, bloated_string)
        if value:
            self.messages = []
            return value
        # at this point we have the initiative.
        cursor_location = (ansi.row, ansi.col)
        self.process_incoming_status(ansi)
        self.read_post_status_messages(ansi)
        value = self.process_incoming_misc(ansi)
        if not value:
            value = '.'
        # See if we are trying to move.
        value_to_offset = {
            'k': (-1, 0),
            'j': (1, 0),
            'h': (0, -1),
            'l': (0, 1),
            'y': (-1, -1),
            'u': (-1, 1),
            'b': (1, -1),
            'n': (1, 1)
        }
        next_location = None
        next_square = None
        if value in value_to_offset:
            drow, dcol = value_to_offset[value]
            next_location = (ansi.row + drow, ansi.col + dcol)
            next_square = self.levelmap.level[next_location]
        # See if we are attacking a monster.
        # This is used for interpreting peaceful monster messages.
        if next_square:
            if next_square.monster:
                self.attack_location = next_location
        # If all of the following conditions hold then we might be stuck:
        #   - neither the screen contents nor the cursor position have changed for three turns with initiative
        #   - last time we had the initiative we tried to move or attack
        #   - we currently have the initiative and are trying to move or attack again
        #   - we are not trapped in a pit
        # If these conditions hold then try opening a door in the direction we want to go.
        current_ansi_hash = hash(ansi)
        check_stuck = False
        # add the current hash and command to the lists of recent states
        self.recent_initiative_hashes.append(current_ansi_hash)
        self.recent_initiative_commands.append(value)
        # make sure the number of saved hashes is the same as the number of saved commands
        if len(self.recent_initiative_commands) != len(self.recent_initiative_hashes):
            print >> self.log, 'WARNING: the number of recorded recent initiative commands and initiative hashes should be the same'
            print >> self.log, len(self.recent_initiative_commands), 'recorded recent initiative commands'
            print >> self.log, len(self.recent_initiative_hashes), 'recorded recent initiative hashes'
        # make sure we are not saving too much history
        if len(self.recent_initiative_commands) > 3:
            print >> self.log, 'WARNING: there were', len(self.recent_initiative_commands), 'recorded recent initiative commands but there should be no more than three'
        # detect repetition
        if len(set(self.recent_initiative_commands)) == 1:
            if len(set(self.recent_initiative_hashes)) == 1:
                print >> self.log, len(self.recent_initiative_hashes), 'detected some repetition'
                check_stuck = True
        if check_stuck:
            if value in value_to_offset and not self.trapped_pit:
                # log the stuck state
                print >> self.log, 'requesting to use the semi-colon to see why we are stuck'
                print >> self.log, 'target square: %s  target square state: %d' % (str(next_location), self.levelmap.level[next_location].hard)
                # log a stuck screenshot
                f = open('stuck-screenshot.ansi', 'wb')
                f.write(ansi.to_ansi_string())
                f.close()
                # notify that we need to examine the target location
                self.stuck_target_location = next_location
                self.stuck_target_direction = value
                value = ';'
        # If we went up or down the stairs then we expect a level change.
        if value in list('<>'):
            self.expecting_level_change = True
        # store the cursor location
        self.last_cursor_location = cursor_location
        # clear the messages
        self.messages = []
        # forget a little bit of the past
        self.recent_initiative_hashes = self.recent_initiative_hashes[-2:]
        self.recent_initiative_commands = self.recent_initiative_commands[-2:]
        # send the command
        return value


class Nethack:
    def __init__(self):
        # login_state can be:
        # 0 not logged in
        # 1 playing a new game
        # 2 playing a restored game
        # 3 dead or quit
        self.login_state = 0
        self.bot = None
        self.log = open('nethack.log', 'wt')
        self.slaves = []

    def set_bot(self, bot):
        self.bot = bot

    def add_slave(self, slave):
        """
        Maintain a list of places to send the commands.
        Each place has an add_bot_command(msg) function.
        """
        self.slaves.append(slave)

    def give_order(self, msg):
        print >> self.log, msg
        self.log.flush()
        for slave in self.slaves:
            slave.add_bot_command(msg)

    def process_incoming_get_order(self, ansi):
        incoming_ascii_strings = ansi.to_ascii_strings()
        bloated_string = ''.join(incoming_ascii_strings)
        s = bloated_string
        # get this party started
        if self.login_state == 0:
            if 'welcome to NetHack!' in s:
                print >> self.log, 'yay more plunder'
                self.login_state = 1
            elif 'Restoring save file' in s:
                print >> self.log, 'boo old game'
                self.login_state = 2
                return '\n'
            elif 'some stale' in s:
                print >> self.log, 'dealing with a stale process'
                return '\n'
            elif 'Logged in as' in s:
                if 'Play NetHack' not in s:
                    print >> self.log, 'ERROR: the Play NetHack option was not available'
                print >> self.log, 'selecting the Play NetHack option'
                print >> self.log, 'seconds since the epoch:', time.time()
                return 'p'
            elif 'Not logged in' in s:
                print >> self.log, 'selecting the login option'
                return 'l'
            elif 'Please enter your username.' in s:
                print >> self.log, 'entering the username'
                return self.bot.get_username() + '\n'
            elif 'Please enter your password.' in s:
                print >> self.log, 'entering the password'
                return self.bot.get_password() + '\n'
            else:
                print >> self.log, 'unknown pre-login message'
        # nip these confirmations at the bud
        if 'Really quit?' in s:
            return 'y'
        elif 'Still climb?' in s:
            return 'y'
        elif 'Do you want your possessions identified?' in s:
            return 'q'
        # notice the death message
        if 'You die..' in bloated_string:
            self.login_state = 3
            print >> self.log, 'we have apparently died'
            self.log.flush()
        # notice the Goodbye screen
        top_string = incoming_ascii_strings[0]
        if top_string.startswith('Goodbye'):
            self.login_state = 3
            print >> self.log, 'NetHack has bid us goodbye'
            self.log.flush()
        # ask the bot about everything else once we are logged in
        if self.login_state == 1:
            return self.bot.process_incoming(ansi, incoming_ascii_strings, bloated_string)
        else:
            if '--More--' in s:
                print >> self.log, 'the bot is confused about the login state and is trying to skip past messages'
                self.log.flush()
                return '\n'
            else:
                print >> self.log, 'the bot is confused about the login state so it is trying to quit'
                self.log.flush()
                return ascii_to_meta('q')

    def process_incoming(self, ansi):
        order = self.process_incoming_get_order(ansi)
        if not order:
            print >> self.log, 'no response for this input'
            assert False
        self.give_order(order)


def get_screenshot():
    f = open('screenshot.txt', 'wt')
    print >> f, ansi.to_ansi_string()

def main():
    """
    # play nethack repeatedly
    """
    while True:
        syslog = open('sys.log', 'a')
        print >> syslog, 'init'
        # create the socket layer
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("nethack.alt.org", 23))
        # create the telnet layer
        telnet = Telnet()
        telnet.set_custom_action(get_screenshot)
        # create the ansi terminal layer
        ansi = Ansi()
        telnet.add_listener(ansi)
        # create the nethack layer
        nethack = Nethack()
        nethack.add_slave(telnet)
        ansi.add_listener(nethack)
        # create the bot layer
        bot = GatherBot()
        nethack.set_bot(bot)
        # alternate sending and receiving data until the connection breaks
        while True:
            errors = [s]
            readers = []
            writers = []
            if telnet.network_state in (STATE_WANT_TO_SEND_DATA, STATE_WANT_TO_SEND_PING):
                writers = [s]
                canread, canwrite, haserr = select.select(readers, writers, errors, 10)
                if s in haserr:
                    break
                if s in canwrite:
                    data = telnet.get_pending_output()
                    assert data
                    nsent = s.send(data)
                    assert nsent
                    telnet.notify_bytes_sent(nsent)
                else:
                    print >> syslog, time.asctime()
                    print >> syslog, '\t', 'timout in network state', telnet.network_state
            elif telnet.network_state in (STATE_WAITING_FOR_DATA, STATE_WAITING_FOR_DATA_AND_PONG):
                readers = [s]
                canread, canwrite, haserr = select.select(readers, writers, errors, 10)
                if s in haserr:
                    break
                if s in canread:
                    try:
                        data = s.recv(4096)
                    except socket.error, e:
                        print >> syslog, e
                        break
                    if data:
                        telnet.process_incoming(data)
                    else:
                        print >> syslog, 'received zero bytes somehow'
                else:
                    print >> syslog, time.asctime()
                    print >> syslog, '\t', 'timout in network state', telnet.network_state
        if not bot.loops_forever():
            print >> syslog, 'the bot does not want to loop forever'
            break

if __name__ == '__main__':
    #profile.run('main()')
    main()


