"""
This code deals with nethack's square selection mode.
In nethack there are at least two ways to enter square selection mode.
1) The command ';' lets you inspect a square.
2) The command 'C' lets you name a monster.
The selection mode lets you move a cursor around the screen to pick a square.
The selection cursor starts on the player's square.
Navigation of the cursor is possible using single letter commands.
The 8 directional keys {h,j,k,l,y,u,b,n} move the cursor to a neighboring square.
The capitalized forms of these keys move the cursor up to 8 squares away.
Dungeon features can also be used to move the cursor.
When these are used, the cursor moves to the right until it encounters the feature.
If no feature was encountered on the current line, the cursor moves to the
first column of the next line and continues the scan.
Some features that can be used in this way include:
    ^   trap
    |   wall or open door
    -   wall or open door
    _   altar
    {   fountain (I think I have also defined sink and throne as this symbol)
    >   staircase down
    <   staircase up
    #   unlit floor or other rare dungeon feature
Once the cursor has been moved to the target square
pressing the '.' key makes the selection thereby terminating the selection mode.
"""

from AscUtil import Rect, vi_delta_pairs
import AscDP

# For a rectangle of given dimensions the transitions induced
# by directional moves are always the same.
# Cache these transitions so they can be reused among instances.
# This precalculation is for speed optimization.
dimensions_to_move_cache = {}

class DirectionMoveCache(Rect):
    """
    This precalculates directional transitions common to all maps.
    """
    def __init__(self, row_min, col_min, row_max, col_max):
        Rect.__init__(self, row_min, col_min, row_max, col_max)
        self.cached_links = []

    def gen_direction_moves(self):
        """
        @yield: (source_location, target_location, command) triples
        """
        if not self.cached_links:
            self.cache_links()
        for triple in self.cached_links:
            yield triple

    def cache_links(self):
        """
        Create the cached links.
        These are the links between locations caused by using direction keys for navigation
        as opposed to using dungeon features.
        """
        for source_location in self.gen_locations():
            for vi, delta in vi_delta_pairs:
                drow, dcol = delta
                for command, magnitude in ((vi, 1), (vi.upper(), 8)):
                    target_location = source_location
                    for i in range(magnitude):
                        trow, tcol = target_location
                        next_target_location = (trow + drow, tcol + dcol)
                        if self.is_inbounds(next_target_location):
                            target_location = next_target_location
                        else:
                            break
                    triple = (source_location, target_location, command)
                    self.cached_links.append(triple)


class ObjectPicker(Rect):
    def __init__(self, location_to_ascii, row_min=1, col_min=0, row_max=21, col_max=78):
        """
        Build the transition and dynamic programming tables used to find
        the shortest path to a location.
        One object picker should be created per selection.
        @param location_to_ascii: a dictionary mapping location pairs to ascii values
        @param target_locations: an iterable collection of equivalent target locations
        """
        # Define the area of interest.
        Rect.__init__(self, row_min, col_min, row_max, col_max)
        # Define the transition table.
        self.transition_table = AscDP.BackwardsForwardsTable()
        # Add direction moves specific to the dimensions of this map.
        dimensions = (row_min, col_min, row_max, col_max)
        if dimensions not in dimensions_to_move_cache:
            dimensions_to_move_cache[dimensions] = DirectionMoveCache(*dimensions)
        for triple in dimensions_to_move_cache[dimensions].gen_direction_moves():
            self.transition_table.add(*triple)
        # Add feature moves specific to this map.
        for triple in self.gen_feature_moves(location_to_ascii):
            self.transition_table.add(*triple)

    def gen_feature_moves(self, location_to_ascii):
        # Generate dungeon feature movements.
        dungeon_features = '^|-_{<>#'
        for feature in dungeon_features:
            # Get the sorted list of locations of the feature.
            feature_locations = []
            for location in self.gen_locations():
                ascii = location_to_ascii[location]
                if ascii == feature:
                    feature_locations.append(location)
            feature_locations.sort()
            if len(feature_locations) == 0:
                # No features were found.
                continue
            elif len(feature_locations) == 1:
                # One feature was found.
                target_location = feature_locations[0]
                for source_location in self.gen_locations():
                    yield (source_location, target_location, feature)
            else:
                # Consider wrapped pairs of consecutive feature locations.
                for location_begin, location_end in zip(feature_locations, feature_locations[1:] + [feature_locations[0]]):
                    # Allow all squares in each location range to move to the end of the range in one step.
                    for source_location in self.row_major_range(location_begin, location_end):
                        yield (source_location, location_end, feature)

    def get_next_location(self, location, action):
        return self.transition_table.forwards.get_sink(location, action)

    def get_best_action(self, location, targets):
        """
        @param location: current location
        @param targets: an iterable container of equally desirable target locations
        @return: the first action in the shortest path
        """
        best_actions = AscDP.get_best_actions(location, targets, self.transition_table.backwards, self.transition_table.forwards)
        if best_actions:
            return list(best_actions)[0]

def mytest():
    field = [
            '01234567890123456789',
            '1...................',
            '2..@................',
            '3...........|---.|..',
            '4...........|....|..',
            '5...........|....|..',
            '6...........|----|..',
            '7...^...............',
            '8...................',
            '9...................',
            '0...................',
            '1..........>........',
            '2...................',
            '3.......>...........',
            '4...................',
            '5...................',
            '6...................',
            '7............^x.....',
            '8...................',
            '9...................'
            ]
    location_to_ascii = dict(((row, col), c) for (row, line) in enumerate(field) for (col, c) in enumerate(line) if row > 0 and col > 0)
    target_locations = [loc for loc, c in location_to_ascii.items() if c in 'xy']
    print 'target locations:', target_locations
    p = ObjectPicker(location_to_ascii, 1, 1, 19, 19)
    print 'field:'
    print '\n'.join(field)
    location = [loc for loc, c in location_to_ascii.items() if c == '@'][0]
    path_locations = [location]
    path_actions = []
    while location not in target_locations:
        action = p.get_best_action(location, target_locations)
        path_actions.append(action)
        location = p.get_next_location(location, action)
        path_locations.append(location)
    location_pairs = zip(path_locations[:-1], path_locations[1:])
    for (loca, locb), action in zip(location_pairs, path_actions):
        print '%s %s %s' % (loca, action, locb)

if __name__ == '__main__':
    mytest()





