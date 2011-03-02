
"""
This module is testing fodder for the searching algorithms in AscDP.
"""

import random

def slide_transition(source):
    """
    This is a toy transition function for testing.
    This function could be a member of the state, but that is not how this is factored.
    Generates sink states given a source state.
    @param source: a sequence of integer sequences that defines a row major sliding tile puzzle state.
    """
    nrows = len(source)
    ncols = len(source[0])
    all_values = set()
    free_row, free_col = None, None
    for row in range(nrows):
        for col in range(ncols):
            all_values.add(source[row][col])
            if not source[row][col]:
                free_row, free_col = row, col
    neighbor_values = set()
    if free_row > 0:
        neighbor_values.add(source[free_row-1][free_col])
    if free_col > 0:
        neighbor_values.add(source[free_row][free_col-1])
    if free_row < nrows - 1:
        neighbor_values.add(source[free_row+1][free_col])
    if free_col < ncols - 1:
        neighbor_values.add(source[free_row][free_col+1])
    for neighbor_value in neighbor_values:
        d = dict((v, v) for v in all_values)
        d[0] = neighbor_value
        d[neighbor_value] = 0
        yield tuple(tuple(d[v] for v in row) for row in source)

def slide_min_distance(source, target):
    """
    This is a toy function for testing.
    This calculates a lower bound on the number of turns from a source to a target puzzle state.
    """
    nrows = len(source)
    ncols = len(source[0])
    source_location = {}
    target_location = {}
    for row in range(nrows):
        for col in range(ncols):
            source_location[source[row][col]] = (row, col)
            target_location[target[row][col]] = (row, col)
    distance = 0
    for v in range(1, nrows*ncols):
        ra, ca = source_location[v]
        rb, cb = target_location[v]
        distance += abs(rb-ra) + abs(cb-ca)
    return distance

class Heuristic:
    def __init__(self, target_state):
        self.target_state = target_state
    def __call__(self, source):
        return slide_min_distance(source, self.target_state)

def slide_string(source):
    """
    This function visualizes the puzzle state.
    """
    return '\n'.join(' '.join(str(x) for x in row) for row in source)

def run():
    final_state = ((0,1,2),(3,4,5),(6,7,8))
    state = final_state
    for i in range(20):
        print slide_string(state)
        print slide_min_distance(state, final_state)
        print
        state = random.choice(tuple(slide_transition(state)))

if __name__ == '__main__':
    run()



