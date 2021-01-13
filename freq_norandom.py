from frequencytablesolver import FrequencyTableSolver

class FrequencyTableSolverWithoutShuffle(FrequencyTableSolver):

    # The base class FrequencyTableSolver shuffles the parameters
    # This replacement for the parameter list update function simply does nothing,
    # so the parameters are stepped in the same order every iteration
    def update_parameter_list(self):
        pass

if __name__ == "__main__":

    file_name = "degree by family income_6x12.csv"

    solver = FrequencyTableSolverWithoutShuffle(file_name, 'output.csv')
    solver.show_state('STARTING POINT SOLUTION')

    solver.solve(iterations=10000)
    solver.show_state('ENDING POINT SOLUTION')

    print(f'error_list: {solver.error_list}')
    print(f'data: {solver.data}')
    print(f'fitted_frequencies: {solver.fitted_frequencies}')
