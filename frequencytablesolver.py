 # Simple Solver for a Small Rectangular Table of Frequencies in .csv format, using Chi-Square as the Objective Fiunction
from datetime import datetime
import json
import multiprocessing as mp
import numpy as np
import random
import time

class FrequencyTableSolver():

    def __init__(self, input_file_name, output_file_name):

        np.seterr(all='raise')
        np.set_printoptions(precision=5)

        self.iteration = None
        self.minimum_error = 0
        self.one_dimensional_distances = None
        self.products_of_multipliers = None

        self.input_file_name = input_file_name
        self.output_file_name = output_file_name
        self.read_csv_data(self.input_file_name)
        self.nrow, self.ncol = np.shape(self.data)

        print(f'row_labels: {self.row_labels}')
        print(f'column_labels: {self.column_labels}')
        print(f'data: {self.data}')

        self.initialize_parameter_list()
        self.initialize_starting_point()


    def show_state(self, tag):
        print()
        print(15*'=')
        print(f'Solver status at {tag} {datetime.now()}')
        print(f'iteration: {self.iteration}')
        print(f'rx: {self.rx}')
        print(f'cx: {self.cx}')
        print(f'rm: {self.rm}')
        print(f'cm: {self.cm}')
        print(f'a: {self.a:.5f}')
        print(f'error: {self.minimum_error:.5f}')
        self.save_solution_to_file()


    def read_csv_data(self, file_name):
        with open(file_name, 'r') as infile:
            text = infile.read()
        lines = text.split('\n')                    # split file in to lines separated by the invisible character \r
        lines = [line.split(',') for line in lines] # convert each line to a list of its column values
        input_as_array = np.array(lines)            # convert to np array format
        self.column_labels = input_as_array[0,1:]   # first column of array (from second row to end)
        self.row_labels = input_as_array[1:,0]      # first row of array (from second column to endd)
        self.data = input_as_array[1:, 1:].astype("float")


    def save_solution_to_file(self):
        with open(self.output_file_name, 'a') as file:
            file.write(json.dumps({
                'iteration': self.iteration,
                'row_labels': self.row_labels.tolist(),
                'column_labels': self.column_labels.tolist(),
                'rx': self.rx.tolist(),
                'cx': self.cx.tolist(),
                'rm': self.rm.tolist(),
                'a': self.a,
                'error': self.evaluate(),
                'data': self.data.tolist(),
                'fitted_frequencies': self.fitted_frequencies.tolist()
            }) + '\n')


    def get_random_starting_point(self):
        # Multipliers
        # Use the row and column factors of the standard zero correlation model for tabular data
        self.total = np.sum(self.data)
        print("total", self.total)
        self.rm = np.sum(self.data, 1) / self.total**.5
        self.cm = np.sum(self.data, 0) / self.total **.5
        self.zero_correlation_model = np.outer(self.rm, self.cm)

        # Coordinates: Use random coordinates in the range + or = 1
        self.rx = 2.*(np.random.rand(self.nrow) - .5)
        self.cx = 2.*(np.random.rand(self.ncol) - .5)
        self.a = 2  # Initial estimate of attenuation

        self.standardize_multipliers()


    def standardize_multipliers(self):
        #standardize row multipliers and column multipliers to a common geometric mean
        row_geomean = self.rm.prod()**(1 / self.nrow)
        col_geomean = self.cm.prod()**(1 / self.ncol)
        common_mean = (row_geomean * col_geomean)**.5
        self.rm = self.rm * (common_mean / row_geomean)
        self.cm = self.cm * (common_mean / col_geomean)

        #standardize coordinates to mean
        s = self.rx.mean() + self.cx.mean()
        self.rx = self.rx - s
        self.cx = self.cx - s


    def initialize_starting_point(self, tries=20, iterations=2):
        best_error = None
        best_solution = None
        for random_start in range(tries):
            self.get_random_starting_point()
            self.show_state(f'Random start: {random_start}')
            error = self.solve(iterations=iterations)
            if best_error is None or error < best_error:
                best_solution = self.save_solution()

        #Continue from the best of the semi_starts.   Add lots of iterations.
        if best_solution is None: raise('no starting point')
        self.restore_solution(best_solution)


    def save_solution(self):
        return (self.rx, self.cx, self.rm, self.cm, self.a)


    def restore_solution(self, solution):
       self.rx, self.cx, self.rm, self.cm, self.a = solution


    def evaluate(self, hint=''):
        # Chi-square against zero correlation model
        one_dimensional_distances = np.absolute(np.subtract.outer(self.rx, self.cx))
        products_of_multipliers = (np.outer(self.rm, self.cm))
        self.fitted_frequencies = products_of_multipliers * 2**(-(one_dimensional_distances**self.a))
        return np.sum(((self.data - self.fitted_frequencies)**2) / self.fitted_frequencies)


    def evaluate_with_hint(self, hint=''):
        # Chi-square against zero correlation model
        if self.one_dimensional_distances is None or (hint == 'rx' or hint == 'cx'):
            self.one_dimensional_distances = np.absolute(np.subtract.outer(self.rx, self.cx))
        if self.products_of_multipliers is None or (hint == 'rm' or hint == 'cm'):
            self.products_of_multipliers = (np.outer(self.rm, self.cm))
        self.fitted_frequencies = self.products_of_multipliers * 2**(-(self.one_dimensional_distances**self.a))
        return np.sum(((self.data - self.fitted_frequencies)**2) / self.fitted_frequencies)



    # Solver optimization implementation

    def initialize_parameter_list(self):
        # Parameters are adjusted in random order, once per iteration
        # Build a list with one entry for each parameter; we shuffle the array below
        param_rx = [(self.twiddle_row_coordinate, i, 'rx') for i in range(self.nrow)]       # row coordinate i
        param_rm = [(self.twiddle_row_multiplier, i, 'rm') for i in range(self.nrow)]       # row multiplier i
        param_cx = [(self.twiddle_column_coordinate, i, 'cx') for i in range(self.ncol)]    # column ccoordinate i
        param_cm = [(self.twiddle_column_multiplier, i, 'cm') for i in range(self.ncol)]    # column multiplier i
        param_a  = [(self.twiddle_a, 0, 'a')]                                               # attenuation and two dummy values
        self.parameters = param_rx + param_rm + param_cx + param_cm + param_a


    def update_parameter_list(self):
        # Shuffle the parameters so the solving proceeds in random order
        random.shuffle(self.parameters)


    # Methods to step each parameter type down the goodness-of-fit gradient

    def twiddle_row_multiplier(self, i):
        self.rm[i] *= self.rm_delta[i]
        right_error = self.evaluate(hint='rm')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.rm_delta[i] *= 1.01
        else:
            self.rm[i] /= self.rm_delta[i]**2
            left_error = self.evaluate(hint='rm')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.rm_delta[i] /= 1.01    
            else:
                self.rm[i] *= self.rm_delta[i]
                self.rm_delta[i] **= .5
        return(('rm', i, self.rm[i], self.rm_delta[i]))

    def twiddle_column_multiplier(self, i):
        self.cm[i] *= self.cm_delta[i]
        right_error = self.evaluate(hint='cm')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.cm_delta[i] *= 1.01        
        else:
            self.cm[i] /= self.cm_delta[i]**2
            left_error = self.evaluate(hint='cm')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.cm_delta[i] /= 1.01
            else:
                self.cm[i] *= self.cm_delta[i]
                self.cm_delta[i] **= .5
        return(('cm', i, self.cm[i], self.cm_delta[i]))

    def twiddle_row_coordinate(self, i):
        self.rx[i] += self.rx_delta[i]
        right_error = self.evaluate(hint='rx')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.rx_delta[i] *= 1.1
        else:
            self.rx[i] -= 2 * self.rx_delta[i]
            left_error = self.evaluate(hint='rx')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.rx_delta[i] *= -1.1
            else:
                self.rx[i] += self.rx_delta[i]
                self.rx_delta[i] *= .5
        return(('rx', i, self.rx[i], self.rx_delta[i]))

    def twiddle_column_coordinate(self, i):
        self.cx[i] += self.cx_delta[i]
        right_error = self.evaluate(hint='cxx')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.cx_delta[i] *= 1.1        
        else:
            self.cx[i] -= 2 * self.cx_delta[i]
            left_error = self.evaluate(hint='cxx')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.cx_delta[i] *= -1.1
            else:
                self.cx[i] += self.cx_delta[i]
                self.cx_delta[i] *= .5
        return(('cx', i, self.cx[i], self.cx_delta[i]))

    def twiddle_a(self, i):
        self.a += self.a_delta
        right_error = self.evaluate(hint='a')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.a_delta += .0001       
        else:
            self.a -= 2 * self.a_delta
            left_error = self.evaluate(hint='a')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.a_delta = - (self.a_delta +.0001)  
            else:
                self.a = self.a + self.a_delta
                self.a_delta += .0001
        return(('a', i, self.a, self.a_delta))


    def initialize_deltas(self):
        self.rx_delta = np.zeros_like(self.rx) + .1
        self.cx_delta = np.zeros_like(self.cx) + .1
        self.rm_delta = np.ones_like(self.rm) * 1.1
        self.cm_delta = np.ones_like(self.cm) * 1.1
        self.a_delta = .001


    def solve(self, iterations=1):
        self.t_solve_start = time.time()
        self.initialize_deltas()
        self.error_list = []
        for self.iteration in range(iterations):
            self.t_start = time.time()
            self.minimum_error = self.evaluate()
            self.update_parameter_list()
            for parameter in self.parameters:
                parameter[0](parameter[1])      # call the parameter stepping function
            self.error_list.append([self.iteration, self.minimum_error])
            self.t_end = time.time()
            if (self.iteration % 1000) == 0:
                self.show_state(f'Iteration: {self.iteration} dt:{self.t_end-self.t_start:.4f}')
        self.t_solve_end = time.time()


    def twiddle_one_parameter(self, parameter):
        #print('twiddle:', parameter[2], parameter[1])
        return parameter[0](parameter[1])


    def update_parameter(self, update):
        if update[0] == 'rx':
            self.rx[update[1]] = update[2]
            self.rx_delta[update[1]] = update[3]
        elif update[0] == 'cx':
            self.cx[update[1]] = update[2]
            self.cx_delta[update[1]] = update[3]
        elif update[0] == 'rm':
            self.rm[update[1]] = update[2]
            self.rm_delta[update[1]] = update[3]
        elif update[0] == 'cm':
            self.cm[update[1]] = update[2]
            self.cm_delta[update[1]] = update[3]
        elif update[0] == 'a':
            self.a = update[2]
            self.a_delta = update[3]


    def solve_parallel(self, iterations=1):
        self.t_solve_start = time.time()
        self.initialize_deltas()
        self.error_list = []
        pool = mp.Pool(mp.cpu_count())
        #pool = mp.Pool(1)

        for self.iteration in range(iterations):
            self.t_start = time.time()
            self.minimum_error = self.evaluate()
            self.update_parameter_list()
    
            results = pool.map_async(self.twiddle_one_parameter, [parameter for parameter in self.parameters]).get()
            #print('pool result:', results)
            for result in results:
                self.update_parameter(result)

            # update worker processes with new solution
            context = self.save_solution()
            results = pool.apply(self.restore_solution, args=(context)).get()

            self.error_list.append([self.iteration, self.minimum_error])
            self.t_end = time.time()
            if (self.iteration % 100) == 0:
                self.show_state(f'Iteration: {self.iteration} dt:{self.t_end-self.t_start:.4f}')

        pool.close()
        pool.join()
        self.t_solve_end = time.time()

if __name__ == "__main__":

    file_name = "degree by family income_6x12.csv"

    solver = FrequencyTableSolver(file_name, 'output.csv')
    solver.show_state('STARTING POINT SOLUTION')

    profile = False
    if profile:
        import cProfile, io, pstats
        pr = cProfile.Profile()
        pr.enable()
        solver.solve(iterations=1000)
        #solver.solve_parallel(iterations=1000)
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats(pstats.SortKey.CUMULATIVE)
        ps.print_stats()
        print(s.getvalue())
    else:
        solver.solve(iterations=10000)
        #solver.solve_parallel(iterations=1000)

    solver.show_state('ENDING POINT SOLUTION')

    print(f'error_list: {solver.error_list}')
    print(f'data: {solver.data}')
    print(f'fitted_frequencies: {solver.fitted_frequencies}')
    print(f'iterations/second: {(solver.iteration+1)/(solver.t_solve_end-solver.t_solve_start):.1f}')