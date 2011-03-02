
from AscLevelConstants import *

class WallSearch:
    """
    This is the search plan for a region for which we are desperate to find a secret door.
    Create and store a set of wall locations that should be searched.
    The WallSearch object associated with a region should be deleted if a conventionally unsearched square is discovered.
    The __init__ function is very CPU intensive.
    """
    def __init__(self, levelmap):
        self.level = levelmap
        # get the reachable locations
        reachable_locations = self.get_reachable_locations()
        self.remark('WallSearch: %d reachable locations' % len(reachable_locations))
        # get the walls orthogonally adjacent to a reachable location
        ortho_wall_locations = self.get_ortho_wall_locations(reachable_locations)
        self.remark('WallSearch: %d walls orthogonally adjacent to a reachable location' % len(ortho_wall_locations))
        # get (wall_location, target_location) pairs
        wall_target_pairs = self.get_wall_target_pairs(reachable_locations, ortho_wall_locations)
        self.remark('WallSearch: %d wall and target pairs were found' % len(wall_target_pairs))
        # get the good wall locations after filtering the wall_target_pairs
        self.good_wall_locations = self.get_good_wall_locations(reachable_locations, wall_target_pairs)
        self.remark('WallSearch: %d good wall locations' % len(self.good_wall_locations))

    def remark(self, message):
        self.level.remark(message)

    def get_reachable_locations(self):
        """
        @return: the set of all squares reachable from the current square
        """
        player_region = self.level.get_player_region()
        target_set = set([player_region.location])
        taboo_set = self.level.cached_untouchable_locations
        loc_to_dist = self.level.get_location_evaluations(target_set, taboo_set)
        return set(loc_to_dist)

    def get_ortho_wall_locations(self, reachable_locations):
        """
        @return: the set of all walls orthogonally adjacent to a reachable square
        """
        ortho_wall_locations = set()
        for square_location in reachable_locations:
            for neighbor_location in self.level.cached_neighbor_locations_ortho[square_location]:
                neighbor_square = self.level.level[neighbor_location]
                if neighbor_square.hard == HM_WALL:
                    ortho_wall_locations.add(neighbor_location)
        return ortho_wall_locations

    def get_wall_target_pairs(self, reachable_locations, ortho_wall_locations):
        """
        @return: a list of (wall location, target_location) pairs
        """
        wall_target_pairs = []
        for wall_location in ortho_wall_locations:
            reachable_neighbor_locations = []
            for neighbor_location in self.level.cached_neighbor_locations_ortho[wall_location]:
                if neighbor_location in reachable_locations:
                    reachable_neighbor_locations.append(neighbor_location)
            # require that the wall be accessible by exactly one reachable square
            if len(reachable_neighbor_locations) != 1:
                continue
            # find the target square across the wall from the reachable square
            reachable_neighbor_location = reachable_neighbor_locations[0]
            wall_row, wall_col = wall_location
            reachable_row, reachable_col = reachable_neighbor_location
            delta_row = wall_row - reachable_row
            delta_col = wall_col - reachable_col
            target_location = (wall_row + delta_row, wall_col + delta_col)
            # require that the target location be in bounds
            if target_location not in set(self.level.cached_neighbor_locations_ortho[wall_location]):
                continue
            wall_target_pair = (wall_location, target_location)
            wall_target_pairs.append(wall_target_pair)
        return wall_target_pairs

    def get_good_wall_locations(self, reachable_locations, wall_target_pairs):
        """
        @return: a set of wall locations that are worth searching for secret doors
        """
        good_wall_locations = set()
        for wall_location, target_location in wall_target_pairs:
            # make sure the target location is not already reachable and is not a wall or part of a store
            target_square = self.level.level[target_location]
            if target_square.store == GM_STORE:
                continue
            if target_square.hard == HM_WALL:
                continue
            if target_square in reachable_locations:
                continue
            # make sure none of the orthogonal neighbors of the target square is reachable
            ortho_reachable_target_neighbors = []
            for neighbor_location in self.level.cached_neighbor_locations_ortho[target_location]:
                if neighbor_location in reachable_locations:
                    ortho_reachable_target_neighbors.append(neighbor_location)
            if ortho_reachable_target_neighbors:
                continue
            # because the wall location passed all the tests add it to the list of walls to be searched
            good_wall_locations.add(wall_location)
        return good_wall_locations

