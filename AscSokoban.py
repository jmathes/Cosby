"""
This module is related to NetHack sokoban.

Commands:
    {h, j, k, l} : move or push one space in a cardinal direction
    {y, u, b, n} : move one space diagonally
          {<, >} : load the previous or next unfinished level
              r  : reload the current level
              q  : quit
              .  : automatically move or push one space if possible
"""


import StringIO
import os
import profile
import time

from AscUtil import Rect, vi_delta_pairs
import AscDP

from heapq import heappush, heappop

all_level_strings_and_names = []

all_level_strings_and_names.append((
"""
------  -----   
|....|  |...|   
|.0..----.0.|   
|.0......0..|   
|..--->---0.|   
|---------.---  
|..^^^<|.....|  
|..----|0....|  
--^|   |.0...|  
 |^-----.0...|  
 |..^^^^0.0..| 
 |..----------
 ----
""", 'level_1a'))

all_level_strings_and_names.append((
"""
-------- ------
|<|>...---....|
|^|-.00....0..|
|^||..00|.0.0.|
|^||....|.....|
|^|------0----|
|^|    |......|
|^------......|
|..^^^^0000...|
|..-----......|
----   --------
""", 'level_1b'))

all_level_strings_and_names.append((
"""
-----------       -----------
|....|....---     |.........|
|..00|00...>|     |.........|
|.....0...---     |.........|
|....|....|       |....<....|
|-.---------      |.........|
|..0.|.....|      |.........|
|.00.|0.0.0|      |.........|
|..0.....0.|      |.........|
|.000|0..0.----------------+|
|....|..0.0.^^^^^^^^^^^^^^^.|
-----------------------------
""", 'level_2a'))

all_level_strings_and_names.append((
"""
 ----          -----------
--.>--------   |.........|
|..........|   |.........|
|.0-----0-.|   |.........|
|..|...|.0.|   |....<....|
|.0.0....0-|   |.........|
|.0..0..|..|   |.........|
|.----0.--.|   |.........|
|..0...0.|.--  |.........|
|.---0-...0.------------+|
|...|..0-.0.^^^^^^^^^^^^.|
|..0......----------------
-----..|..|               
    -------               
""", 'level_2b'))

all_level_strings_and_names.append((
"""
  --------          
---.|....|          
|...0....|----------
|.-.00-00|.|.......|
|.00-......|.......|
|.-..0.|...|.......|
|....-0--0-|...<...|
|..00..0...|.......|
|.--...|...|.......|
|....-0|---|.......|
---..0.-----------+|
  |..0>^^^^^^^^^^^.|
  ------------------
""", 'level_3a'))

all_level_strings_and_names.append((
"""
--------------------
|........|...|.....|
|.00..-00|.-.|.....|
|..|.0.0.|00.|.....|
|-.|..-..|.-.|..<..|
|...--.......|.....|
|...|.0.-...-|.....|
|.0.|0.|...--|.....|
|-0.|..-----------+|
|..0....^^^^^^^^^^.|
|...|.>-------------
--------            
""", 'level_3b'))

all_level_strings_and_names.append((
"""
--------------------------
|>......^^^^^^^^^^^^^^^^.|
|.......----------------.|
-------.------         |.|
 |...........|         |.|
 |.0.0.0.0.0.|         |.|
--------.----|         |.|
|...0.0..0.0.|         |.|
|...0........|         |.|
-----.--------   ------|.|
 |..0.0.0...|  --|.....|.|
 |.....0....|  |.+.....|.|
 |.0.0...0.--  |-|.....|.|
-------.----   |.+.....+.|
|..0.....|     |-|.....|--
|........|     |.+.....|  
|...------     --|.....|  
-----            -------
""", 'level_4a'))

all_level_strings_and_names.append((
"""
  ------------------------
  |..^^^^^^^^^^^^^^^^^^..|
  |..-------------------.|
----.|    -----        |.|
|..|0--  --...|        |.|
|.....|--|.0..|        |.|
|.00..|..|..0.|        |.|
--..00|...00.--        |.|
 |0..0...|0..|   ------|.|
 |.00.|..|..0| --|.....|.|
 |.0.0---|.0.| |.+.....|.|
 |.......|..-- |-|.....|.|
 ----.0..|.--  |.+.....+.|
    ---.--.|   |-|.....|--
     |.0...|   |.+.....|  
     |>.|..|   --|.....|  
     -------     -------  
""", 'level_4b'))


def sokoban_string_to_map(level_string):
    """
    Generate a refined map of the level from the crude ascii drawing.
    This function is designed to be used inside or outside the context of SokoMap.
    """
    level = {}
    raw_lines = [line.rstrip() for line in StringIO.StringIO(level_string)]
    while not raw_lines[0]:
        del raw_lines[0]
    while not raw_lines[-1]:
        del raw_lines[-1]
    row_count = len(raw_lines)
    col_count = max(len(raw_line) for raw_line in raw_lines)
    for row in range(row_count):
        for col in range(col_count):
            loc = (row, col)
            level[loc] = ' '
    for row, raw_line in enumerate(raw_lines):
        for col, c in enumerate(raw_line):
            loc = (row, col)
            level[loc] = c
    return level

def load_push_sequence(level_name):
    """
    Load the sequence of player moves that push a boulder.
    Each line in the file has four tab separated numbers:
        (player_row, player_col, boulder_row, boulder_col)
    @return: a list of boulder pushes or None if the file is empty or does not exist
    This function is designed to be used inside or outside the context of SokoMap.
    """
    filename = '%s.soko' % level_name
    if not os.path.exists(filename):
        return None
    push_sequence = []
    lines = list(open(filename).readlines())
    if not lines:
        return None
    for line in lines:
        push_command = [int(value) for value in line.split()]
        assert len(push_command) == 4
        push_sequence.append(push_command)
    return push_sequence


class BoulderTransition:
    """
    This object defines transitions between (boulder location, player location) states.
    The boulder in question is a single active boulder that has been removed from the level.
    One of these objects should be created for each active boulder.
    """
    def __init__(self, rect, level, floor_neighbors, location_to_back_front_pairs):
        self.level = level
        self.rect = rect
        self.location_to_back_front_pairs = location_to_back_front_pairs
        self.manhattan_transition = ManhattanTransition(rect, level, floor_neighbors)
        # maps a (boulder location, player location) state to the set of reachable boulder side locations
        self.side_cache = {}
    def __call__(self, source):
        """
        Interesting moves include pushing the boulder and moving to a different side of the boulder to push it.
        """
        boulder_location, player_location = source
        # Keep a set of the next states to return at the end of the function.
        next_states = set()
        # Make sure that the state is valid.
        assert self.rect.is_inbounds(boulder_location)
        assert self.rect.is_inbounds(player_location)
        assert self.level[boulder_location] not in '0-|^', (boulder_location, self.level[boulder_location])
        assert self.level[player_location] not in '0-|^', (player_location, self.leve[player_location])
        # Put the boulder on the floor.
        self.level[boulder_location] = '0'
        # Keep a set of the locations we want to visit to push the boulder in a different direction.
        target_locations = set()
        # This set includes all target locations and may include the current location.
        all_desirable_sides = set()
        for back, front in self.location_to_back_front_pairs[boulder_location]:
            # You cannot push a boulder while standing on a trap or solid object.
            if self.level[back] in '0^':
                continue
            # You cannot push a boulder into a solid object
            if self.level[front] == '0':
                continue
            # At this point the boulder is pushable if we can get behind it.
            all_desirable_sides.add(back)
            if player_location == back:
                # If we are already behind it then add a boulder push to the list of next states.
                next_states.add((front, boulder_location))
            else:
                # Otherwise add the location behind the boulder to a list of places we want to reach.
                target_locations.add(back)
        # See which of the target locations we can reach while the boulder is on the floor.
        if target_locations:
            reachable_desirable_sides = self.side_cache.get(source, None)
            if not reachable_desirable_sides:
                reachable_desirable_sides = AscDP.flood_all_targets([player_location], all_desirable_sides, self.manhattan_transition)
            for back in reachable_desirable_sides:
                adjacent_state = (boulder_location, back)
                self.side_cache[adjacent_state] = reachable_desirable_sides
                if adjacent_state != source:
                    next_states.add(adjacent_state)
        # Take the boulder back off of the floor.
        self.level[boulder_location] = '.'
        return next_states


class RelaxedBoulderReverseTransition:
    """
    This transition defines a relaxation such that the player may teleport to floor squares.
    The states used for these transitions are simply boulder locations.
    Because this object considers a single boulder at a time, all other boulders are fixed.
    This relaxation helps to find potential targets and lower distance bounds for the more constrained problem.
    Calling this function object with a sink gives all sources that lead to that sink.
    """
    def __init__(self, rect, level, location_to_back_front_pairs):
        """
        The active boulder should be removed before calling this function.
        Walls and bounds have already been considered in location_to_back_front_pairs.
        """
        self.sink_to_sources = {}
        for source, back_front_pairs in location_to_back_front_pairs.items():
            # You cannot push a boulder off of a trap or solid object (the active boulder has been removed).
            if level[source] in ('0^'):
                continue
            for back, front in back_front_pairs:
                # You cannot push a boulder while standing on a trap or solid object.
                if level[back] in '0^':
                    continue
                # You cannot push a boulder into a solid object
                if level[front] == '0':
                    continue
                if front in self.sink_to_sources:
                    self.sink_to_sources[front].add(source)
                else:
                    self.sink_to_sources[front] = set([source])
    def __call__(self, sink):
        return self.sink_to_sources.get(sink, [])


class BoulderTransitionHeuristic:
    """
    One of these objects should be created for each active boulder.
    This function object basically guesses how close you are to finishing the boulder.
    """
    def __init__(self, rect, level, location_to_back_front_pairs):
        relaxed_reverse_transition = RelaxedBoulderReverseTransition(rect, level, location_to_back_front_pairs)
        relaxed_targets = set(loc for loc, c in level.items() if c == '^')
        self.boulder_location_to_lower_bound = AscDP.measure_all_states(relaxed_targets, relaxed_reverse_transition)
    def __call__(self, source):
        """
        @return: None if impossible, 0 if finished, otherwise and optimistic distance guess.
        """
        boulder_location, player_location = source
        return self.boulder_location_to_lower_bound.get(boulder_location, None)


class SlowNeighborTransition:
    """
    This is a simple but slow transition function that is not for inner loops.
    """
    def __init__(self, rect, passability_provider):
        self.passability_provider = passability_provider
        self.rect = rect
    def __call__(self, source):
        for sink in self.rect.gen_neighbors(source):
            if self.passability_provider.is_passable(source, sink):
                yield sink

class ManhattanTransition(Rect):
    """
    This transition function uses a lot of precomputation.
    One of these objects should be created for each active boulder.
    """
    def __init__(self, rect, level, floor_neighbors):
        Rect.__init__(self, rect.row_min, rect.col_min, rect.row_max, rect.col_max)
        self.level = level
        self.source_to_sinks = {}
        for source, potential_sinks in floor_neighbors.items():
            if level[source] not in '0^':
                sinks = [sink for sink in potential_sinks if level[sink] not in '0^']
                if sinks:
                    self.source_to_sinks[source] = sinks
    def __call__(self, source):
        potential_sinks = self.source_to_sinks.get(source, [])
        for sink in potential_sinks:
            if self.level[sink] != '0':
                yield sink

class SokoMap(Rect):
    """
    Use this class for running the demo but use a derived class when AI is needed.
    """
    def __init__(self, level_string, level_name):
        # this name is used for debugging and for logging boulder moves to a file
        self.name = level_name
        # initialize the map
        self.level = sokoban_string_to_map(level_string)
        row_max = max(row for row, col in self.level)
        col_max = max(col for row, col in self.level)
        # initialize the base class with the rectangle dimensions
        Rect.__init__(self, 0, 0, row_max, col_max)
        # the player starts on the down staircase
        start_locations = [loc for loc in self.gen_locations() if self.level[loc] == '>']
        assert len(start_locations) == 1
        self.player_location = start_locations[0]
        # replace stairs and doors with floor
        for loc in self.gen_locations():
            if self.level[loc] in list('<>+'):
                self.level[loc] = '.'

    def on_boulder_push(self, old_player_location, new_player_location):
        """
        Do not do anything special when a boulder has been pushed.
        """
        pass

    def move_player(self, delta):
        """
        @param delta: the (row, col) offset from the current location of the player
        @param is_controlled: False if the movement under user control instead of auto control
        This is the only place the player location is changed after initialization.
        Manual and automated commands both go through this function.
        """
        row, col = self.player_location
        drow, dcol = delta
        new_player_location = (row + drow, col + dcol)
        # If the move was a single diagonal move then make sure it is valid.
        # This check disallows squeezing between solid dungeon features.
        if drow in (-1, 1) and dcol in (-1, 1):
            if not self.is_passable(self.player_location, new_player_location):
                return False
        # If the move would go out of bounds then do not allow the move.
        if not self.is_inbounds(new_player_location):
            return False
        # See what glyph the player hopes to land on.
        target_glyph = self.level[new_player_location]
        # If the glyph is a wall or a trap then do not allow the move.
        if target_glyph in '-|^':
            return False
        # See if we pushed a boulder.
        # Boulders can be pushed only by a single cardinal step.
        if (drow, dcol) in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if self.level[new_player_location] == '0':
                new_boulder_location = (row + drow*2, col + dcol*2)
                # We are not allowed to push a boulder off the map.
                if not self.is_inbounds(new_boulder_location):
                    return False
                # See what glyph the boulder hopes to land on.
                boulder_target_glyph = self.level[new_boulder_location]
                # We are not allowed to push the boulder into a wall or another boulder.
                if self.level[new_boulder_location] in '-|0':
                    return False
                # At this point the boulder push is a success.
                self.level[new_player_location] = '.'
                # A boulder is added to the new boulder location or a trap is filled.
                if boulder_target_glyph == '^':
                    self.level[new_boulder_location] = '.'
                else:
                    self.level[new_boulder_location] = '0'
                # Log the boulder pushing event.
                self.on_boulder_push(self.player_location, new_player_location)
        # At this point the player move is a success.
        self.player_location = new_player_location
        return True

    def is_passable(self, loca, locb):
        """
        Is there a distance of 1 between these two locations?
        Pushing a boulder is not allowed for this calculation.
        """
        rowa, cola = loca
        rowb, colb = locb
        drow = rowb - rowa
        dcol = colb - cola
        # each location must be in bounds
        if not self.is_inbounds(loca):
            return False
        if not self.is_inbounds(locb):
            return False
        # Each location must be floor.
        # Do not let the player walk on a trap.
        if self.level[loca] in '0-|^':
            return False
        if self.level[locb] in '0-|^':
            return False
        # the locations must be neighbors
        if drow not in (-1, 0, 1):
            return False
        if dcol not in (-1, 0, 1):
            return False
        if (drow, dcol) == (0, 0):
            return False
        # if the locations are diagonal from each other
        # then make sure we are not trying to squeeze through a crack
        if drow in (-1, 1) and dcol in (-1, 1):
            locw = (rowa, colb)
            locz = (rowb, cola)
            if self.level[locw] in '-|0' and self.level[locz] in '-|0':
                return False
        # if all of these tests have been passed then the way is passable
        return True

    def is_solved(self):
        return not set(loc for loc, c in self.level.items() if c == '^')

    def gen_ascii_lines(self):
        """
        Get the ascii lines representing the screen.
        """
        for row in self.gen_rows():
            yield ''.join(self.level[(row, col)] for col in self.gen_cols())

    def draw_to_curses_screen(self, scr):
        """
        Draw the map on a curses screen.
        The caller should refresh after having called this function.
        """
        # draw the map
        for i, line in enumerate(self.gen_ascii_lines()):
            scr.addstr(i, 0, line)
        # draw the player
        player_row, player_col = self.player_location
        scr.addstr(player_row, player_col, '@')
        # set the cursor to the player
        scr.move(player_row, player_col)


class ActiveSokoMap(SokoMap):
    """
    This derived class adds caching for the AI.
    """
    def __init__(self, level_string, level_name):
        SokoMap.__init__(self, level_string, level_name)
        # log boulder pushes
        self.push_list = []
        # cache the non-wall manhattan neighbors of each non-wall square
        self.floor_neighbors = {}
        for location in self.gen_locations():
            if self.level[location] not in '-|':
                neighbors = []
                for neighbor in self.gen_manhattan_neighbors(location):
                    if self.level[neighbor] not in '-|':
                        neighbors.append(neighbor)
                if neighbors:
                    self.floor_neighbors[location] = neighbors
        # cache some ways of pushing a boulder
        self.location_to_back_front_pairs = {}
        for location in self.gen_locations():
            if self.level[location] not in '-|':
                srow, scol = location
                pairs = []
                for drow, dcol in ((0,1),(1,0)):
                    side_a = (srow - drow, scol - dcol)
                    side_b = (srow + drow, scol + dcol)
                    for pair in ((side_a, side_b), (side_b, side_a)):
                        back, front = pair
                        if not self.is_inbounds(back):
                            continue
                        if not self.is_inbounds(front):
                            continue
                        if self.level[back] in '-|':
                            continue
                        if self.level[front] in '-|':
                            continue
                        pairs.append(pair)
                if pairs:
                    self.location_to_back_front_pairs[location] = pairs
        # there is no good path known
        self.traceback = None
        # initialize the traceback
        self.invalidate()

    def on_boulder_push(self, old_player_location, new_player_location):
        """
        Boulder pushes are defined by the movement of the player,
        not the movement of the boulder.
        """
        old_row, old_col = old_player_location
        new_row, new_col = new_player_location
        args = (old_row, old_col, new_row, new_col)
        self.push_list.append(args)

    def notify_success(self):
        """
        This should be called when the level has been completed so that the boulder pushes can be written to a file.
        To redo a level delete the corresponding file manually and run this script again.
        """
        filename = '%s.soko' % self.name
        self.logfile = open(filename, 'w')
        for args in self.push_list:
            print >> self.logfile, '%d\t%d\t%d\t%d' % args

    def process_command(self, command):
        """
        The special command '.' makes the AI take over for a single turn.
        """
        if command == '.':
            return self.auto_command_finish()
        else:
            return self.process_command_move(command)

    def invalidate(self):
        """
        A boulder has been moved so the traceback must be recalculated.
        """
        # calling this function means something has caused the old traceback to become invalid
        self.traceback = None
        # see where the boulders are
        boulder_locations = [loc for loc, c in self.level.items() if c == '0']
        # create solvers associated with boulder locations
        pq = []
        distance_solver_location_triples = []
        for boulder_location in boulder_locations:
            self.level[boulder_location] = '.'
            boulder_transition = BoulderTransition(self, self.level, self.floor_neighbors, self.location_to_back_front_pairs)
            boulder_heuristic = BoulderTransitionHeuristic(self, self.level, self.location_to_back_front_pairs)
            initial_state = (boulder_location, self.player_location)
            solver = AscDP.MeasureInformedTraceback([initial_state], boulder_transition, boulder_heuristic)
            solver.step()
            self.level[boulder_location] = '0'
            distance = solver.get_distance()
            if distance is not None:
                heappush(pq, (distance, solver, boulder_location))
        # Keep going until a solver has finished or until they have all failed to find a solution.
        best_path = None
        while pq:
            distance, solver, boulder_location = heappop(pq)
            solution = solver.get_solution()
            if solution:
                best_path = AscDP.traceback_to_path(*solution)
                break
            self.level[boulder_location] = '.'
            solver.step()
            self.level[boulder_location] = '0'
            distance = solver.get_distance()
            if distance is not None:
                heappush(pq, (distance, solver, boulder_location))
        # Set the path if one was found.
        if best_path:
            # Convert the path to boulder pushes.
            assert len(best_path) > 1
            self.traceback = []
            for (new_boulder, new_player), (old_boulder, old_player) in zip(best_path[0:-1], best_path[1:]):
                if new_boulder != old_boulder:
                    self.traceback.append((new_player, old_player))

    def auto_command_finish(self):
        # If the traceback does not exist then it means the bot has not found a path.
        if not self.traceback:
            return False
        new_player, old_player = self.traceback[-1]
        if self.player_location == old_player:
            # Push the boulder.
            proximal = new_player
            self.traceback.pop()
        else:
            # Move next to the boulder.
            slow_neighbor_transition = SlowNeighborTransition(self, self)
            loc_to_dist = AscDP.measure_all_targets([old_player], [self.player_location], slow_neighbor_transition)
            assert self.player_location in loc_to_dist, error_message
            path = AscDP.get_path(self.player_location, slow_neighbor_transition, loc_to_dist)
            assert len(path) > 1, error_message
            proximal = path[1]
        row, col = self.player_location
        nrow, ncol = proximal
        drow = nrow - row
        dcol = ncol - col
        delta = (drow, dcol)
        move_result = self.move_player(delta)
        if not self.traceback:
            self.invalidate()
        return move_result

    def process_command_move(self, command):
        delta = dict(vi_delta_pairs).get(command, None)
        if not delta:
            return False
        old_push_count = len(self.push_list)
        move_result = self.move_player(delta)
        new_push_count = len(self.push_list)
        if old_push_count != new_push_count:
            self.invalidate()
        return move_result

    def draw_to_curses_screen(self, scr):
        """
        Draw the map on a curses screen.
        The caller should refresh after having called this function.
        """
        # draw the map
        SokoMap.draw_to_curses_screen(self, scr)
        # get the player location
        player_row, player_col = self.player_location
        # if we can push a boulder then add some flair
        if self.traceback:
            (boulder_row, boulder_col), next_player_target = self.traceback[-1]
            scr.addstr(boulder_row, boulder_col, '0', curses.A_BOLD)
            scr.addstr(player_row, player_col, '@', curses.A_BOLD)
        # set the cursor to the player
        scr.move(player_row, player_col)


def do_curses_demo(stdscr):
    # do not wait for a keypress when using getch()
    stdscr.nodelay(1)
    # create the subscreen to leave room at the top for a message
    sokoban_screen = stdscr.subpad(1, 0)
    # solve each level
    for level_string, level_name in all_level_strings_and_names:
        # load the list of boulder pushes from the file
        push_list = load_push_sequence(level_name)
        # all of the soko files should exist when this function is called
        assert push_list
        # load the level
        level = SokoMap(level_string, level_name)
        # show the level name on the top row
        stdscr.addstr(0, 0, level_name)
        stdscr.refresh()
        # play the level automatically
        push_index = 0
        while True:
            # quit if a key is pressed during the demo
            # note that getch() usually waits for a keypress,
            # but this has been disabled on stdscr by the nodelay(1) call.
            if stdscr.getch() != -1:
                return
            # show the initial move or the result of the last move
            level.draw_to_curses_screen(sokoban_screen)
            sokoban_screen.refresh()
            # pause between animation frames
            time.sleep(.1)
            # if we win then go to the next level
            if level.is_solved():
                break
            # are we at the square that allows us to push yet?
            rowa, cola, rowb, colb = push_list[push_index]
            drow = rowb - rowa
            dcol = colb - cola
            target_player_location = (rowa, cola)
            player_location = level.player_location
            if player_location == target_player_location:
                # push the boulder
                delta = (drow, dcol)
                level.move_player(delta)
                push_index += 1
            else:
                # move the player in the direction of the target player location
                slow_neighbor_transition = SlowNeighborTransition(level, level)
                loc_to_dist = AscDP.measure_all_targets([target_player_location], [level.player_location], slow_neighbor_transition)
                path = AscDP.get_path(level.player_location, slow_neighbor_transition, loc_to_dist)
                best_loc = path[1]
                row, col = player_location
                nrow, ncol = best_loc
                delta = (nrow - row, ncol - col)
                level.move_player(delta)
        # clear the screen to prepare to show the new level map and map name
        stdscr.clear()
        stdscr.refresh()

def do_curses_main(stdscr, unfinished_level_strings_and_names):
    # create the subscreen to leave room at the top for a message
    sokoban_screen = stdscr.subpad(1, 0)
    # keep track of which level we are on and how many levels there are
    level_index = 0
    nlevels = len(unfinished_level_strings_and_names)
    # keep playing levels
    while True:
        level_string, level_name = unfinished_level_strings_and_names[level_index]
        level = ActiveSokoMap(level_string, level_name)
        stdscr.addstr(0, 0, level_name)
        stdscr.refresh()
        # keep playing a level
        while True:
            level.draw_to_curses_screen(sokoban_screen)
            sokoban_screen.refresh()
            if level.is_solved():
                # log the important moves
                level.notify_success()
                # remove the level from the list of unfinished levels
                del unfinished_level_strings_and_names[level_index]
                nlevels = len(unfinished_level_strings_and_names)
                level_index = min(level_index, nlevels - 1)
                # see if all of the levels have been completed
                if not nlevels:
                    stdscr.addstr(0, 0, 'You win!  Press any key.')
                    stdscr.getch()
                    return
                stdscr.addstr(0, 0, 'Level completed.  Press any key.')
                stdscr.getch()
                break
            command = chr(sokoban_screen.getch())
            if command == 'q':
                return
            elif command == 'r':
                break
            elif command == '>':
                level_index += 1
                level_index %= nlevels
                break
            elif command == '<':
                level_index -= 1
                level_index %= nlevels
                break
            else:
                level.process_command(command)
        stdscr.clear()
        stdscr.refresh()


def do_curses(stdscr):
    # which levels still need to be completed?
    unfinished_level_strings_and_names = []
    for level_string, level_name in all_level_strings_and_names:
        filename = '%s.soko' % level_name
        if not os.path.exists(filename):
            unfinished_level_strings_and_names.append((level_string, level_name))
    # if there are no levels on startup then run a demo
    if not unfinished_level_strings_and_names:
        do_curses_demo(stdscr)
    else:
        do_curses_main(stdscr, unfinished_level_strings_and_names)

def verify_letter_set():
    """
    Verify that only valid letters are present in the level strings.
    """
    letters = ' |-0<>.+^'
    for level_string, level_name in all_level_strings_and_names:
        lines = [line.rstrip() for line in StringIO.StringIO(level_string)]
        for letter in ''.join(lines):
            assert letter in letters

def verify_start_locations():
    """
    Verify the presence and uniqueness of the start location on each level.
    """
    for level_string, level_name in all_level_strings_and_names:
        lines = [line.rstrip() for line in StringIO.StringIO(level_string)]
        assert ''.join(lines).count('>') == 1

def run():
    try:
        global curses
        import curses
    except ImportError, e:
        print 'Import error: %s.' % str(e)
        print 'The python curses module may not be installed or even exist for your operating system.'
        print 'Your operating system is %s.' % os.name
        return
    verify_letter_set()
    verify_start_locations()
    curses.wrapper(do_curses)

if __name__ == '__main__':
    run()
    #profile.run('run()')



