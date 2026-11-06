"""Dependency graph and cycle detection (Phase 2, SPEC.md section 8).

This module is language-neutral: it only looks at Edge objects, so it works
the same for Python now and Java later.

Words used here:
- graph: for every module, the list of modules it depends on.
- strongly connected component (SCC): a largest group of modules where every
  module can reach every other module by following edges.
- cycle: an SCC with more than one module, or one module that imports itself.

The SCCs are found with Tarjan's algorithm. It is written with an explicit
stack instead of recursion: a recursive version would call itself once per
module in a long chain, and Python stops at about 1000 nested calls
(RecursionError). docs/how-it-works.md walks through an example.
"""

from __future__ import annotations

from collections.abc import Iterable

from repolens.model import Cycle, Edge, EdgeKind, ImportClass, edge_sort_key

# Only resolved dependencies count (AGENTS.md requirement 1). Dynamic edges
# never count, because a cycle is an architecture rule.
COUNTED_KINDS = frozenset({EdgeKind.IMPORT, EdgeKind.SAME_PACKAGE})


def counted_edges(edges: Iterable[Edge]) -> list[Edge]:
    """Keep only the edges that count for the graph: local, and import or same_package."""
    return [
        edge
        for edge in edges
        if edge.classification is ImportClass.LOCAL and edge.kind in COUNTED_KINDS
    ]


def build_graph(edges: Iterable[Edge]) -> dict[str, list[str]]:
    """Return {module id: sorted list of the module ids it depends on}.

    Every module that appears in an edge is a key, even if it depends on
    nothing, so the algorithm below can look up any module. Neighbours are
    sorted and repeated edges (same pair, different lines) appear once, so
    the walk order, and therefore the result, never depends on input order.
    """
    targets: dict[str, set[str]] = {}
    for edge in edges:
        targets.setdefault(edge.source, set()).add(edge.target)
        targets.setdefault(edge.target, set())
    return {node: sorted(targets[node]) for node in sorted(targets)}


def strongly_connected_components(graph: dict[str, list[str]]) -> list[list[str]]:
    """Tarjan's algorithm, without recursion. Returns every SCC (cycle or not).

    What the algorithm remembers for each module:
    - index: the order in which the module was first visited (0, 1, 2 ...).
    - lowlink: the smallest index reachable from this module while walking,
      using modules that are still "open" (on the stack).
    When a module finishes and its lowlink equals its own index, it is the
    first-visited module (the "root") of an SCC, and every module above it
    on the stack belongs to that SCC.
    """
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []  # open modules, in visit order
    on_stack: set[str] = set()  # the same modules, for fast "is it open?" checks
    components: list[list[str]] = []
    next_index = 0

    for start in graph:  # graph keys are sorted, so the result is deterministic
        if start in index:
            continue  # already visited from an earlier start

        # The explicit stack replaces recursion. Each entry is a module and an
        # iterator over its neighbours: the iterator remembers how far we got,
        # which is what a recursive call would keep on Python's call stack.
        index[start] = lowlink[start] = next_index
        next_index += 1
        stack.append(start)
        on_stack.add(start)
        work = [(start, iter(graph[start]))]

        while work:
            node, neighbours = work[-1]
            descended = False
            for neighbour in neighbours:
                if neighbour not in index:
                    # First visit: give it an index and walk into it next.
                    index[neighbour] = lowlink[neighbour] = next_index
                    next_index += 1
                    stack.append(neighbour)
                    on_stack.add(neighbour)
                    work.append((neighbour, iter(graph[neighbour])))
                    descended = True
                    break  # continue with the neighbour; come back here later
                if neighbour in on_stack:
                    # The neighbour is still open, so we found a way back up
                    # the current path: a loop. Remember the smallest index.
                    lowlink[node] = min(lowlink[node], index[neighbour])
                # A visited neighbour that is NOT on the stack already belongs
                # to a finished SCC, so it cannot be part of ours: ignore it.
            if descended:
                continue

            # Every neighbour of `node` is done: `node` is finished.
            work.pop()
            if work:
                # Tell the parent what we could reach (like returning from
                # a recursive call).
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])

            if lowlink[node] == index[node]:
                # `node` is the root of an SCC: pop it and everything above it.
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)

    return components


def find_cycles(edges: Iterable[Edge]) -> list[Cycle]:
    """Return every cycle, fully sorted (SPEC.md section 8).

    A cycle is an SCC with more than one module, or a single module with an
    edge to itself. Each cycle lists its sorted module ids and the counted
    edges inside it. The list is sorted by each cycle's first module id;
    SCCs never share a module, so no two cycles have the same first id.
    """
    kept = counted_edges(edges)
    graph = build_graph(kept)

    cycles: list[Cycle] = []
    for component in strongly_connected_components(graph):
        members = set(component)
        is_self_import = len(component) == 1 and component[0] in graph[component[0]]
        if len(component) == 1 and not is_self_import:
            continue  # a single module without a self-import is not a cycle
        inside = [e for e in kept if e.source in members and e.target in members]
        cycles.append(Cycle(tuple(sorted(members)), tuple(sorted(inside, key=edge_sort_key))))

    cycles.sort(key=lambda cycle: cycle.modules[0])
    return cycles
