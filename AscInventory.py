
"""
Track items in inventory.
Scrape inventory messages off of the screen.
"""

# need the trap name definitions
from AscLevelConstants import *

# TODO only recognize names given during the current game.

import re

# define the possible (B)lessed, (U)ncursed, (C)ursed states.
BUC_CURSED = 0
BUC_UNKNOWN = 1
BUC_UNCURSED = 2
BUC_BLESSED = 3

class Item:
    """
    This class describes an item or stack of items in inventory.
    """
    def __init__(self):
        self.name = None
        self.count = None

    def set_item_string(self, item_string):
        """
        @param item_string: the string describing an item or stack of items in inventory
        item_string examples:
            2 uncursed food rations
            a +0 two-handed sword (weapon in hands)
        """
        m = re.search(r'^a (.*)', item_string)
        if m:
            self.name = m.groups()[0]
            self.count = 1
            return True
        m = re.search(r'^an (.*)', item_string)
        if m:
            self.name = m.groups()[0]
            self.count = 1
            return True
        m = re.search(r'^(\d+) (.*)', item_string)
        if m:
            self.name = m.groups()[1]
            self.count = int(m.groups()[0])
            return True
        return False

    def get_buc(self):
        if 'blessed' in self.name:
            return BUC_BLESSED
        if 'uncursed' in self.name:
            return BUC_UNCURSED
        if 'cursed' in self.name:
            return BUC_CURSED
        if self.is_weapon():
            # if a weapon has a known enchantment and is not explicitly blessed or cursed
            # then it is uncursed
            if re.search(r'([-+]\d)'):
                return BUC_UNCURSED
        # if an item has known charges and is not explicitly blessed or cursed
        # then it is uncursed
        if re.search(r'(\(\d+:\d+\))'):
            return BUC_UNCURSED
        return BUC_UNKNOWN

    def get_corrosion_level(self):
        if 'corroded' in self.name:
            if 'thoroughly corroded' in self.name:
                return 3
            elif 'very corroded' in self.name:
                return 2
            else:
                return 1
        else:
            return 0

    def get_rust_level(self):
        if 'rusty' in self.name:
            if 'thoroughly rusty' in self.name:
                return 3
            elif 'very rusty' in self.name:
                return 2
            else:
                return 1
        else:
            return 0

    def get_moniker(self):
        pattern = r'named ([\da-zA-Z]+)'
        m = re.search(pattern, self.name)
        if m:
            return m.groups()[0]
        else:
            return None

    def includes_one_of(self, names):
        """
        @return: True when self.name includes one of the input names.
        """
        if not self.name:
            return False
        for name in names:
            if name in self.name:
                return True
        return False

    def is_gem(self):
        if self.includes_one_of(['glass orb', 'looking glass']):
            return False
        if self.includes_one_of(['gem', 'glass']):
            return True
        return False

    def is_wand(self):
        return self.includes_one_of(['wand'])

    def is_ring(self):
        """
        Ring mail isn't a ring.
        Neither is anything that quivering, shimmering, or glittering.
        Neither is stormbringer.
        """
        if self.includes_one_of(['mail', 'quivering', 'shimmering', 'glittering', 'bringer']):
            return False
        if self.includes_one_of(['ring']):
            return True

    def is_dagger(self):
        return self.includes_one_of(['dagger'])

    def is_dart(self):
        return self.includes_one_of(['dart', 'shuriken'])

    def is_weapon(self):
        if self.is_dagger():
            return True
        if self.is_dart():
            return True
        if self.includes_one_of(['axe', 'two-handed sword', 'short sword']):
            return True
        return False

    def is_good_helm(self):
        return self.includes_one_of(['dwarvish iron helm', 'hard hat'])

    def is_good_shoes(self):
        """
        These shoes rule.
        """
        return self.includes_one_of(['high boots', 'jackboots', 'iron shoes', 'hard shoes'])

    def is_good_cloak(self):
        """
        These cloaks have at least one base AC.
        Maintain one in inventory to wear when we get mithril.
        Do not wear one of unknown curse status over bad body armor.
        """
        # these cloaks have no base AC so skip them
        if self.includes_one_of(['mummy wrapping', 'orcish cloak', 'coarse mantelet', 'dwarvish cloak', 'hooded cloak']):
            return False
        # real names of magic cloaks
        if self.includes_one_of(['cloak of displacement', 'cloak of invisibility', 'cloak of magic resistance', 'cloak of protection']):
            return True
        # appearances of magic cloaks
        if self.includes_one_of(['piece of cloth', 'opera cloak', 'ornamental cope', 'tattered cape']):
            return True
        # real names of nonmagic cloaks
        if self.includes_one_of(['leather cloak', 'oilskin cloak', 'alchemy smock', 'elven cloak', 'robe']):
            return True
        # appearances of nonmagic cloaks
        if self.includes_one_of(['slippery cloak', 'apron', 'faded pall']):
            return True
        return False

    def is_gold(self):
        return self.includes_one_of(['gold piece'])

    def is_special_food(self):
        """
        The bot should generally not eat tripe or lizard corpses.
        """
        return self.includes_one_of(['tripe', 'lizard corpse'])

    def is_human_food(self):
        """
        Nutrition is available for each of these.
        """
        names = (
                'ration',
                'lembas wafer',
                'pancake',
                'cream pie',
                'candy bar',
                'fortune cookie'
                )
        return self.includes_one_of(names)

    def is_monkey_food(self):
        return self.includes_one_of(['banana'])

    def is_herbivore_food(self):
        # Things that are orange are not necessarily oranges
        if self.includes_one_of(['mail', 'scales', 'gem', 'potion']):
            return False
        # A horse wants a pear but not a spear
        if self.includes_one_of(['spear', 'pearl']):
            return False
        names = (
                'banana',
                'orange',
                'apple',
                'pear',
                'carrot',
                'lichen corpse',
                'melon',
                'slime mold',
                'myfruit',
                'wolfsbane',
                'garlic'
                )
        return self.includes_one_of(names)

    def get_nutrition(self):
        """
        This list is incomplete.
        It also fails to account for rotten food.
        """
        name_nutrition_pairs = (
                ('food ration', 800),
                ('cram ration', 600),
                ('K-ration', 400),
                ('C-ration', 300),
                ('lembas wafer', 800),
                ('pancake', 200),
                ('cream pie', 100),
                ('candy bar', 100),
                ('myfruit', 250),
                ('melon', 100),
                ('fortune cookie', 40)
                )
        for name, nutrition in name_nutrition_pairs:
            if name in self.name:
                return nutrition

    def is_light_source(self):
        names = (
                'candle',
                'lamp',
                'lantern'
                )
        return self.includes_one_of(names)

    def is_mithril(self):
        return self.includes_one_of(['mithril'])

    def is_skeleton_key(self):
        """
        Monkey isn't actually a kind of key.
        Neither is something that is murkey.
        """
        if self.includes_one_of(['onkey', 'urkey']):
            return False
        if self.includes_one_of(['key']):
            return True

    def can_lock(self):
        if self.is_skeleton_key():
            return True
        if self.includes_one_of(['lock pick']):
            return True
        return False

    def can_unlock_containers(self):
        """
        Credit cards cannot unlock containers.
        """
        if self.is_skeleton_key():
            return True
        if self.includes_one_of(['lock pick']):
            return True
        return False

    def can_unlock_doors(self):
        if self.is_skeleton_key():
            return True
        if self.includes_one_of(['credit', 'lock pick']):
            return True
        return False

    def is_large_container(self):
        if self.includes_one_of(['large box', 'chest', 'ice box']):
            return True

    def is_body_armor(self):
        return self.includes_one_of(['mail', 'leather armor', 'leather jacket', 'mithril'])

    def is_good(self):
        """
        These are items we always want to pick up.
        There are other items that we want to pick up conditionally:
            mithril
            light sources
            large containers (for naming)
        """
        if self.is_gold():
            return True
        if self.is_herbivore_food():
            return True
        if self.is_human_food():
            return True
        if self.is_special_food():
            return True
        if self.can_unlock_containers():
            return True
        if self.can_unlock_doors():
            return True
        if self.is_wand():
            return True
        if self.is_ring():
            return True
        return False

    def __str__(self):
        return '{%d} {%s}' % (self.count, self.name)

def item_selection_helper(ascii_strings, bloated_string):
    """
    Look at a page of selectable items.
    This can be used for the 'Pick up what' screen or for the inventory screen.
    It works for single or multi-page screens.
    For inventory screens there should be no selected letter item pairs.
    @return: (unselected letter item pairs, selected letter item pairs) or None
    """
    unselected_letter_item_pairs = []
    selected_letter_item_pairs = []
    # make sure we are looking at the right screen
    termination_string = None
    if '(end)' in bloated_string:
        termination_string = '(end)'
    else:
        pattern = r'(\(\d+ of \d+\))'
        m = re.search(pattern, bloated_string)
        if m:
            termination_string = m.groups()[0]
    if not termination_string:
        return None
    # find the row and column of '(end)'
    end_row = None
    end_col = None
    for row_index, line in enumerate(ascii_strings):
        end_col = line.find(termination_string)
        if end_col != -1:
            end_row = row_index
            break
    # make sure we found some inventory items
    if end_row is None:
        return None
    # read the inventory messages
    for line in ascii_strings[:end_row]:
        inventory_line = line[end_col:].strip()
        selection_marker = inventory_line[1:4]
        if selection_marker in (' - ', ' + '):
            letter = inventory_line[0]
            item_string = inventory_line[4:]
            item = Item()
            if item.set_item_string(item_string):
                if selection_marker == ' - ':
                    unselected_letter_item_pairs.append((letter, item))
                else:
                    selected_letter_item_pairs.append((letter, item))
    # return the unselected and the selected letter item pairs
    return (unselected_letter_item_pairs, selected_letter_item_pairs)

def get_pick_up_what(ascii_strings, bloated_string):
    """
    This is in response to 'Pick up what'.
    Note that in multi-page piles only the first page has 'Pick up what' at the top.
    @return: (unselected letter item pairs, selected letter item pairs) or None
    """
    return item_selection_helper(ascii_strings, bloated_string)

def gen_things_that_are_here(ascii_strings, bloated_string):
    """
    This is called in response to seeing the message:
    'Things that are here'
    @param ascii_strings: lines of ascii text on the screen when the inventory is being displayed.
    @param bloated_string: all the ascii strings concatenated together.
    """
    # make sure we are looking at the right screen
    if 'Things that are here' not in bloated_string:
        return
    # see where the list of items begins
    begin_row = None
    begin_col = None
    for row_index, line in enumerate(ascii_strings):
        begin_col = line.find('Things that are here')
        if begin_col != -1:
            begin_row = row_index
            break
    # make sure we found some inventory items
    if begin_row is None:
        return
    # read the inventory messages
    for line in ascii_strings[begin_row + 1:]:
        item_string = line[begin_col:].strip()
        if item_string.startswith('--More--'):
            break
        letter = None
        item = Item()
        if item.set_item_string(item_string):
            yield item

def gen_floor_items(bloated_string):
    """
    This is called in response to seeing the message:
    'You see here'
    @param bloated_string: all the ascii strings concatenated together.
    """
    # look for interesting stuff on the floor
    if 'You see here' in bloated_string:
        current_index = -1
        while True:
            index = bloated_string.find('You see here', current_index+1)
            pattern = r'^You see here (.*?)\.'
            m = re.search(pattern, bloated_string[index:])
            if m:
                item_string = m.groups()[0]
                item = Item()
                if item.set_item_string(item_string):
                    yield item
                current_index = index
            else:
                break

class AscInventory:
    def __init__(self, lore):
        self.lore = lore
        self.letter_to_item = {}

    def add_inventory(self, ascii_strings, bloated_string):
        """
        @param ascii_strings: lines of ascii text on the screen when the inventory is being displayed.
        @param bloated_string: all the ascii strings concatenated together.
        """
        # TODO add more descriptive error messages
        response = item_selection_helper(ascii_strings, bloated_string)
        if not response:
            return False
        unselected_letter_item_pairs, selected_letter_item_pairs = response
        if selected_letter_item_pairs:
            return False
        if not unselected_letter_item_pairs:
            return False
        for letter, item in unselected_letter_item_pairs:
            self.letter_to_item[letter] = item

    def get_carnivore_letter(self):
        """
        Return the letter of the best food with which to tame a carnivore.
        """
        priority_letter_pairs = []
        for letter, item in self.letter_to_item.items():
            if 'tripe' in item.name:
                # tripe is best
                priority_letter_pairs.append((0, letter))
            elif item.includes_one_of(['egg', 'cream pie']):
                # throwing these at an animal is aggressive
                continue
            elif item.is_human_food():
                # throw the dog a piece of human food with low nutrition
                priority_letter_pairs.append((item.get_nutrition(), letter))
        if priority_letter_pairs:
            priority, best_letter = min(priority_letter_pairs)
            return best_letter

    def get_herbivore_letter(self):
        """
        Return the letter of the best food with which to tame an herbivore.
        """
        priority_letter_pairs = []
        for letter, item in self.letter_to_item.items():
            if item.is_herbivore_food():
                if 'wolfsbane' in item.name:
                    # save wolfsbane to get out of lycanthropy
                    priority_letter_pairs.append((1500, letter))
                elif 'carrot' in item.name:
                    # save carrots to cure blindness
                    priority_letter_pairs.append((1000, letter))
                else:
                    # save items with high nutrition
                    nutrition = item.get_nutrition()
                    if nutrition:
                        priority = nutrition
                    else:
                        priority = 0
                    priority_letter_pairs.append((1000, letter))
        if priority_letter_pairs:
            priority, best_letter = min(priority_letter_pairs)
            return best_letter

    def get_food_letter_and_nutrition(self):
        """
        Return the letter and nutrition of some food that the bot should eat.
        This is called when the bot has a high hunger level and has not eaten enough since the last time it prayed.
        """
        priority_letter_nutrition_triples = []
        for letter, item in self.letter_to_item.items():
            nutrition = item.get_nutrition()
            if nutrition:
                if 'cream pie' in item.name:
                    # prefer cream pie because it is useless for taming
                    priority_letter_nutrition_triples.append((-1000, letter, nutrition))
                else:
                    # prefer high nutrition food
                    priority_letter_nutrition_triples.append((-nutrition, letter, nutrition))
        if priority_letter_nutrition_triples:
            priority, best_letter, best_nutrition = min(priority_letter_nutrition_triples)
            return (best_letter, best_nutrition)

    def get_wear_letter(self):
        """
        If the inventory has armor that is better than what we are wearing,
        then return the letter of the armor being worn.
        Currently this gives a letter if we have a mithril coat but are not wearing a mithril coat.
        Assume that the bot is not fortunate enough to have dragon scale mail.
        Also wear a hat and boots without regard to BUC status.
        """
        wearing_body_armor = False
        wearing_helm = False
        wearing_shoes = False
        wearing_cloak = False
        wearing_mithril = False
        for letter, item in self.letter_to_item.items():
            if '(being worn)' in item.name:
                if item.is_body_armor():
                    wearing_body_armor = True
                    if 'mithril' in item.name:
                        wearing_mithril = True
                elif item.is_good_helm():
                    wearing_helm = True
                elif item.is_good_shoes():
                    wearing_shoes = True
                elif item.is_good_cloak():
                    wearing_cloak = True
        # if we are not wearing body armor and we have mithril then wear the mithril
        if not wearing_body_armor:
            for letter, item in self.letter_to_item.items():
                if 'mithril' in item.name:
                    return letter
        # if we are not wearing shoes then wear good shoes if we have some
        if not wearing_shoes:
            for letter, item in self.letter_to_item.items():
                if item.is_good_shoes():
                    return letter
        # if we are not wearing a helm then wear a good helm if we have one
        if not wearing_helm:
            for letter, item in self.letter_to_item.items():
                if item.is_good_helm():
                    return letter
        # if we are wearing mithril but not a cloak then wear a cloak
        if wearing_mithril and (not wearing_cloak):
            for letter, item in self.letter_to_item.items():
                if item.is_good_cloak():
                    return letter

    def get_take_letter(self):
        """
        If the inventory has armor that is better than what we are wearing,
        then return the letter of the armor being worn.
        Currently this gives a letter if we have mithril but are wearing something else.
        Assume that the bot is not fortunate enough to have dragon scale mail.
        """
        bad_body_armor_letter = None
        good_body_armor_letter = None
        for letter, item in self.letter_to_item.items():
            is_being_worn = '(being worn)' in item.name
            is_mithril = 'mithril' in item.name
            is_body_armor = item.is_body_armor()
            # note the letter of our armor that is worse than mithril
            if is_being_worn and is_body_armor and (not is_mithril):
                bad_body_armor_letter = letter
            # note the letter of our unworn mithril coat
            if (not is_being_worn) and is_mithril:
                good_body_armor_letter = letter
        # if we have mithril but are wearing bad body armor then take off the bad body armor
        if good_body_armor_letter and bad_body_armor_letter:
            return bad_body_armor_letter

    def gen_letter_acquisition_selection(self, unselected_letter_item_pairs, selected_items):
        """
        Decide which items to pick up.
        If we have a lot of items in inventory and a lot of items are selected
        then we might not want to select so many unselected items.
        The list of possessed items includes:
            - items in inventory
            - items that have been previously selected
            - items that have been selected in this function
        @return: a set of letters
        """
        # Make a list of all possessed items that includes those in inventory and those already selected.
        temp_possessed_items = self.letter_to_item.values() + selected_items
        # If we have mithril then do not choose mithril.
        # Otherwise select the first mithril item on each page.
        possessed_mithril_items = [item for item in temp_possessed_items if 'mithril' in item.name]
        # If we have a large container in inventory the do not pick one up.
        # Otherwise select the first unnamed large container on each page.
        possessed_large_container_items = [item for item in temp_possessed_items if item.is_large_container()]
        # If we have a lot of gems in inventory then do not pick one up.
        # Otherwise select the first gem on each page.
        possessed_gem_items = [item for item in temp_possessed_items if item.is_gem()]
        # do the same for helms and shoes and cloaks
        possessed_good_shoe_items = [item for item in temp_possessed_items if item.is_good_shoes()]
        possessed_good_helm_items = [item for item in temp_possessed_items if item.is_good_helm()]
        possessed_good_cloak_items = [item for item in temp_possessed_items if item.is_good_cloak()]
        # maintain some daggers and darts in inventory for sokoban
        possessed_dagger_items = [item for item in temp_possessed_items if item.is_dagger()]
        possessed_dart_items = [item for item in temp_possessed_items if item.is_dart()]
        # Make the selection.
        for letter, item in unselected_letter_item_pairs:
            moniker = item.get_moniker()
            if 'mithril' in item.name:
                # maintain a single mithril item
                if not possessed_mithril_items:
                    possessed_mithril_items.append(item)
                    yield letter
            elif item.is_good_shoes():
                # maintain a single pair of good shoes
                if not possessed_good_shoe_items:
                    possessed_good_shoe_items.append(item)
                    yield letter
            elif item.is_good_helm():
                # maintain a single good helm
                if not possessed_good_helm_items:
                    possessed_good_helm_items.append(item)
                    yield letter
            elif item.is_good_cloak():
                # maintain a single good cloak
                if not possessed_good_cloak_items:
                    possessed_good_cloak_items.append(item)
                    yield letter
            elif item.is_large_container() and not moniker:
                # maintain at most one large container and only if it is unnamed
                if not possessed_large_container_items:
                    possessed_large_container_items.append(item)
                    yield letter
            elif item.is_gem():
                # maintain a few gems to throw at unicorns
                gem_count = sum(item.count for item in possessed_gem_items)
                if gem_count < 5:
                    possessed_gem_items.append(item)
                    yield letter
            elif item.is_dagger():
                # maintain a few daggers for throwing at monsters behind boulders in sokoban
                dagger_count = sum(item.count for item in possessed_dagger_items)
                if dagger_count < 2:
                    possessed_dagger_items.append(item)
                    yield letter
            elif item.is_dart():
                # maintain a few darts for throwing at monsters behind boulders in sokoban
                dart_count = sum(item.count for item in possessed_dart_items)
                if dart_count < 20:
                    possessed_dart_items.append(item)
                    yield letter
            elif item.is_light_source():
                # pick up all anonymous and non-empty light sources
                if not moniker:
                    yield letter
                elif not self.lore.get_or_create_item(moniker).empty:
                    yield letter
            elif item.is_good():
                yield letter

    def should_pick_up_something(self, items):
        """
        Force the data to match the format required by gen_letter_acquisition_selection.
        @return: True if one of the items in the list is worth picking up.
        """
        # Create virtual item letters.
        unselected_letter_item_pairs = []
        for i, item in enumerate(items):
            virtual_letter = chr(ord('a') + i)
            item_pair = (virtual_letter, item)
            unselected_letter_item_pairs.append(item_pair)
        # Create a list of zero virtual selected items.
        selected_items = []
        # Use the more sophisticated function to determine which items should be picked up.
        letters = list(self.gen_letter_acquisition_selection(unselected_letter_item_pairs, selected_items))
        # Return True or False depending on whether any item is worth picking up.
        if letters:
            return True
        else:
            return False

    def is_lit(self):
        """
        Are we carrying a lit light source?
        """
        for item in self.letter_to_item.values():
            if item.is_light_source():
                if '(lit)' in item.name:
                    return True
        return False

    def gen_letter_naming_selection(self):
        """
        Decide which items to name.
        For now this includes only unnamed large containers.
        @return: a set of letters
        """
        for letter, item in self.letter_to_item.items():
            # Only name something once.
            if item.get_moniker():
                continue
            # Name large containers.
            if item.is_large_container():
                yield letter
            # Name a single light source if no light source is already named.
            named_light_source_letters = []
            unnamed_light_source_letters = []
            for letter, item in self.letter_to_item.items():
                if item.is_light_source():
                    if item.get_moniker():
                        named_light_source_letters.append(letter)
                    else:
                        unnamed_light_source_letters.append(letter)
            if unnamed_light_source_letters and not named_light_source_letters:
                yield unnamed_light_source_letters[0]

    def gen_letter_drop_selection(self, level_square):
        """
        Decide which items to drop.
        What we drop may depend on where we are standing.
        We may want to avoid dropping things on down staircases so the dropped items do not fall down the stairs.
        We may not want to drop an item on a square with a trap.
        We may want to drop items of certain BUC status on a square with an altar.
        @return: a set of letters
        """
        # Keep only one mithril item.
        # If a mithril item is being worn, then keep that item.
        # Otherwise, keep an arbitrary mithril item.
        mithril_letter_and_items = [(letter, item) for (letter, item) in self.letter_to_item.items() if 'mithril' in item.name]
        worn_mithril_letter_and_items = [(letter, item) for (letter, item) in mithril_letter_and_items if '(being worn)' in item.name]
        assert len(worn_mithril_letter_and_items) <= 1
        if len(worn_mithril_letter_and_items):
            letter, item = worn_mithril_letter_and_items[0]
            mithril_letter_to_keep = letter
        elif mithril_letter_and_items:
            letter, item = mithril_letter_and_items[0]
            mithril_letter_to_keep = letter
        else:
            mithril_letter_to_keep = None
        # If a mithril item has been chosen for retention then drop all other body armor that is not being worn.
        if mithril_letter_to_keep:
            for letter, item in self.letter_to_item.items():
                is_body_armor = item.is_body_armor()
                if is_body_armor and letter != mithril_letter_to_keep:
                    if '(being worn)' not in item.name:
                        yield letter
        # Drop named large containers.
        # Do not drop a named large container on a square with a trap.
        # Do not drop a named large container on a square with a down staircase.
        if level_square.trap in (TRAP_UNKNOWN, TRAP_NONE):
            if level_square.hard not in (HM_DOWN_UNCONFIRMED, HM_DOWN_CONFIRMED):
                for letter, item in self.letter_to_item.items():
                    if item.is_large_container() and item.get_moniker():
                        yield letter
        # Drop all named empty light sources.
        for letter, item in self.letter_to_item.items():
            moniker = item.get_moniker()
            if moniker:
                if item.is_light_source():
                    if self.lore.get_or_create_item(moniker).empty:
                        yield letter

    def get_light_source_letter(self):
        """
        This is the letter that should be applied to toggle between the lit and unlit state.
        For now, it is whichever light source is named.
        """
        for letter, item in self.letter_to_item.items():
            if item.is_light_source():
                if item.get_moniker():
                    return letter

    def get_light_source_moniker(self):
        """
        This is the letter that should be applied to toggle between the lit and unlit state.
        For now, it is whichever light source is named.
        """
        for letter, item in self.letter_to_item.items():
            if item.is_light_source():
                moniker = item.get_moniker()
                if moniker:
                    return moniker

    def get_unlock_letter(self):
        """
        To unlock something, prefer {a key}, then {a lock pick, a credit card}.
        """
        # find a skeleton key if we have one
        for letter, item in self.letter_to_item.items():
            if item.is_skeleton_key():
                return letter
        # find a lock pick or a credit card
        for letter, item in self.letter_to_item.items():
            if item.can_unlock_doors():
                return letter

    def get_skeleton_key_letter(self):
        """
        Be sure to use a skeleton key to unlock doors in minetown,
        because the guards are less likely to notice.
        """
        for letter, item in self.letter_to_item.items():
            if item.is_skeleton_key():
                return letter

    def __str__(self):
        arr = []
        for letter, item in self.letter_to_item.items():
            arr.append('{%s} %s' % (letter, str(item)))
        return '\n'.join(arr)




