import random

from AscLevelConstants import *

from AscAnsi import Ansi, AnsiSquare
from AscMonster import MonsterHistory
from AscWallSearch import WallSearch
from AscUtil import distL1, distLinf, get_bounding_coordinates, vi_delta_pairs, Rect
import AscSokoban
import AscDetect

class ItemHistory:
    """
    This class is analogous to MonsterHistory,
    except it deals with items instead of monsters.
    It is less sophisticated because items tend to be less mobile and aggressive.
    This might eventually include the inventory of each square.
    """
    def __init__(self, ansi_square):
        newansi = ansi_square.copy()
        self.ansi_square = newansi
        self.exploration_level = EXP_UNEXPLORED
    def is_explored(self):
        return (self.exploration_level == EXP_EXPLORED)
    def set_explored(self):
        self.exploration_level = EXP_EXPLORED

    def get_connected_regions(self, force_safe = False):
        """
        Returns a list of regions that are connected to the player region.
        Danger is disregarded for now.
        """
        shell = [self]
        connected_regions = [self]
        while shell:
            new_shell = []
            for region in shell:
                if force_safe:
                    neighbors_and_distances = list(region.gen_safe_neighbors_and_distances())
                else:
                    neighbors_and_distances = list(region.gen_neighbors_and_distances())
                for neighbor, distance in neighbors_and_distances:
                    if neighbor not in connected_regions:
                        connected_regions.append(neighbor)
                        new_shell.append(neighbor)
            shell = new_shell
        return connected_regions

    def get_best_neighbor_region(self):
        """
        Return the neighboring region that is closest to the
        shallowest connected unexplored region.
        If there is no such region or if the player's region is best then return None.
        If the current region is best return None.
        This function does not allow traversal of suicidally dangerous links.
        """
        verbose = True
        if verbose:
            self.remark('get_best_neighbor_region')
        # First get the list of target levels without regard to distance.
        connected_regions = self.get_safe_connected_regions()
        if verbose:
            self.remark('%d safely connected regions:' % len(connected_regions))
            for region in connected_regions:
                self.remark(str(region))
        unexplored_regions = [r for r in connected_regions if r.exploration_level == EXP_UNEXPLORED and r.exploration_danger_level == DANGER_SAFE]
        if verbose:
            self.remark('%d safely unexplored safely connected regions:' % len(unexplored_regions))
            for region in unexplored_regions:
                self.remark(str(region))
        if not unexplored_regions:
            return None
        shallowest_dlvl = min(r.level.level_dlvl for r in unexplored_regions)
        target_regions = [r for r in unexplored_regions if r.level.level_dlvl == shallowest_dlvl]
        if verbose:
            self.remark('%d target regions:' % len(target_regions))
            for region in target_regions:
                self.remark(str(region))
        if self in target_regions:
            return None
        return self.get_best_neighbor_region_helper(connected_regions, target_regions)

    def get_best_neighbor_region_desperate(self):
        """
        Return the neighboring region that is closest to a region that may need thorough exploration.
        If there is no such region or if the path is too dangerous then return None
        If the current region is best return None.
        This function does not allow traversal of suicidally dangerous links.
        """
        self.remark('get_best_neighbor_region_desperate')
        # Get the list of regions that are connected to this region.
        connected_regions = self.get_safe_connected_regions()
        if not connected_regions:
            self.remark('no safely connected regions')
            return None
        self.remark('%d safely connected regions:' % len(connected_regions))
        for region in connected_regions:
            self.remark(str(region))
        # Of the connected regions, get the list of regions that are in the doom branch or an unknown branch or minetown.
        filtered_connected_regions = []
        for region in connected_regions:
            if region.level.level_branch in (LEVEL_BRANCH_UNKNOWN, LEVEL_BRANCH_DOOM) or region.level.level_special == LEVEL_SPECIAL_MINETOWN:
                filtered_connected_regions.append(region)
        if not filtered_connected_regions:
            self.remark('none of these regions are in the appropriate branch or special level')
            return None
        self.remark('of these regions %d were in an appropriate branch or special level:' % len(filtered_connected_regions))
        for region in filtered_connected_regions:
            self.remark(str(region))
        # Of the remaining interesting regions get the ones that are not adjacent to a region with down stairs.
        target_regions = []
        for region in filtered_connected_regions:
            has_adjacent_stair_down = False
            for adjacent_region, distance in region.gen_safe_neighbors_and_distances():
                if adjacent_region.region_type == REGION_DOWN:
                    has_adjacent_stair_down = True
            if not has_adjacent_stair_down:
                target_regions.append(region)
        if not target_regions:
            self.remark('all of these regions are safely connected to a down stair region on the same level')
            return None
        self.remark('of these regions %d are not safely connected to a down stair region on the same level:' % len(target_regions))
        for region in target_regions:
            self.remark(str(region))
        # if our own region is a target region then return None
        if self in target_regions:
            return None
        # return the neighbor region on the path to the closest target region
        return self.get_best_neighbor_region_helper(connected_regions, target_regions)

    def get_best_neighbor_region_helper(self, connected_regions, target_regions):
        """
        This is a helper function that should be called by one of:
        {get_best_neighbor_region, get_best_neighbor_region_desperate}
        Given a list of target regions it finds the adjacent region closest to the nearest target region.
        """
        # Now find the closest of these regions.
        # Use a cheesy best first search with an inefficient priority queue.
        region_id_to_distance = dict((id(r), 0) for r in target_regions)
        regions_and_distances = [(r, 0) for r in target_regions]
        while len(regions_and_distances) < len(connected_regions):
            # get the shell of all neighbors and their distances
            distances_and_neighbors = []
            for region, distance in regions_and_distances:
                for neighbor, ddist in region.gen_neighbors_and_distances():
                    if id(neighbor) not in region_id_to_distance:
                        distances_and_neighbors.append((distance + ddist, neighbor))
            # add the closest neighbor of the entire shell
            best_distance, best_neighbor = min(distances_and_neighbors)
            region_id_to_distance[id(best_neighbor)] = best_distance
            regions_and_distances.append((best_neighbor, best_distance))
        # Determine which neighboring region to approach.
        # This is like traceback.
        distance_and_neighbor = [(region_id_to_distance[id(r)], r) for r, d in self.gen_neighbors_and_distances()]
        best_distance, best_neighbor = min(distance_and_neighbor)
        return best_neighbor


class LevelSquare:
    def __init__(self):
        # where is the square?
        self.loc = None
        # what is the type of the square?
        self.hard = HM_UNKNOWN
        # is graffiti known to be on the square?
        self.graffiti = False
        # has the square been stepped on by the player?
        self.trod = False
        # is the square in a store?
        self.store = GM_NONE
        # how many searches have been done from this square?
        self.search_count_from = 0
        # how many searches have been done to this square?
        self.search_count_to = 0
        # what trap is on the square?
        self.trap = TRAP_UNKNOWN
        # what is the monster history of this square?
        self.monster = None
        # what is the item history of this square?
        self.item = None
        # cache the passable neighbor locations for speed
        self.passable_neighbor_locations = []
        # what are the names of the large containers dropped here?
        self.large_container_names = []
        # is there a boulder on the square?
        self.boulder = False


class Dungeon:
    def __init__(self):
        self.levels = []
        self.log = open('dungeon.log', 'w')
    def remark(self, s):
        print >> self.log, s
    def get_doom_fork_level(self):
        doom_fork_levels = []
        for level in self.levels:
            if level.level_special == LEVEL_SPECIAL_DOOM_FORK:
                doom_fork_levels.append(level)
        if not doom_fork_levels:
            return None
        if len(doom_fork_levels) == 1:
            return doom_fork_levels[0]
        else:
            self.remark('ERROR: %d levels were annotated as the special doom fork level' % len(doom_fork_levels))
            return None


class LevelMap(Rect):
    def __init__(self, dungeon):
        # define the rectangle within the ansi screen that contains the map
        Rect.__init__(self, 1, 0, 21, 78)
        self.dungeon = dungeon
        self.level_time = None
        self.level_dlvl = None
        self.level_branch = LEVEL_BRANCH_UNKNOWN
        self.level_special = LEVEL_SPECIAL_UNKNOWN
        self.sokoban_name = None
        self.sokoban_queue = None
        self.wall_type = WALL_TYPE_PLAIN
        self.regions = []
        self.region_links = []
        self.level = {}
        self.cached_interesting_locations = set()
        self.cached_neighbor_locations = {}
        self.cached_neighbor_locations_ortho = {}
        # init level squares
        for loc in self.gen_locations():
            square = LevelSquare()
            square.loc = loc
            self.level[loc] = square
        # init cached neighbor locations
        for loc in self.gen_locations():
            self.cached_neighbor_locations[loc] = tuple(self.gen_neighbors(loc))
            self.cached_neighbor_locations_ortho[loc] = tuple(self.gen_manhattan_neighbors(loc))


    def remark(self, s):
        self.dungeon.remark(s)

    def init_sokoban(self, ansi, level_name):
        """
        This level has been identified as a sokoban level.
        Initialize the sokoban level name.
        Initialize the queue of boulder pushes that should be executed.
        @param ansi: the ansi map of the level used to calibrate the sokoban push queue
        @param level_name: the name of the sokoban level, e.g. 'level_2b'
        """
        # Make sure that this level is not already initialized as a sokoban level.
        assert not self.sokoban_name
        assert not self.sokoban_queue
        # Initialize the name.
        self.sokoban_name = level_name
        # Define wall ascii symbols for the purpose of sokoban level detection.
        sokoban_wall_characters = ('-', '|')
        # Get the set of wall locations on the observed ansi map.
        raw_wall_locations = set()
        for loc in self.level:
            row, col = loc
            ansi_square = ansi.lines[row][col]
            if ansi_square.char in sokoban_wall_characters:
                raw_wall_locations.add(loc)
        # If this function was called there had better be some walls to identify.
        assert raw_wall_locations
        # Get the offset of the left and top walls.
        rmin, cmin, rmax, cmax = get_bounding_coordinates(raw_wall_locations)
        # Get the raw queue of moves for this level.
        raw_push_queue = AscSokoban.load_push_sequence(level_name)
        # Convert the queue of moves to account for the position of sokoban within the screen.
        self.sokoban_queue = []
        for player_row, player_col, boulder_row, boulder_col in raw_push_queue:
            args = (player_row + rmin, player_col + cmin, boulder_row + rmin, boulder_col + cmin)
            self.sokoban_queue.append(args)
        # Get the map representing the level so we can place the traps and boulders.
        sokomaps = []
        for sokoban_level_string, sokoban_level_name in AscSokoban.all_level_strings_and_names:
            if level_name == sokoban_level_name:
                sokomap = AscSokoban.sokoban_string_to_map(sokoban_level_string)
                sokomaps.append(sokomap)
        assert len(sokomaps) == 1
        sokomap = sokomaps[0]
        # Place the traps on the level.
        for loc, c in sokomap.items():
            if c == '^':
                row, col = loc
                trap_location = (row + rmin, col + cmin)
                self.level[trap_location].trap = TRAP_OTHER
        # Place the boulders on the level.
        for loc, c in sokomap.items():
            if c == '0':
                row, col = loc
                boulder_location = (row + rmin, col + cmin)
                self.level[boulder_location].boulder = True

    def get_sokoban_push_delta(self, current_player_location):
        """
        If we are in sokoban positioned next to a boulder that we are supposed to push then go for it.
        @return: a cardinal delta pair or None
        """
        # If we are not in sokoban then do not push a boulder.
        if self.level_branch != LEVEL_BRANCH_SOKOBAN:
            return None
        # If the sokoban puzzle has already been completed on this level then do not push a boulder.
        if not self.sokoban_queue:
            return None
        # Find the target square.
        player_row, player_col, boulder_row, boulder_col = self.sokoban_queue[0]
        target_player_location = (player_row, player_col)
        # If we are not on the target square then we cannot push the boulder.
        if current_player_location != target_player_location:
            return None
        # Calculate the direction to push it.
        drow = boulder_row - player_row
        dcol = boulder_col - player_col
        delta = (drow, dcol)
        return delta

    def identify_embedded(self, ansi, target_location):
        """
        @param target_location: this is the square containing the embedded object
        """
        # Pretend the target square is a wall.
        # This may be true but it could also be a door.
        row, col = target_location
        ansi_square = ansi.lines[row][col]
        level_square = self.level[target_location]
        level_square.hard = HM_WALL
        # Recognize that there is something shiny in the wall.
        level_square.item = ItemHistory(ansi_square)
        # Pretend we have already explored it so that it is no longer interesting.
        # This is true in the sense that we explored it with a semicolon.
        level_square.item.set_explored()

    def identify_trap(self, trap_location, trap_name):
        # TODO actually use the trap name
        self.remark('trap identification at %s' % str(trap_location))
        square = self.level[trap_location]
        if square.trap == TRAP_UNKNOWN:
            self.remark('identified trap {%s} at %s' % (trap_name, str(trap_location)))
            square.trap = TRAP_OTHER
        else:
            self.remark('trap {%s} at %s was already identified' % (trap_name, str(trap_location)))

    def add_missile(self, location):
        """
        Arrow traps and dart traps may leave missiles on the ground.
        Change the item history of the location in this case.
        Arrows and darts are cyan and are represented by the ')' character.
        """
        ansi_square = AnsiSquare()
        ansi_square.foreground = 36
        ansi_square.char = ')'
        self.level[location].item = ItemHistory(ansi_square)

    def add_rock(self, location):
        """
        Falling rock traps may leave rocks on the ground.
        Change the item history of the location in this case.
        Rocks are the default foreground color and are represented by the '*' character.
        """
        ansi_square = AnsiSquare()
        ansi_square.char = '*'
        self.level[location].item = ItemHistory(ansi_square)

    def gen_unidentified_trap_locations(self, ansi):
        for loc, level_square in self.level.items():
            row, col = loc
            ansi_square = ansi.lines[row][col]
            if ansi_square.char == '^':
                if level_square.trap == TRAP_UNKNOWN:
                    yield loc

    def gen_unidentified_remote_trap_locations(self, ansi):
        cursor_location = (ansi.row, ansi.col)
        for loc in self.gen_unidentified_trap_locations(ansi):
            if distLinf(cursor_location, loc) > 1:
                yield loc


    def explore_stairway(self):
        """
        Look for a stairway on the current level that is one of the following:
            1) unconfirmed
            2) unassociated with a region
            3) has an associated region with no target_region
        Once such a stairway has been found, return the location and best command to get there.
        The command may be to follow a staircase if the player is standing on it.
        Return None if no such staircase exists or can be reached.
        """
        player_region = self.get_player_region()
        target_locations = set()
        location_to_stair_region = dict((r.location, r) for r in self.regions if r.region_type in (REGION_UP, REGION_DOWN))
        # Look for regions on this level that do not have known targets.
        # If we are standing on such a stair then follow it.
        for location, region in location_to_stair_region.items():
            if not (region.region_type == REGION_UP and region.level.level_special == LEVEL_SPECIAL_TOP):
                if region.target_region is None:
                    if player_region.location == location:
                        if region.region_type == REGION_UP:
                            self.remark('ascending a staircase to see where it goes')
                            return '<'
                        else:
                            self.remark('descending a staircase to see where it goes')
                            return '>'
                    else:
                        target_locations.add(location)
        # Look for unconfirmed staircases.
        # If we are standing on unconfirmed stairs then look at the ground.
        # Look for confirmed stairs that are not associated with a region.
        for location, square in self.level.items():
            if square.hard in (HM_UP_UNCONFIRMED, HM_DOWN_UNCONFIRMED):
                if player_region.location == location:
                    self.remark('examining an unconfirmed staircase')
                    return ':'
                else:
                    target_locations.add(location)
            elif square.hard in (HM_UP_CONFIRMED, HM_DOWN_CONFIRMED):
                if location not in location_to_stair_region:
                    target_locations.add(location)
        # If we found no target locations then return None
        if not target_locations:
            self.remark('no interesting staircases were found')
            return None
        # Return the first step of the shortest path to a target if any path exists.
        target_set = set(target_locations)
        command = None
        # Try two levels of safety for the pathing.
        for safety, taboo_set in (('safely', self.cached_scary_locations), ('unsafely', self.cached_untouchable_locations)):
            loc_to_dist = self.get_location_evaluations(target_set, taboo_set)
            command = self.distances_to_command(player_region.location, loc_to_dist)
            if command:
                self.remark('moving %s across the level towards a staircase to explore' % safety)
                return command
        self.remark('no path or no non-suicidal path to an interesting staircase was found')
        return None

    def explore_travel(self):
        """
        Find the shallowest connected and unexplored region.
        If no such region can be found then return None.
        If the current level is unexplored and has the same dlvl as the found region then return None.
        Otherwise return a command to go towards the region.
        The command may be to follow a staircase if the player is standing on it.
        """
        player_region = self.get_player_region()
        best_neighbor_region = player_region.get_best_neighbor_region()
        if not best_neighbor_region:
            self.remark('no better level was found')
            return None
        # If the regions have the same location then follow the portal of the neighbor.
        if player_region.location == best_neighbor_region.location:
            if best_neighbor_region.region_type == REGION_UP:
                self.remark('going up a staircase seeking a better level')
                return '<'
            elif best_neighbor_region.region_type == REGION_DOWN:
                self.remark('going down a staircase seeking a better level')
                return '>'
            else:
                self.remark('inappropriate region type of the best neighbor: %d' % best_neighbor_region.region_type)
                return None
        # If the regions are on the same level then move towards the neighbor location.
        if player_region.level is best_neighbor_region.level:
            target_set = set([best_neighbor_region.location])
            # Try two levels of safety for the pathing.
            for safety, taboo_set in (('safely', self.cached_scary_locations), ('unsafely', self.cached_untouchable_locations)):
                loc_to_dist = self.get_location_evaluations(target_set, taboo_set)
                command = self.distances_to_command(player_region.location, loc_to_dist)
                if command:
                    self.remark('traveling %s across the map to a better region' % safety)
                    return command
            self.remark('no path or no non-suicidal path to a better region was found')
            return None
        self.remark('the best neighbor region appears not to be a neighbor')
        return None

    def explore_square(self):
        """
        Find the closest connected interesting square on the level.
        If there is no such square then return None.
        """
        player_region = self.get_player_region()
        target_set = self.cached_interesting_locations
        # Try two levels of safety for the pathing.
        for safety, taboo_set in (('safely', self.cached_scary_locations), ('unsafely', self.cached_untouchable_locations)):
            loc_to_dist = self.get_location_evaluations(target_set, taboo_set)
            command = self.distances_to_command(player_region.location, loc_to_dist)
            if command:
                self.remark('traveling %s across the map to an unexplored square' % safety)
                return command
        self.remark('no path or no non-suicidal path to an unexplored square was found')
        return None

    def explore_travel_desperate(self):
        """
        Go towards a room that must be searched in desperation.
        """
        player_region = self.get_player_region()
        best_neighbor_region = player_region.get_best_neighbor_region_desperate()
        if not best_neighbor_region:
            self.remark('no better level was found')
            return None
        # If the regions have the same location then follow the portal of the neighbor.
        if player_region.location == best_neighbor_region.location:
            if best_neighbor_region.region_type == REGION_UP:
                self.remark('going up a staircase desperately seeking a better level')
                return '<'
            elif best_neighbor_region.region_type == REGION_DOWN:
                self.remark('going down a staircase desperately seeking a better level')
                return '>'
            else:
                self.remark('inappropriate region type of the best neighbor: %d' % best_neighbor_region.region_type)
                return None
        # If the regions are on the same level then move towards the neighbor location.
        if player_region.level is best_neighbor_region.level:
            target_set = set([best_neighbor_region.location])
            # Try two levels of safety for the pathing.
            for safety, taboo_set in (('safely', self.cached_scary_locations), ('unsafely', self.cached_untouchable_locations)):
                loc_to_dist = self.get_location_evaluations(target_set, taboo_set)
                command = self.distances_to_command(player_region.location, loc_to_dist)
                if command:
                    self.remark('traveling and %s across the map to a better region' % safety)
                    return command
            self.remark('no path or no non-suicidal path to a better region was found')
            return None
        self.remark('the best neighbor region appears not to be a neighbor')
        return None

    def explore_square_desperate(self):
        """
        There is nothing to do but to search desperately for a secret door.
        """
        # Get the set of wall locations that are good for searching.
        wall_search = WallSearch(self)
        good_wall_locations = wall_search.good_wall_locations
        if not good_wall_locations:
            self.remark('no squares with potential secret doors were found')
            return None
        self.remark('%d wall squares might have secret doors' % len(good_wall_locations))
        # Narrow down this set by removing those locations that have been thoroughly searched.
        filtered_wall_locations = set()
        for wall_location in good_wall_locations:
            wall_square = self.level[wall_location]
            if wall_square.search_count_to < 18:
                filtered_wall_locations.add(wall_location)
        if not good_wall_locations:
            self.remark('all of the squares with potential secret doors have been thoroughly searched')
            return None
        self.remark('%d walls with potential secret doors have not been thoroughly searched' % len(filtered_wall_locations))
        # Get the locations adjacent to the remaining walls.
        target_set = set()
        for wall_location in filtered_wall_locations:
            for neighbor in self.cached_neighbor_locations[wall_location]:
                target_set.add(neighbor)
        # Find the player location.
        player_region = self.get_player_region()
        # See if we are already there.
        if player_region.location in target_set:
            self.remark('we are at a good square to search desperately for a secret door')
            return None
        # Try two levels of safety for the pathing.
        for safety, taboo_set in (('safely', self.cached_scary_locations), ('unsafely', self.cached_untouchable_locations)):
            loc_to_dist = self.get_location_evaluations(target_set, taboo_set)
            command = self.distances_to_command(player_region.location, loc_to_dist)
            if command:
                self.remark('traveling %s across the map to a square to search desperately' % safety)
                return command
        self.remark('no path or no non-suicidal path to square to search desperately was found')
        return None

    def distances_to_command(self, location, loc_to_dist):
        """
        Given the location of the player and costs of various squares,
        return the command that moves the player towards the lowest cost square.
        Return None if there is no path.
        """
        row, col = location
        deltas = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0)]
        ortho_deltas = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        dist_delta_pairs = []
        for delta in deltas:
            drow, dcol = delta
            nloc = (row+drow, col+dcol)
            if self.is_inbounds(nloc):
                if self.is_passable(location, nloc):
                    if nloc in loc_to_dist:
                        dist_delta_pairs.append((loc_to_dist[nloc], delta))
        if dist_delta_pairs:
            # find the best distance
            best_dist, best_delta = min(dist_delta_pairs)
            # find all deltas that are as good as the best delta
            best_deltas = [delta for dist, delta in dist_delta_pairs if dist == best_dist]
            # of these pick an ortho move if possible
            best_ortho_deltas = [delta for delta in best_deltas if delta in ortho_deltas]
            # return a somewhat randomized choice
            if best_ortho_deltas:
                selected_delta = random.choice(best_ortho_deltas)
            else:
                selected_delta = random.choice(best_deltas)
            delta_to_vi = dict((delta, vi) for (vi, delta) in vi_delta_pairs)
            return delta_to_vi[selected_delta]
        else:
            return None

    def get_player_region(self):
        player_regions = [region for region in self.regions if region.region_type == REGION_PLAYER]
        if not player_regions:
            return None
        assert len(player_regions) < 2
        return player_regions[0]

    def cache_scary_locations(self):
        player_region = self.get_player_region()
        self.cached_scary_locations = self.get_scary_locations() - set([player_region.location])

    def cache_untouchable_locations(self):
        player_region = self.get_player_region()
        self.cached_untouchable_locations = self.get_untouchable_locations() - set([player_region.location])

    def cache_passable_neighbor_locations(self):
        empty_states = (HM_OPEN, HM_FLOOR, HM_OCCUPIABLE, HM_ALTAR, HM_UP_CONFIRMED, HM_DOWN_CONFIRMED, HM_UP_UNCONFIRMED, HM_DOWN_UNCONFIRMED)
        for location, square in self.level.items():
            # clear the current cache value at this square
            square.passable_neighbor_locations = []
            # see if the location itself is even accessible
            if square.hard not in empty_states:
                continue
            for neighbor in self.cached_neighbor_locations[location]:
                # see if the neighbor is accessible
                neighbor_square = self.level[neighbor]
                if neighbor_square.hard not in empty_states:
                    continue
                # see if the path between the neighbors is allowed
                if self.is_passable(location, neighbor):
                    square.passable_neighbor_locations.append(neighbor)

    def process_incoming(self, ansi, player_status):
        """
        Look at the map and update what we know about the level.
        The cursor should be on the player tile.
        """
        cursor_location = (ansi.row, ansi.col)
        # look at the features of the map if we are not blind
        if not player_status.blind:
            self.update_hardmap(ansi)
        # cache the passable neighbor locations of each square
        self.cache_passable_neighbor_locations()
        # look for traps
        self.update_traps(ansi)
        # update the monster and item status on the map
        # it is still useful if blind or hallu
        self.update_softmap(ansi, player_status)
        # mark our presence on a square
        self.level[cursor_location].trod = True
        # update the regions in the level
        self.update_regions(cursor_location)
        # cache squares that we would rather not visit
        self.cache_scary_locations()
        self.cache_untouchable_locations()
        # update the connections between regions
        self.update_region_links()
        # cache the set of interesting locations
        self.cached_interesting_locations = self.get_interesting_locations()
        # update the exploration status of each region
        self.update_region_exploration_levels()
        # update our knowledge of the level type
        self.update_level_type(ansi)

    def update_level_type(self, ansi):
        """
        Look at the map to see if that helps us to decide which level type we are on.
        """
        # get level identification information from the pattern of the wall glyphs
        if self.wall_type == WALL_TYPE_PLAIN:
            if AscDetect.detect_cavern_walls(self, ansi):
                self.wall_type = WALL_TYPE_CAVERN
                if self.level_branch == LEVEL_BRANCH_UNKNOWN:
                    self.level_branch = LEVEL_BRANCH_MINES
                    self.remark('marked the current level as belonging to the mines branch')
        # get level identification information from the presence of a door
        if AscDetect.detect_doors(self, ansi):
            if self.level_branch == LEVEL_BRANCH_MINES:
                if self.level_special == LEVEL_SPECIAL_UNKNOWN:
                    self.level_special = LEVEL_SPECIAL_MINETOWN
                    self.remark('marked the current level as minetown')
            elif self.level_branch == LEVEL_BRANCH_UNKNOWN:
                self.level_branch = LEVEL_BRANCH_DOOM
                self.remark('marked the current level as belonging to the dungeons of doom branch')
        # get level identification information from the number of stairs
        down_regions = [r for r in self.regions if r.region_type == REGION_DOWN]
        if len(down_regions) == 2:
            # This level must be where the mines split from the dungeon of doom.
            # Assert various level properties.
            if self.level_branch == LEVEL_BRANCH_MINES:
                self.remark('WARNING: found two down regions in the mines' % len(down_regions))
            if self.level_dlvl not in (2, 3, 4):
                self.remark('WARNING: found two down regions on dlvl %d' % self.level_dlvl)
            if self.level_special not in (LEVEL_SPECIAL_UNKNOWN, LEVEL_SPECIAL_DOOM_FORK):
                self.remark('WARNING: found two down regions in special level %d' % self.level_special)
            # Set this level to the doom fork.
            if self.level_special != LEVEL_SPECIAL_DOOM_FORK:
                self.remark('marked the current level as the level at which the dungeon of doom and the mines split')
            self.level_branch = LEVEL_BRANCH_DOOM
            self.level_special = LEVEL_SPECIAL_DOOM_FORK
        elif len(down_regions) > 2:
            self.remark('WARNING: There are too many down regions: %d' % len(down_regions))

    def update_region_exploration_levels(self):
        """
        Find the exploration level associated with each region.
        This is done without regard to the danger of the path.
        """
        # Clear the exploration levels.
        for region in self.regions:
            region.exploration_level = EXP_UNKNOWN
            region.exploration_danger_level = DANGER_UNKNOWN
        # Try to go to squares that might give exploration information.
        interesting_locations = self.cached_interesting_locations
        # First look at exploration that can be done without suicidal danger.
        taboo_set = self.cached_untouchable_locations
        loc_to_dist = self.get_location_evaluations(interesting_locations, taboo_set)
        for region in self.regions:
            if region.location in loc_to_dist:
                region.exploration_level = EXP_UNEXPLORED
                region.exploration_danger_level = DANGER_SAFE
        # If all of the regions are unexplored and safe then we are done.
        if len([r for r in self.regions if r.exploration_danger_level == DANGER_SAFE]) == len(self.regions):
            return
        # For the remaining regions try a more dangerous search.
        taboo_set = set()
        loc_to_dist = self.get_location_evaluations(interesting_locations, taboo_set)
        for region in self.regions:
            if region.exploration_level == EXP_UNKNOWN:
                if region.location in loc_to_dist:
                    region.exploration_level = EXP_UNEXPLORED
                    region.exploration_danger_level = DANGER_SUICIDAL
        # Any region that still lacks access to a square of interest is explored.
        for region in self.regions:
            if region.exploration_level == EXP_UNKNOWN:
                region.exploration_level = EXP_EXPLORED


    def update_region_links(self):
        """
        Find a path associated with each pair of regions.
        This is without regard to the danger of the path.
        Transitivity of links is assumed.
        Note that this transitivity helps speed but loses distance information.
        """
        self.region_links = []
        # add links of unknown danger level
        linked_regions = []
        for region in self.regions:
            # don't bother finding links to the sole unlinked region;
            # according to transitivity it is not linked to anything.
            if len(self.regions) == len(linked_regions) + 1:
                break
            # don't find links to a region that is already linked;
            # these links have been taken care of by transitivity
            if region in linked_regions:
                continue
            # find a clump of transitively linked regions
            contiguous_regions = []
            interesting_locations = set([region.location])
            taboo_locations = set()
            loc_to_dist = self.get_location_evaluations(interesting_locations, taboo_locations)
            for target in self.regions:
                if target.location in loc_to_dist:
                    contiguous_regions.append(target)
            # link all of the regions in the clump to each other
            for r1 in contiguous_regions:
                for r2 in contiguous_regions:
                    if r1 is not r2:
                        link = RegionLink()
                        link.danger_level = DANGER_UNKNOWN
                        link.distance = 10
                        link.region_pair = (r1, r2)
                        self.region_links.append(link)
            # extend the linked_regions to include the contiguous_regions
            linked_regions.extend(contiguous_regions)
        # see which links that include the player region are safe
        player_region = self.get_player_region()
        interesting_locations = set([player_region.location])
        taboo_locations = self.cached_untouchable_locations
        loc_to_dist = self.get_location_evaluations(interesting_locations, taboo_locations)
        for region in self.regions:
            if region is player_region:
                continue
            if region.location in loc_to_dist:
                for link in self.region_links:
                    r1, r2 = link.region_pair
                    if (r1 is player_region and r2 is region) or (r1 is region and r2 is player_region):
                        link.danger_level = DANGER_SAFE
        # links that include the player region and that haven't been marked safe are unsafe
        for link in self.region_links:
            if player_region in link.region_pair:
                if link.danger_level == DANGER_UNKNOWN:
                    link.danger_level = DANGER_SUICIDAL
        # print the links for debugging
        self.remark(('region ids on dlvl %d: ' % self.level_dlvl) + ' '.join(str(id(region)) for region in self.regions))
        self.remark('links:')
        for link in self.region_links:
            self.remark(str(link))

    def update_regions(self, cursor_location):
        """
        This updates all of the portal regions in a level and the player region.
        Portal regions and player regions may be added here.
        Portal regions are never deleted.
        Player regions are deleted when the player leaves the level, but that is not done here.
        The target_region of each region is set when a player changes level, but that is not done here.
        """
        self.remark('updating regions on dlvl %d' % self.level_dlvl)
        # Portal squares are not mutable, so assert that old non-player regions are still valid.
        for region in self.regions:
            hardmap = self.level[region.location].hard
            fails = False
            if region.region_type == REGION_UP and hardmap != HM_UP_CONFIRMED:
                fails = True
            if region.region_type == REGION_DOWN and hardmap != HM_DOWN_CONFIRMED:
                fails = True
            if fails:
                self.remark('ERROR: the following region is located at hardmap symbol %d:' % hardmap)
                self.remark(str(region))
        # Identify new portal regions.
        old_up_regions = [region for region in self.regions if region.region_type == REGION_UP]
        old_down_regions = [region for region in self.regions if region.region_type == REGION_DOWN]
        new_locations_and_types = []
        for location, square in self.level.items():
            if square.hard == HM_UP_CONFIRMED:
                if location not in [region.location for region in old_up_regions]:
                    self.remark('creating a new REGION_UP in update_regions at location %s' % str(location))
                    new_locations_and_types.append((location, REGION_UP))
            elif square.hard == HM_DOWN_CONFIRMED:
                if location not in [region.location for region in old_down_regions]:
                    self.remark('creating a new REGION_DOWN in update_regions at location %s' % str(location))
                    new_locations_and_types.append((location, REGION_DOWN))
        for location, region_type in new_locations_and_types:
            region = Region()
            region.location = location
            region.level = self
            region.region_type = region_type
            region.target_region = None
            region.exploration_level = EXP_UNKNOWN
            region.exploration_danger_level = DANGER_UNKNOWN
            self.regions.append(region)
        # Find the player region, or create it if it does not exist.
        player_region = self.get_player_region()
        if not player_region:
            player_region = Region()
            player_region.level = self
            player_region.region_type = REGION_PLAYER
            player_region.target_region = None
            player_region.exploration_level = EXP_UNKNOWN
            player_region.exploration_danger_level = DANGER_UNKNOWN
            self.regions.append(player_region)
        # Update the player region with the current location.
        player_region.location = cursor_location

    def update_traps(self, ansi):
        for loc, level_square in self.level.items():
            # if you can see one of these characters,
            # then if you have stepped on the square we will say there is no trap.
            row, col = loc
            ansi_square = ansi.lines[row][col]
            if ansi_square.char in '.#{<>_':
                if level_square.trod and level_square.trap == TRAP_UNKNOWN:
                    level_square.trap = TRAP_NONE

    def update_hardmap(self, ansi):
        cursor_location = (ansi.row, ansi.col)
        # Process all locations including the player's location and neighboring locations.
        for loc, level_square in self.level.items():
            row, col = loc
            ansi_square = ansi.lines[row][col]
            value = None
            if ansi_square.char == ' ':
                pass
            elif ansi_square.char == '.':
                if ansi_square.foreground:
                    value = HM_OPEN
                else:
                    value = HM_FLOOR
            elif ansi_square.char == '{':
                value = HM_FLOOR
            elif ansi_square.char == '#':
                if ansi_square.foreground in (0, 37):
                    value = HM_FLOOR
                else:
                    value = HM_MISC_OBSTACLE
            elif ansi_square.char in 'IX':
                # These monsters might be in walls.
                pass
            elif ansi_square.char == '_':
                value = HM_ALTAR
            elif ansi_square.char == '<':
                # This might be a mimic
                if level_square.hard != HM_UP_CONFIRMED:
                    value = HM_UP_UNCONFIRMED
            elif ansi_square.char == '>':
                # This might be a mimic
                if level_square.hard != HM_DOWN_CONFIRMED:
                    value = HM_DOWN_UNCONFIRMED
            elif ansi_square.char in '|-':
                value = HM_WALL
            elif ansi_square.char == ']' and ansi_square.foreground == 33:
                # This might be a mimic
                # If the door is known to be unlocked or locked then don't change the state
                if level_square.hard not in (HM_LOCKED, HM_UNLOCKED):
                    value = HM_CLOSED
            elif ansi_square.char == '}':
                if ansi_square.foreground == 31:
                    value = HM_LAVA
                elif ansi_square.foreground == 34:
                    value = HM_WATER
            else:
                # Assume that any other item means an unknown square is occupiable.
                # This includes monsters and items.
                if level_square.hard == HM_UNKNOWN:
                    value = HM_OCCUPIABLE
            if value is not None:
                level_square.hard = value
            # Now deal with boulders on dungeon branches other than sokoban.
            if self.level_branch != LEVEL_BRANCH_SOKOBAN:
                level_square.boulder = (ansi_square.char == '0')
        # Reprocess locations adjacent to the player.
        neighbor_count = 0
        mapped_neighbor_count = 0
        for loc in self.cached_neighbor_locations[cursor_location]:
            neighbor_count += 1
            row, col = loc
            ansi_square = ansi.lines[row][col]
            level_square = self.level[loc]
            if ansi_square.char == ' ':
                if level_square.hard == HM_UNKNOWN:
                    if not level_square.boulder:
                        level_square.hard = HM_WALL
                        mapped_neighbor_count += 1
        #self.remark('player location: %s (%d)' % (str(ansi.get_location()), self.level[ansi.get_location()].hard))
        #self.remark('%d of %d neighbors were marked as invisible walls' % (mapped_neighbor_count, neighbor_count))

    def update_softmap(self, ansi, player_status):
        """
        Update the item and monster states.
        This function may be called while blind (to detect "I" monsters).

            )        A weapon of some sort.
            [        A suit or piece of armor.
            %        Something edible (not necessarily healthy).
            /        A wand.
            =        A ring.
            ?        A scroll.
            !        A potion.
            (        Some other useful object (pick-axe, key, lamp...)
            $        A pile of gold.
            *        A gem or rock (possibly valuable, possibly worthless).
            +        A closed door, or a spellbook
            "        An amulet.
        """
        item_symbols = ')[%/=?!($*+"'
        special_monster_symbols = ":;&@'"
        cursor_location = (ansi.row, ansi.col)
        # Update the monster history at all locations including the player's location and neighboring locations.
        for loc, level_square in self.level.items():
            row, col = loc
            ansi_square = ansi.lines[row][col]
            if ansi_square.char.isalpha() or ansi_square.char in special_monster_symbols:
                if level_square.monster and level_square.monster.ansi_square == ansi_square:
                    # if the square confirms the existing monster then update the monster history
                    level_square.monster.update(self.level_time)
                else:
                    # if the monster is new then replace the monster history
                    level_square.monster = MonsterHistory(self.level_time, ansi_square)
        # Update the item history at all locations including the player's location and neighboring locations.
        if (not player_status.blind) and (not player_status.hallu):
            for loc, level_square in self.level.items():
                row, col = loc
                ansi_square = ansi.lines[row][col]
                if (not level_square.boulder) and (not ansi_square.char.isalpha()) and (not ansi_square.char in special_monster_symbols):
                    # if there is no monster and we know what we are looking for and there is no boulder on the square then update the item history
                    if ansi_square.char in item_symbols:
                        if level_square.item and level_square.item.ansi_square == ansi_square:
                            # if the square already has the known item on it then it is boring
                            pass
                        else:
                            # if the square appears to have a new or different item then it is interesting
                            level_square.item = ItemHistory(ansi_square)
                    else:
                        level_square.item = None
        # Clear the monster history of the player's location.
        # Mark the item at the player's location as explored.
        player_square = self.level[cursor_location]
        player_square.monster = None
        if player_square.item:
            player_square.item.set_explored()
        # Clear the monster history at adjacent squares if no monster is observed.
        for loc in self.cached_neighbor_locations[cursor_location]:
            row, col = loc
            ansi_square = ansi.lines[row][col]
            if not (ansi_square.char.isalpha() or ansi_square.char in special_monster_symbols):
                self.level[loc].monster = None

    def is_dead_end(self, loc):
        """
        Dead ends are common places to find secret doors.
        After exploring a level it might be useful to search for secret doors.
        """
        if self.level[loc].hard in (HM_FLOOR, HM_OCCUPIABLE, HM_OPEN):
            wallcount = 0
            ortho_locations = set(self.cached_neighbor_locations_ortho[loc])
            for nloc in ortho_locations:
                if self.level[nloc].hard == HM_WALL:
                    wallcount += 1
            if wallcount == len(ortho_locations) - 1:
                return True
        return False

    def get_untouchable_locations(self):
        """
        Moving onto these squares is a fatal mistake.
        Such a mistake could include angering a shopkeeper or watchman.
        Going into a store will probably get you trapped inside.
        Falling through holes in sokoban will cause a loop.
        """
        # TODO improve dealing with shopkeepers
        # so the bot can enter a store without getting trapped.
        untouchable_set = set()
        for loc, square in self.level.items():
            monster = square.monster
            if monster:
                if monster.expect_presence(self.level_time):
                    if monster.is_untouchable():
                        untouchable_set.add(loc)
            if square.store in (GM_ENTRANCE, GM_STORE):
                untouchable_set.add(loc)
        # force traps to be untouchable in sokoban
        if self.level_branch == LEVEL_BRANCH_SOKOBAN:
            for loc, square in self.level.items():
                if square.trap not in (TRAP_NONE, TRAP_UNKNOWN):
                    untouchable_set.add(loc)
        return untouchable_set

    def get_scary_locations(self):
        """
        These locations are dangerous.
        They may be traversed when no alternative is available unless they are also untouchable.
        This set is a superset of untouchable locations.
        """
        scary_set = self.get_untouchable_locations()
        for loc, square in self.level.items():
            monster = square.monster
            if square.store in (GM_ENTRANCE, GM_STORE):
                scary_set.add(loc)
            elif square.trap not in (TRAP_NONE, TRAP_UNKNOWN):
                scary_set.add(loc)
            elif monster and monster.expect_presence(self.level_time):
                if monster.is_pet():
                    # Path through pets.
                    pass
                elif monster.is_scary(self):
                    # Avoid pathing through or near a scary monster.
                    scary_set.add(loc)
                    for nloc in self.cached_neighbor_locations[loc]:
                        scary_set.add(nloc)
                else:
                    # Avoid pathing through a monster even if it is not scary.
                    scary_set.add(loc)
        return scary_set

    def get_interesting_locations(self):
        """
        Reachable known squares next to closed or unlocked doors are interesting.
        Reachable known squares next to an unknown square not obscured by a boulder are interesting.
        Creature information is not taken into account here.
        An untrodden open door is always interesting because it might give a store message.
        An unexplored item square is interesting.
        In sokoban the square in front of the next boulder to push is interesting.
        """
        empty_states = (HM_OPEN, HM_FLOOR, HM_OCCUPIABLE, HM_ALTAR, HM_UP_CONFIRMED, HM_DOWN_CONFIRMED, HM_UP_UNCONFIRMED, HM_DOWN_UNCONFIRMED)
        interesting_set = set()
        for loc, square in self.level.items():
            if square.boulder:
                continue
            if square.hard not in empty_states:
                continue
            if (square.hard == HM_OPEN) and (not square.trod):
                interesting_set.add(loc)
                continue
            if square.item and (not square.item.is_explored()):
                interesting_set.add(loc)
            found_frontier = False
            for nloc in self.cached_neighbor_locations[loc]:
                nsquare = self.level[nloc]
                if nsquare.hard in (HM_CLOSED, HM_UNLOCKED):
                    found_frontier = True
                elif nsquare.hard == HM_UNKNOWN:
                    if not nsquare.boulder:
                        found_frontier = True
            for nloc in self.cached_neighbor_locations_ortho[loc]:
                if self.level[nloc].hard == HM_LOCKED:
                    if self.get_kickable_status(nloc) != 'unkickable':
                        found_frontier = True
            if found_frontier:
                interesting_set.add(loc)
        # if we are in a level that might have secret doors then dead ends are interesting.
        if self.has_secret_doors():
            for loc, square in self.level.items():
                if self.is_dead_end(loc):
                    if square.search_count_from < 27:
                        interesting_set.add(loc)
        # In sokoban the square in front of the next boulder to push is interesting.
        if self.level_branch == LEVEL_BRANCH_SOKOBAN:
            if self.sokoban_queue:
                flanking_row, flanking_col, boulder_row, boulder_col = self.sokoban_queue[0]
                target_player_location = (flanking_row, flanking_col)
                interesting_set.add(target_player_location)
        return interesting_set

    def has_secret_doors(self):
        if self.level_special == LEVEL_SPECIAL_MINETOWN:
            if self.wall_type != WALL_TYPE_CAVERN:
                return True
        if self.level_branch == LEVEL_BRANCH_SOKOBAN:
            return False
        if self.level_branch == LEVEL_BRANCH_MINES:
            return False
        if self.level_branch == LEVEL_BRANCH_DOOM:
            return True
        return True

    def get_location_evaluations(self, interesting_locations, scary_locations):
        """
        Return a dict mapping a location to the distance from an interesting square.
        If a location is not in the dict, then no path exists.
        """
        shell = interesting_locations - scary_locations
        loc_to_dist = {}
        depth = 0
        for loc in shell:
            loc_to_dist[loc] = depth
        while shell:
            depth += 1
            next_shell = set()
            for loc in shell:
                square = self.level[loc]
                for nloc in square.passable_neighbor_locations:
                    if nloc in scary_locations:
                        continue
                    if nloc not in loc_to_dist:
                        next_shell.add(nloc)
                        loc_to_dist[nloc] = depth
            shell = next_shell
        return loc_to_dist

    def is_passable(self, loca, locb):
        """
        This calculation takes into account only the hardmap.
        Because this function is in an inner loop,
        the preconditions are somewhat stringent.
        1) The locations loca and locb should have a distLinf of exactly 1.
           That is, they should be exactly one square away from each other.
        """
        empty_states = (HM_OPEN, HM_FLOOR, HM_OCCUPIABLE, HM_ALTAR, HM_UP_CONFIRMED, HM_DOWN_CONFIRMED, HM_UP_UNCONFIRMED, HM_DOWN_UNCONFIRMED)
        rowa, cola = loca
        rowb, colb = locb
        # check the first location for passability
        square_a = self.level[loca]
        if square_a.hard not in empty_states:
            return False
        if square_a.boulder:
            return False
        # check the second location for passability
        square_b = self.level[locb]
        if square_b.hard not in empty_states:
            return False
        if square_b.boulder:
            return False
        # check for passage orthogonality
        if rowa == rowb or cola == colb:
            return True
        # cannot cross an open doorway diagonally
        if square_a.hard == HM_OPEN or square_b.hard == HM_OPEN:
            return False
        # check the two counter-diagonal squares for a way to squeeze through
        mloca_square = self.level[(rowa, colb)]
        mlocb_square = self.level[(rowb, cola)]
        if self.level_branch == LEVEL_BRANCH_SOKOBAN:
            # in sokoban levels we cannot squeeze between diagonal boulders
            if (mloca_square.hard != HM_WALL) and (not mloca_square.boulder):
                return True
            if (mlocb_square.hard != HM_WALL) and (not mlocb_square.boulder):
                return True
        else:
            # in non-sokoban levels we can squeeze between diagonal boulders
            if mloca_square.hard != HM_WALL:
                return True
            if mlocb_square.hard != HM_WALL:
                return True
        return False
    
    def get_pickable_status(self, loc):
        """
        This returns whether or not we should pick a locked door at a given location.
        The danger is that we are in minetown and the guards will get angry.
        Return one of {'unknown', 'pickable', 'unpickable'}
        """
        # do not pick a lock in minetown
        if self.level_special == LEVEL_SPECIAL_MINETOWN:
            return 'unpickable'
        else:
            return 'pickable'

    def get_kickable_status(self, loc):
        """
        This returns whether or not we should kick a locked door at a given location.
        One danger is that it is a shop door that is closed for inventory.
        We make this decision based on whether or not there is graffiti
        on a square ortho to the door.
        Another danger is that we are in minetown and the guards will get angry.
        Return one of {'unknown', 'kickable', 'unkickable'}
        """
        # do not kick a door in minetown
        if self.level_special == LEVEL_SPECIAL_MINETOWN:
            return 'unkickable'
        # do not kick doors that might be shop doors
        has_graffiti = False
        has_trod = False
        for nloc in self.cached_neighbor_locations_ortho[loc]:
            nsquare = self.level[nloc]
            if nsquare.graffiti:
                has_graffiti = True
            elif nsquare.trod:
                has_trod = True
        if has_graffiti:
            return 'unkickable'
        elif has_trod:
            return 'kickable'
        else:
            return 'unknown'

    def notify_graffiti(self, location):
        square = self.level[location]
        square.graffiti = True

    def notify_store_door(self, last_loc, store_door_loc):
        """
        This is a notification that a store door has been identified at the given location.
        Identify the GM_DOOR, the GM_ENTRANCE, and each GM_STORE square.
        @param last_loc: the location of the player before stepping on the door (presumably outside the store)
        @param store_door_loc: the location of the store door itself
        """
        # make sure the last move was a non-diagonal move of a single square
        if abs(last_loc[0] - store_door_loc[0]) + abs(last_loc[1] - store_door_loc[1]) != 1:
            return 'the move to the store door was strange: %s to %s' % (last_loc, store_door_loc)
        # note the store's door
        self.level[store_door_loc].store = GM_DOOR
        # note the store's entrance square
        entrance_row = store_door_loc[0] + (store_door_loc[0] - last_loc[0])
        entrance_col = store_door_loc[1] + (store_door_loc[1] - last_loc[1])
        entrance_loc = (entrance_row, entrance_col)
        self.level[entrance_loc].store = GM_ENTRANCE
        # fill the rest of the store with GM_STORE status
        store_counter = 0
        shell = [entrance_loc]
        while shell:
            newshell = set()
            for oldloc in shell:
                for newloc in self.cached_neighbor_locations[oldloc]:
                    square = self.level[newloc]
                    if square.hard in (HM_OCCUPIABLE, HM_FLOOR) and square.store == GM_NONE:
                        square.store = GM_STORE
                        newshell.add(newloc)
                        store_counter += 1
            shell = newshell
        return 'added %d store tiles' % store_counter






