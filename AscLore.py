
# for checking sokoban data file existence
import os

class AscLoreItem:
    """
    Keep the information associated with the name of an item.
    """
    def __init__(self, moniker):
        """
        For all of these options None means the state is unknown.
        """
        # save the name here for reverse lookup
        self.moniker = moniker
        # the emptiness property applies to lamps and charged items
        self.empty = None
        # count the number of times we have attempted to untrap the item
        self.untrap_attempt_count = None
        # have we found a trap on the item?
        self.trapped = None
        # is it known to be locked?
        self.locked = None
        # is it known to be looted?
        self.looted = None


class AscLore:
    """
    Remember properties of named objects and monsters.
    """
    def __init__(self):
        self.moniker_to_item = {}

    def create_item(self, moniker):
        self.moniker_to_item[moniker] = AscLoreItem(moniker)

    def get_existing_item(self, moniker):
        return self.moniker_to_item.get(moniker, None)

    def get_or_create_item(self, moniker):
        if moniker not in self.moniker_to_item:
            self.moniker_to_item[moniker] = AscLoreItem(moniker)
        return self.moniker_to_item[moniker]


class IdGenerator:
    """
    Generates unique printable strings.
    """
    def __init__(self):
        """
        Generate globally unique identifiers.
        They are global in the sense that they persist across sessions.
        This is important because 'bones files' allow items in earlier games to reappear.
        """
        self.digits = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        self.base = len(self.digits)
        self.guid_filename = 'next-guid.dat'

    def get_next_id(self):
        # create the guid file if it does not exist
        if not os.path.exists(self.guid_filename):
            f = open(self.guid_filename, 'wt')
            print >> f, 0
            f.close()
        # read the guid from the guid file
        f = open(self.guid_filename, 'rt')
        guid = int(list(f.readlines())[0])
        f.close()
        # write the next guid to the file
        f = open(self.guid_filename, 'wt')
        print >> f, guid + 1
        f.close()
        id_string = self.integer_to_string(guid)
        # test the integer conversion
        id_integer = self.string_to_integer(id_string)
        error_message = 'original id integer: %d  translated id string: %s  back translated integer: %d' % (guid, id_string, id_integer)
        assert id_integer == guid, error_message
        # return the string
        return id_string

    def integer_to_string(self, id_integer):
        """
        @param id_integer: an integer
        @return: the corresponding compressed string
        """
        arr = []
        counter = id_integer
        while True:
            arr.append(counter % self.base)
            counter /= self.base
            if counter == 0:
                break
        return ''.join(self.digits[x] for x in reversed(arr))

    def string_to_integer(self, id_string):
        """
        @param id_string: the compressed string representing the id of the object or monster
        @return: the corresponding integer
        """
        # convert the string to an array accounting of the possibility of a single digit
        if len(id_string) == 1:
            arr = [id_string]
        else:
            arr = list(id_string)
        total = 0
        multiplier = 1
        for digit in reversed(arr):
            if digit not in self.digits:
                return None
            value = self.digits.find(digit)
            total += value * multiplier
            multiplier *= self.base
        return total
