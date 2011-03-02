

# These are the trap types
TRAP_UNKNOWN = 0
TRAP_NONE = 1
TRAP_SAFE = 2
TRAP_UNSAFE = 3
TRAP_HOLE = 4
TRAP_OTHER = 5

# HM stands for "hard map"
# which is a relatively stable map of the dungeon
# misc obstacles include trees and iron bars.
HM_UNKNOWN = 0
HM_OCCUPIABLE = 1
HM_FLOOR = 2
#HM_BOULDER = 3
HM_WALL = 4
HM_UNDIGGABLE = 5
HM_WATER = 6
HM_LAVA = 7
HM_ALTAR = 8
HM_CLOSED = 10
HM_OPEN = 11
HM_LOCKED = 12
HM_UNLOCKED = 13
HM_UP_UNCONFIRMED = 22
HM_DOWN_UNCONFIRMED = 23
HM_UP_CONFIRMED = 24
HM_DOWN_CONFIRMED = 25
HM_MISC_OBSTACLE = 30

# This is the set of store states for each tile
GM_NONE = 0
GM_STORE = 1
GM_ENTRANCE = 2
GM_DOOR = 3

# Level branches
LEVEL_BRANCH_UNKNOWN = 0
LEVEL_BRANCH_DOOM = 1
LEVEL_BRANCH_MINES = 2
LEVEL_BRANCH_SOKOBAN = 3

def level_branch_to_string(level_branch):
    d = {
        LEVEL_BRANCH_UNKNOWN : 'unknown',
        LEVEL_BRANCH_DOOM : 'doom',
        LEVEL_BRANCH_MINES : 'mines',
        LEVEL_BRANCH_SOKOBAN : 'sokoban'
    }
    return d[level_branch]

# Special levels
LEVEL_SPECIAL_UNKNOWN = 0
LEVEL_SPECIAL_NONE = 1
LEVEL_SPECIAL_TOP = 2
LEVEL_SPECIAL_DOOM_FORK = 3
LEVEL_SPECIAL_MINETOWN = 4
LEVEL_SPECIAL_MINESEND = 5
LEVEL_SPECIAL_ORACLE = 6
LEVEL_SPECIAL_SOKOBAN_FORK = 7

def level_special_to_string(level_special):
    d = {
        LEVEL_SPECIAL_UNKNOWN : 'unknown',
        LEVEL_SPECIAL_NONE : 'none',
        LEVEL_SPECIAL_TOP : 'top',
        LEVEL_SPECIAL_DOOM_FORK : 'doomfork',
        LEVEL_SPECIAL_MINETOWN : 'minetown',
        LEVEL_SPECIAL_MINESEND : 'minesend',
        LEVEL_SPECIAL_ORACLE : 'oracle',
        LEVEL_SPECIAL_SOKOBAN_FORK : 'sokobanfork'
    }
    return d[level_special]

