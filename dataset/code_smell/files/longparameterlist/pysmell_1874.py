# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/parse/chart.py#L649-L703
# smelly line(s) in the original file: 649
# smelly line(s) in this file: 8
# ids: pysmell_1874
# note: Python 2 era source, kept as found
def _trees(self, edge, complete, memo, tree_class):
    """
    A helper function for ``trees``.

    :param memo: A dictionary used to record the trees that we've
        generated for each edge, so that when we see an edge more
        than once, we can reuse the same trees.
    """
    # If we've seen this edge before, then reuse our old answer.
    if edge in memo:
        return memo[edge]

    # when we're reading trees off the chart, don't use incomplete edges
    if complete and edge.is_incomplete():
        return []

    # Leaf edges.
    if isinstance(edge, LeafEdge):
        leaf = self._tokens[edge.start()]
        memo[edge] = [leaf]
        return [leaf]

    # Until we're done computing the trees for edge, set
    # memo[edge] to be empty.  This has the effect of filtering
    # out any cyclic trees (i.e., trees that contain themselves as
    # descendants), because if we reach this edge via a cycle,
    # then it will appear that the edge doesn't generate any trees.
    memo[edge] = []
    trees = []
    lhs = edge.lhs().symbol()

    # Each child pointer list can be used to form trees.
    for cpl in self.child_pointer_lists(edge):
        # Get the set of child choices for each child pointer.
        # child_choices[i] is the set of choices for the tree's
        # ith child.
        child_choices = [self._trees(cp, complete, memo, tree_class)
                         for cp in cpl]

        # For each combination of children, add a tree.
        for children in itertools.product(*child_choices):
            trees.append(tree_class(lhs, children))

    # If the edge is incomplete, then extend it with "partial trees":
    if edge.is_incomplete():
        unexpanded = [tree_class(elt,[])
                      for elt in edge.rhs()[edge.dot():]]
        for tree in trees:
            tree.extend(unexpanded)

    # Update the memoization dictionary.
    memo[edge] = trees

    # Return the list of trees.
    return trees
