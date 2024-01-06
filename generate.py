import sys
from typing import Optional

from crossword import *


class CrosswordCreator():

    def __init__(self, crossword):
        """
        Create new CSP crossword generate.
        """
        self.crossword = crossword
        self.domains = {
            var: self.crossword.words.copy()
            for var in self.crossword.variables
        }

    def letter_grid(self, assignment):
        """
        Return 2D array representing a given assignment.
        """
        letters = [
            [None for _ in range(self.crossword.width)]
            for _ in range(self.crossword.height)
        ]
        for variable, word in assignment.items():
            direction = variable.direction
            for k in range(len(word)):
                i = variable.i + (k if direction == Variable.DOWN else 0)
                j = variable.j + (k if direction == Variable.ACROSS else 0)
                letters[i][j] = word[k]
        return letters

    def print(self, assignment):
        """
        Print crossword assignment to the terminal.
        """
        letters = self.letter_grid(assignment)
        for i in range(self.crossword.height):
            for j in range(self.crossword.width):
                if self.crossword.structure[i][j]:
                    print(letters[i][j] or " ", end="")
                else:
                    print("█", end="")
            print()

    def save(self, assignment, filename):
        """
        Save crossword assignment to an image file.
        """
        from PIL import Image, ImageDraw, ImageFont
        cell_size = 100
        cell_border = 2
        interior_size = cell_size - 2 * cell_border
        letters = self.letter_grid(assignment)

        # Create a blank canvas
        img = Image.new(
            "RGBA",
            (self.crossword.width * cell_size,
             self.crossword.height * cell_size),
            "black"
        )
        font = ImageFont.truetype("assets/fonts/OpenSans-Regular.ttf", 80)
        draw = ImageDraw.Draw(img)

        for i in range(self.crossword.height):
            for j in range(self.crossword.width):

                rect = [
                    (j * cell_size + cell_border,
                     i * cell_size + cell_border),
                    ((j + 1) * cell_size - cell_border,
                     (i + 1) * cell_size - cell_border)
                ]
                if self.crossword.structure[i][j]:
                    draw.rectangle(rect, fill="white")
                    if letters[i][j]:
                        _, _, w, h = draw.textbbox((0, 0), letters[i][j], font=font)
                        draw.text(
                            (rect[0][0] + ((interior_size - w) / 2),
                             rect[0][1] + ((interior_size - h) / 2) - 10),
                            letters[i][j], fill="black", font=font
                        )

        img.save(filename)

    def solve(self):
        """
        Enforce node and arc consistency, and then solve the CSP (constraint satisfaction problem).
        """
        self.enforce_node_consistency()
        self.ac3()
        return self.backtrack(dict())

    def enforce_node_consistency(self):
        """
        Update `self.domains` such that each variable is node-consistent.
        (Remove any values that are inconsistent with a variable's unary
         constraints; in this case, the length of the word.)
        """

        for var in self.domains:
            for word in self.domains[var].copy():
                if len(word) != var.length:
                    self.domains[var].remove(word)

        return

    def revise(self, x, y) -> bool:
        """
        Make variable `x` arc consistent with variable `y`.
        To do so, remove values from `self.domains[x]` for which there is no
        possible corresponding value for `y` in `self.domains[y]`.

        Return True if a revision was made to the domain of `x`; return
        False if no revision was made.
        """

        revision_made: bool = False
        overlap: Optional[tuple[int, int]] = self.crossword.overlaps[x, y]

        if not overlap:
            return revision_made

        (x_index, y_index) = overlap
        removed_x_words = set()

        for x_word in self.domains[x]:
            y_words = self.domains[y] - {x_word}
            if all(x_word[x_index] != y_word[y_index] for y_word in y_words):
                removed_x_words.add(x_word)

        self.domains[x] -= removed_x_words

        return False if len(removed_x_words) == 0 else True


    def ac3(self, arcs=None):
        """
        Update `self.domains` such that each variable is arc consistent.
        If `arcs` is None, begin with initial list of all arcs in the problem.
        Otherwise, use `arcs` as the initial list of arcs to make consistent.

        Return True if arc consistency is enforced and no domains are empty;
        return False if one or more domains end up empty.
        """

        if arcs == []:
            return True

        if arcs is None:
            # all the words which can overlap when entered into the crossword structure
            arcs = list(self.crossword.overlaps.keys())

        while arcs:
            x, y = arcs.pop()
            if self.revise(x, y):
                # if the domain of x is empty, then the crossword cannot be solved
                if not self.domains[x]:
                    return False
                # if the domain of x is not empty, then we need to check all x neighbors
                # to see if they are still arc consistent with x
                # (i.e. if there are still words that fit between the two word-spaces)
                for x_neighbours in self.crossword.neighbors(x) - {y}:
                    arcs.append((x_neighbours, x))


        return True

    def assignment_complete(self, assignment):
        """
        Return True if `assignment` is complete (i.e., assigns a value to each
        crossword variable); return False otherwise.
        """

        for variable in self.domains.keys():
            if variable not in assignment:
                return False

        for _, value in assignment.items():
            if not value:
                return False

        return True

    def consistent(self, assignment):
        """
        Return True if `assignment` is consistent (i.e., words fit in crossword
        puzzle without conflicting characters); return False otherwise.
        """

        # check that all values are distinct
        if len(set(assignment.values())) != len(assignment.values()):
            return False

        # check that all values are the correct length
        for variable, value in assignment.items():
            if variable.length != len(value):
                return False

        # check that all values are consistent with neighbors
        for variable, value in assignment.items():
            for neighbour in self.crossword.neighbors(variable):
                if neighbour in assignment:
                    (variable_index, neighbour_index) = self.crossword.overlaps[variable, neighbour]
                    if value[variable_index] != assignment[neighbour][neighbour_index]:
                        return False

        return True

    def order_domain_values(self, var, assignment):
        """
        Return a list of values in the domain of `var`, in order by
        the number of values they rule out for neighboring variables.
        The first value in the list, for example, should be the one
        that rules out the fewest values among the neighbors of `var`.
        """

        domain_values = self.domains[var]

        domain_values_with_elimination_count = dict()

        for value in domain_values:
            domain_values_with_elimination_count[value] = 0
            for neighbor in self.crossword.neighbors(var):
                if neighbor in assignment:
                    # count the value where it is repeated in the domain of a neighbor
                    # as this prevents the neighbor from being assigned to the same value
                    if value in self.domains[neighbor]:
                        domain_values_with_elimination_count[value] += 1
                    (var_index, neighbor_index) = self.crossword.overlaps[var, neighbor]
                    # also count the value when it is inconsistent with a neighbor value in the neighbour's domain
                    # as this prevents the neighbour from being assigned to the clashing value
                    # if value[var_index] != assignment[neighbor][neighbor_index]:
                    #     domain_values_with_elimination_count[value] += 1

        sorted_domain_values_by_elimination_count = sorted(domain_values_with_elimination_count,
                                                           key=lambda item: item[1])

        return sorted_domain_values_by_elimination_count


    def select_unassigned_variable(self, assignment):
        """
        Return an unassigned variable not already part of `assignment`.
        Choose the variable with the minimum number of remaining values
        in its domain. If there is a tie, choose the variable with the highest
        degree. If there is a tie, any of the tied variables are acceptable
        return values.
        """

        if len(assignment) >= len(self.domains):
            raise ValueError("No unassigned variables remaining")

        var_with_domain_values = dict()


        # Select the variable with the fewest number of remaining values in its domain.

        var_with_domain_values = {var: len(self.domains[var]) for var in self.domains.keys() \
                                        if var not in assignment}

        if len(var_with_domain_values) == 0:
            raise ValueError("No unassigned variables remaining")

        if len(var_with_domain_values) == 1:
            return list(var_with_domain_values.keys())[0]

        sorted_var_with_domain_values = sorted(var_with_domain_values.items(),
                                               key=lambda item: item[1] )

        # If tied, list all the variables with the minimum number of remaining values in its domain
        min_domain_value = sorted_var_with_domain_values[0][1]
        min_domain_value_vars = [var[0] for var in sorted_var_with_domain_values \
                                        if var[1] == min_domain_value]


        # If there is a tie between variables, choose the one
        # with the largest degree (has the most neighbors).
        sorted_vars_by_degree = sorted(min_domain_value_vars, \
                                       key=lambda item: len(self.crossword.neighbors(item)),
                                       reverse=True)

        # If there is a tie in both cases, choose arbitrarily.
        return sorted_vars_by_degree[0]


    def backtrack(self, assignment) -> Optional[dict]:
        """
        Using Backtracking Search, take as input a partial assignment for the
        crossword and return a complete assignment if possible to do so.

        `assignment` is a mapping from variables (keys) to words (values).

        If no assignment is possible, return None.
        """

        # if the assignment is complete, return it
        if self.assignment_complete(assignment):
            return assignment

        # select an unassigned variable
        var = self.select_unassigned_variable(assignment)

        # for each value in the domain of the variable
        for value in self.order_domain_values(var, assignment):
            # add the value to the assignment
            assignment[var] = value
            # if the assignment is consistent, then recurse
            if self.consistent(assignment):
                result = self.backtrack(assignment)
                if result:
                    return result
            # if the assignment is not consistent, remove the value from the assignment
            assignment.pop(var)

        return None


def main():

    # Check usage
    if len(sys.argv) not in [3, 4]:
        sys.exit("Usage: python generate.py structure words [output]")

    # Parse command-line arguments
    structure = sys.argv[1]
    words = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) == 4 else None

    # Generate crossword
    crossword = Crossword(structure, words)
    creator = CrosswordCreator(crossword)
    assignment = creator.solve()

    # Print result
    if assignment is None:
        print("No solution.")
    else:
        creator.print(assignment)
        if output:
            creator.save(assignment, output)


if __name__ == "__main__":
    main()
