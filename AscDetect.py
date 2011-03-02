"""
This module looks at the ansi map and infers attributes of the dungeon level.
This module is independent of the internal map representation.

Is it a sokoban level?  Which one is it?
Are there doors?
Are there cavern walls?
"""

import AscSokoban
from AscUtil import Rect


class DetectionError(Exception):
    """
    This exception should be thrown when an error is encountered during the detection of dungeon properties.
    It should not be thrown as a means of reporting that a dungeon property was not detected.
    """
    pass


class AscFirstImpression:
    """
    This class has information that is known about a new level immediately after changing dlvls.
    This information is important for identifying the branch of the new level,
    and possibly for identifying the branch of the linking level.
    """
    def __init__(self, dlvl, location, rect, ansi):
        self.dlvl = dlvl
        self.location = location
        self.engulfed = detect_engulfing(rect, ansi)
        self.sokoban_level_name = detect_sokoban_level(rect, ansi)
        self.doors = detect_doors(rect, ansi)
        self.cavern_walls = detect_cavern_walls(rect, ansi)


def detect_sokoban_level(rect, ansi):
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
    for loc in rect.gen_locations():
        row, col = loc
        ansi_square = ansi.lines[row][col]
        if ansi_square.char in sokoban_wall_characters:
            raw_wall_locations.add(loc)
    # If no walls were observed then the level was not detected.
    if not raw_wall_locations:
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
        return None
    elif len(matching_level_names) > 1:
        raise DetectionError('multiple matching sokoban levels were found')
    else:
        level_name = matching_level_names[0]
        return level_name


def detect_engulfing(rect, ansi):
    engulfing_pattern = r'/-\||\-/'
    offsets = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
    arr = []
    for drow, dcol in offsets:
        nloc = (ansi.row + drow, ansi.col + dcol)
        if rect.is_inbounds(nloc):
            arr.append(ansi.lines[ansi.row + drow][ansi.col + dcol].char)
    detected_pattern = ''.join(arr)
    return (detected_pattern == engulfing_pattern)


def detect_doors(rect, ansi):
    for (row, col) in rect.gen_locations():
        ansi_square = ansi.lines[row][col]
        if ansi_square.foreground == 33:
            if ansi_square.char in ('-', '|', '.'):
                return True
    return False


def detect_cavern_walls(rect, ansi):
    """
    If you see the wall pattern || then this is the mines.
    Also -
         -
    means mines.
    This information is helpful for determining the level type.
    I suspect that this distinctive pattern is caused by the presence of T and + junctions in the walls,
    and that reassigning the ascii symbols will make this detection even more efficient.
    Or maybe it is just adjacent wall corners.
    On the other hand this change to the config file would give fewer dungeon feature reference points
    for navigating around the dungeon map in 'C' or ';' mode.
    """
    for (ra, ca), (rb, cb) in rect.gen_horizontal_neighbor_pairs():
        if ansi.lines[ra][ca].char == '|' and ansi.lines[rb][cb].char == '|':
            return True
    for (ra, ca), (rb, cb) in rect.gen_vertical_neighbor_pairs():
        if ansi.lines[ra][ca].char == '-' and ansi.lines[rb][cb].char == '-':
            return True
    return False



