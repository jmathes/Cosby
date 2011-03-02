import os

vi_delta_pairs = (
        ('k', (-1, 0)),
        ('j', (1, 0)),
        ('h', (0, -1)),
        ('l', (0, 1)),
        ('y', (-1, -1)),
        ('u', (-1, 1)),
        ('b', (1, -1)),
        ('n', (1, 1))
        )

class Rect:
    """
    The methods in this class are not meant to be fast.
    For faster methods use a layer of caching above this class.
    """
    def __init__(self, row_min, col_min, row_max, col_max):
        self.row_min = row_min
        self.col_min = col_min
        self.row_max = row_max
        self.col_max = col_max

    def is_inbounds(self, location):
        row, col = location
        if row < self.row_min or col < self.col_min:
            return False
        if row > self.row_max or col > self.col_max:
            return False
        return True

    def gen_neighbors(self, location):
        row, col = location
        for drow in (-1, 0, 1):
            for dcol in (-1, 0, 1):
                if (drow, dcol) != (0, 0):
                    nloc = (row + drow, col + dcol)
                    if self.is_inbounds(nloc):
                        yield nloc

    def gen_manhattan_neighbors(self, location):
        row, col = location
        for drow, dcol in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nloc = (row + drow, col + dcol)
            if self.is_inbounds(nloc):
                yield nloc

    def gen_horizontal_neighbor_pairs(self):
        rows = list(self.gen_rows())
        cols = list(self.gen_cols())
        for row in rows:
            for ca, cb in zip(cols[:-1], cols[1:]):
                yield ((row, ca), (row, cb))

    def gen_vertical_neighbor_pairs(self):
        rows = list(self.gen_rows())
        cols = list(self.gen_cols())
        for col in cols:
            for ra, rb in zip(rows[:-1], rows[1:]):
                yield ((ra, col), (rb, col))

    def gen_rows(self):
        return range(self.row_min, self.row_max + 1)

    def gen_cols(self):
        return range(self.col_min, self.col_max + 1)

    def gen_locations(self):
        for row in self.gen_rows():
            for col in self.gen_cols():
                yield (row, col)
    
    def row_major_range(self, location_begin, location_end):
        """
        This works analogously to an integer range [a, b),
        except that it is over a bounded row-major rectangular region.
        It wraps.
        """
        row, col = location_begin
        while (row, col) != location_end:
            yield (row, col)
            col += 1
            if col > self.col_max:
                col = self.col_min
                row += 1
                if row > self.row_max:
                    row = self.row_min


def get_bounding_coordinates(locations):
    """
    @param locations: an iterable container of at least one (row, col) location
    @return: (row_min, col_min, row_max, col_max)
    """
    assert locations
    row_min = min(row for row, col in locations)
    col_min = min(col for row, col in locations)
    row_max = max(row for row, col in locations)
    col_max = max(col for row, col in locations)
    return (row_min, col_min, row_max, col_max)

def distL1(loca, locb):
    return abs(loca[0] - locb[0]) + abs(loca[1] - locb[1])

def distLinf(loca, locb):
    return max(abs(loca[0] - locb[0]), abs(loca[1] - locb[1]))

def no_op():
    return

def ascii_to_meta(letter):
    return chr(128 + ord(letter))

def hex_to_ascii(msg):
    """
    Given an binary hex string,
    return a printable ascii string describing it.
    """
    return '.'.join('%02x' % ord(c) for c in msg)

