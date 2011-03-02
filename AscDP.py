
"""
This module has a bunch of dynamic programming stuffs.
"""

# for best-first search
from heapq import heappush, heappop


class TransitionTable:
    """
    Use predefined explicit transitions as opposed to transitions calculated on the fly.
    This is a helper function object intended to be passed to the caller of the flood fill functions.
    """
    def __init__(self):
        self.neighbors = {}
    def add(self, source, sink):
        """
        @param source: a hashable state
        @param sink: a hashable state
        """
        try:
            self.neighbors[source].add(sink)
        except KeyError:
            self.neighbors[source] = set([sink])
    def add_symmetric(self, source, sink):
        """
        @param source: a hashable state
        @param sink: a hashable state
        """
        self.add(source, sink)
        self.add(sink, source)
    def __call__(self, source):
        """
        @param source: a hashable state
        @return: an iterable sequence of sink states
        """
        try:
            return self.neighbors[source]
        except KeyError:
            return set()


class ActionTransitionTable(TransitionTable):
    """
    This transition table specifies not only the allowed transitions,
    but also the action required to make the transition.
    """
    def __init__(self):
        TransitionTable.__init__(self)
        self.actions = {}
        self.sinks = {}
    def add(self, source, sink, action):
        """
        @param source: a hashable state
        @param sink: a hashable state
        @param action: a hashable action
        """
        TransitionTable.add(self, source, sink)
        self.actions[(source, sink)] = action
        self.sinks[(source, action)] = sink
    def add_symmetric(self, source, sink, action):
        self.add(source, sink, action)
        self.add(sink, source, action)
    def get_action(self, source, sink):
        return self.actions.get((source, sink), None)
    def get_sink(self, source, action):
        return self.sinks.get((source, action), None)


class BackwardsForwardsTable:
    def __init__(self):
        self.forwards = ActionTransitionTable()
        self.backwards = ActionTransitionTable()
    def add(self, source, sink, action):
        self.forwards.add(source, sink, action)
        self.backwards.add(sink, source, action)


def flood_all_states(seeds, transition):
    """
    @param seeds: a collection of seed states
    @param transition: yields sink states given a source state
    @return: the set of states reachable from a seed state
    """
    total = set(seeds)
    shell = set(seeds)
    while shell:
        newshell = set()
        for current in shell:
            for next in transition(current):
                if next not in total:
                    total.add(next)
                    newshell.add(next)
        shell = newshell
    return total


def flood_all_targets(seeds, targets, transition):
    """
    @param seeds: a collection of seed states
    @param target: a collection of target states
    @param transition: a generator that yields sink states given a source state
    @return: the set of target states reachable from the seed state
    """
    total = set(seeds)
    target_set = set(targets)
    shell = set(seeds)
    found = shell & target_set
    if found == target_set:
        return found
    while shell:
        newshell = set()
        for current in shell:
            for next in transition(current):
                if next not in total:
                    if next in target_set:
                        found.add(next)
                        if found == target_set:
                            return found
                    total.add(next)
                    newshell.add(next)
        shell = newshell
    return found


def measure_all_states(seeds, transition):
    """
    This function will find the distances from the seeds to all reachable states.
    Each transition is assumed to have distance one.
    @param seeds: a collection of seed states
    @param transition: a generator that yields sink states given a source state
    @return: a dictionary mapping a state to a distance
    """
    distance = 0
    shell = set(seeds)
    state_to_distance = dict((state, 0) for state in shell)
    while shell:
        distance += 1
        newshell = set()
        for current in shell:
            for next in transition(current):
                if next not in state_to_distance:
                    state_to_distance[next] = distance
                    newshell.add(next)
        shell = newshell
    return state_to_distance

def measure_all_targets(seeds, targets, transition):
    """
    This function will find the distances from the seeds to several states including the target states if possible.
    Each transition is assumed to have distance one.
    @param seeds: a collection of seed states
    @param target: a collection of target states
    @param transition: a generator that yields sink states given a source state
    @return: a dictionary mapping a state to a distance
    """
    distance = 0
    target_set = set(targets)
    shell = set(seeds)
    state_to_distance = dict((state, 0) for state in shell)
    found = shell & target_set
    if found == target_set:
        return state_to_distance
    while shell:
        distance += 1
        newshell = set()
        for current in shell:
            for next in transition(current):
                if next not in state_to_distance:
                    state_to_distance[next] = distance
                    newshell.add(next)
                    if next in targets:
                        found.add(next)
                        if found == target_set:
                            return state_to_distance
        shell = newshell
    return state_to_distance

def measure_any_target(seeds, targets, transition):
    """
    This function will find the distances from the seeds to several states including a target state if possible.
    Each transition is assumed to have distance one.
    @param seeds: a collection of seed states
    @param target: a collection of target states
    @param transition: a generator that yields sink states given a source state
    @return: a dictionary mapping a state to a distance
    """
    distance = 0
    shell = set(seeds)
    state_to_distance = dict((state, 0) for state in shell)
    for seed in shell:
        if seed in targets:
            return state_to_distance
    while shell:
        distance += 1
        newshell = set()
        for current in shell:
            for next in transition(current):
                if next not in state_to_distance:
                    state_to_distance[next] = distance
                    newshell.add(next)
                    if next in targets:
                        return state_to_distance
        shell = newshell
    return state_to_distance

def measure_informed(seeds, transition, heuristic):
    """
    @param seeds: a collection of seed states
    @param transition: a generator that yields sink states given a source state
    @param heuristic: given a state it returns zero if the state is terminal or None if a terminal state is unreachable or a lower bound on the distance to a terminal state
    @return: a dictionary mapping a state to a distance
    """
    state_to_distance = {}
    pq = []
    for seed in seeds:
        if seed not in state_to_distance:
            remaining = heuristic(seed)
            if remaining is not None:
                state_to_distance[seed] = 0
                if remaining == 0:
                    return state_to_distance
                heappush(pq, (remaining, seed))
    while pq:
        current_low_path_length, current = heappop(pq)
        for next in transition(current):
            if next not in state_to_distance:
                distance = state_to_distance[current] + 1
                remaining = heuristic(next)
                if remaining is not None:
                    state_to_distance[next] = distance
                    if remaining == 0:
                        return state_to_distance
                    heappush(pq, (distance + remaining, next))
    return state_to_distance

class MeasureInformedTraceback:
    def __init__(self, seeds, transition, heuristic):
        """
        @param seeds: a collection of seed states
        @param transition: a generator that yields sink states given a source state
        @param heuristic: given a state it returns zero if the state is terminal or None if a terminal state is unreachable or a lower bound on the distance to a terminal state
        @return: a (traceback, terminal) pair
        """
        self.transition = transition
        self.heuristic = heuristic
        self.solution = None
        self.state_to_distance = {}
        self.traceback = {}
        self.pq = []
        for seed in seeds:
            if seed not in self.state_to_distance:
                remaining = self.heuristic(seed)
                if remaining is not None:
                    self.traceback[seed] = None
                    self.state_to_distance[seed] = 0
                    if remaining == 0:
                        self.solution = (self.traceback, seed)
                        self.pq = []
                        return
                    heappush(self.pq, (remaining, seed))
        if not self.pq:
            self.solution = (self.traceback, None)
    def get_solution(self):
        return self.solution
    def get_distance(self):
        if self.solution:
            traceback, terminal = self.solution
            if terminal is None:
                return None
            else:
                return self.state_to_distance[terminal]
        else:
            current_low_path_length, current = self.pq[0]
            return current_low_path_length
    def step(self):
        if self.pq:
            current_low_path_length, current = heappop(self.pq)
            for next in self.transition(current):
                if next not in self.state_to_distance:
                    distance = self.state_to_distance[current] + 1
                    remaining = self.heuristic(next)
                    if remaining is not None:
                        self.state_to_distance[next] = distance
                        self.traceback[next] = current
                        if remaining == 0:
                            self.solution = (self.traceback, next)
                            self.pq = []
                            return
                        heappush(self.pq, (distance + remaining, next))
            if not self.pq:
                self.solution = (self.traceback, None)

def measure_informed_traceback(seeds, transition, heuristic):
    """
    @param seeds: a collection of seed states
    @param transition: a generator that yields sink states given a source state
    @param heuristic: given a state it returns zero if the state is terminal or None if a terminal state is unreachable or a lower bound on the distance to a terminal state
    @return: a (traceback, terminal) pair
    """
    state_to_distance = {}
    traceback = {}
    pq = []
    for seed in seeds:
        if seed not in state_to_distance:
            remaining = heuristic(seed)
            if remaining is not None:
                traceback[seed] = None
                state_to_distance[seed] = 0
                if remaining == 0:
                    return (traceback, seed)
                heappush(pq, (remaining, seed))
    while pq:
        current_low_path_length, current = heappop(pq)
        for next in transition(current):
            if next not in state_to_distance:
                distance = state_to_distance[current] + 1
                remaining = heuristic(next)
                if remaining is not None:
                    state_to_distance[next] = distance
                    traceback[next] = current
                    if remaining == 0:
                        return (traceback, next)
                    heappush(pq, (distance + remaining, next))
    return (traceback, None)


def get_path(source, transition, state_to_distance):
    """
    @param source: a source state
    @param transition: a way to generate neighbor states
    @param state_to_distance: the distance from a target state
    @return: the sequence of states from the source state to a target state
    """
    path = [source]
    state = source
    while state_to_distance[state] != 0:
        distance_state_pairs = []
        for next in transition(state):
            if next in state_to_distance:
                distance_state_pairs.append((state_to_distance[next], next))
        distance, state = min(distance_state_pairs)
        path.append(state)
    return path

def traceback_to_path(traceback, terminal):
    """
    This works best with the output of measure_informed_traceback as input.
    """
    path = []
    state = terminal
    while state:
        path.append(state)
        state = traceback[state]
    return path

def get_best_actions(source, targets, backward_transition, forward_transition):
    """
    @param seed: the starting state
    @param targets: a container of equally good target states
    @param transition: a transition function specifying actions that change state
    @return: a container of optimal (action, sink) pairs
    """
    state_to_distance = measure_all_targets(targets, [source], backward_transition)
    distance_sink_pairs = [(state_to_distance[sink], sink) for sink in forward_transition(source) if sink in state_to_distance]
    best_distance = min(distance_sink_pairs)[0]
    return set(forward_transition.get_action(source, sink) for (distance, sink) in distance_sink_pairs if distance == best_distance)


def test1():
    t = TransitionTable()
    for pair in ((1,2), (0,5), (2,3), (2,3), (2,5), (3,4)):
        t.add(*pair)
    assert flood_all_states([2], t) == set([2, 3, 4, 5])

def test2():
    t = TransitionTable()
    for pair in ((1,2), (0,5), (2,3), (2,3), (2,5), (3,4)):
        t.add_symmetric(*pair)
    assert flood_all_states([2], t) == set([0, 1, 2, 3, 4, 5])

def test3():
    t = TransitionTable()
    for pair in ((1,2), (2,3), (4,5), (5,6)):
        t.add_symmetric(*pair)
    assert flood_all_targets([1], [2, 3, 4], t) == set([2, 3])

def test4():
    t = TransitionTable()
    for pair in ((1,2), (2,3), (3,4), (4,5), (5,6), (6,7)):
        t.add(*pair)
    assert flood_all_targets([3], [6], t) == set([6])

def test5():
    t = TransitionTable()
    for pair in ((1,2), (2,3), (3,4), (4,5), (5,6), (6,7)):
        t.add(*pair)
    assert measure_all_targets([3], [6], t) == {3:0, 4:1, 5:2, 6:3}

def test6():
    assert measure_all_targets([3], [6], lambda x: [x+1]) == {3:0, 4:1, 5:2, 6:3}

def test7():
    t = BackwardsForwardsTable()
    for triple in (('a1','a2','-a->'), ('a2','a3','-a->'), ('a3','a4','-a->')):
        t.add(*triple)
    for triple in (('a4','x1','-x->'), ('x1','x2','-x->'), ('x2','x3','-x->'), ('x3','x4','-x->'), ('x4','fail','-x->')):
        t.add(*triple)
    for triple in (('a4','y1','-y->'), ('y1','y2','-y->'), ('y2', 'win1','-y->')):
        t.add(*triple)
    for triple in (('a4','z1','-z->'), ('z1','z2','-z->'), ('z2', 'win2','-z->')):
        t.add(*triple)
    assert get_best_actions('a4', ('win1', 'win2'), t.backwards, t.forwards) == set(['-y->', '-z->'])
    assert get_best_actions('a1', ('win1', 'win2'), t.backwards, t.forwards) == set(['-a->'])
    assert get_best_actions('z1', ('win1', 'win2'), t.backwards, t.forwards) == set(['-z->'])

def test8():
    """
    Test the solution of an 8-puzzle.
    """
    try:
        import AscTilePuzzle
    except ImportError:
        return
    initial_state = ((1,8,7),(2,0,6),(3,4,5))
    terminal_state = ((1,2,3),(4,5,6),(7,8,0))
    heuristic = AscTilePuzzle.Heuristic(terminal_state)
    # do it one way
    state_to_distance = measure_informed([initial_state], AscTilePuzzle.slide_transition, heuristic)
    assert state_to_distance[terminal_state] == 24
    path_a = get_path(terminal_state, AscTilePuzzle.slide_transition, state_to_distance)
    assert len(path_a) == 25
    # do it another way
    traceback, terminal = measure_informed_traceback([initial_state], AscTilePuzzle.slide_transition, heuristic)
    path_b = traceback_to_path(traceback, terminal)
    assert len(path_b) == 25
    # do it another way
    solver = MeasureInformedTraceback([initial_state], AscTilePuzzle.slide_transition, heuristic)
    while not solver.get_solution():
        solver.step()
    path_c = traceback_to_path(*solver.get_solution())
    assert len(path_c) == 25
    # make sure that each method gives the same path
    assert tuple(path_a) == tuple(path_b)
    assert tuple(path_b) == tuple(path_c)


def run():
    test1()
    test2()
    test3()
    test4()
    test5()
    test6()
    test7()
    test8()

if __name__ == '__main__':
    run()



