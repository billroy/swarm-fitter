 # Simple Solver for a Small Rectangular Table of Frequencies in .csv format, using Chi-Square as the Objective Fiunction
from datetime import datetime
import json
import numpy as np
import random
import time

class FrequencyTableSolver():

    def __init__(self):

        np.seterr(all='raise')
        np.set_printoptions(precision=5)
        self.output_file_name = 'output.json'

        self.iteration = None
        self.minimum_error = None
        self.one_dimensional_distances = None
        self.products_of_multipliers = None

        #self.initialize_starting_point()


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
        error = self.minimum_error
        if error == None: error = 0
        print(f'error: {error:.5f}')
        self.save_solution_to_file()


    def read_csv_data(self, file_name):
        print(f'loading file: {file_name}')
        with open(file_name, 'r') as infile:
            text = infile.read()
        lines = text.split('\n')                    # split file in to lines separated by the invisible character \r
        lines = [line.split(',') for line in lines] # convert each line to a list of its column values
        input_as_array = np.array(lines)            # convert to np array format
        self.column_labels = input_as_array[0,1:]   # first column of array (from second row to end)
        self.row_labels = input_as_array[1:,0]      # first row of array (from second column to endd)
        self.data = input_as_array[1:, 1:]
        self.data[self.data==''] = 0.0
        self.data = self.data.astype("float")
        self.nrow, self.ncol = np.shape(self.data)
        print(f'row_labels: {self.row_labels}')
        print(f'column_labels: {self.column_labels}')
        print(f'data: {self.data}')
        self.initialize_parameter_list()
        print(f'parameters: {len(self.parameters)}')



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
                'data': self.data.tolist()
                #'fitted_frequencies': self.fitted_frequencies.tolist()
            }) + '\n')


    def load_solution_from_file(self, file_name, index=-1):
        with open(file_name, 'r') as file:
            solution = json.loads(file.read().strip().split('\n')[index])
        return solution


    def update_job_data(self, update):
        self.nrow = update[0]
        self.ncol = update[1]
        self.column_labels = np.array(update[2])
        self.row_labels = np.array(update[3])
        self.data = np.array(update[4])


    def get_random_starting_point(self):
        # Multipliers
        # Use the row and column factors of the standard zero correlation model for tabular data
        self.total = np.sum(self.data)
        print("total", self.total)
        self.rm = np.sum(self.data, 1) / self.total**.5
        self.cm = np.sum(self.data, 0) / self.total **.5
        #self.zero_correlation_model = np.outer(self.rm, self.cm)

        # Coordinates: Use random coordinates in the range + or = 1
        self.rx = 2.*(np.random.rand(self.nrow) - .5)
        self.cx = 2.*(np.random.rand(self.ncol) - .5)
        self.a = 2  # Initial estimate of attenuation

        self.standardize_multipliers()


    def standardize_multipliers(self):
        #standardize row multipliers and column multipliers to a common geometric mean
        row_geomean = self.rm.prod()**(1 / self.nrow)
        if row_geomean == 0.0: raise Exception(f'Data error: Row geometric mean is zero.  Check for all-zero rows.')

        col_geomean = self.cm.prod()**(1 / self.ncol)
        if col_geomean == 0.0: raise Exception(f'Data error: Column geometric mean is zero.  Check for all-zero columns.')

        #print(f'standardize_multipliers: row_geomean={row_geomean}, col_geomean={col_geomean}, common_mean={common_mean}')

        common_mean = (row_geomean * col_geomean)**.5
        self.rm = self.rm * (common_mean / row_geomean)
        self.cm = self.cm * (common_mean / col_geomean)

        #standardize coordinates to mean
        s = self.rx.mean() + self.cx.mean()
        self.rx = self.rx - s
        self.cx = self.cx - s


    def initialize_starting_point(self, tries=20, iterations=50):
        best_error = None
        best_solution = None
        for random_start in range(tries):
            self.get_random_starting_point()
            self.show_state(f'Random start: {random_start}')
            self.solve(iterations=iterations)
            if best_error is None or self.evaluate() < best_error:
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
        t1 = time.time()
        one_dimensional_distances = np.absolute(np.subtract.outer(self.rx, self.cx))
        t2 = time.time()
        products_of_multipliers = (np.outer(self.rm, self.cm))
        t3 = time.time()
        self.fitted_frequencies = products_of_multipliers * 2**(-(one_dimensional_distances**self.a))
        t4 = time.time()
        # try exp
        #error np.sum(
        error = np.sum(((self.data - self.fitted_frequencies)**2) / self.fitted_frequencies)
        t5 = time.time()
        #print(f'eval tot (us):{1e6*(t5-t1):.3f} t2:{1e6*(t2-t1):.3f} t3:{1e6*(t3-t2):.3f} t4:{1e6*(t4-t3):.3f} t5:{1e6*(t5-t4):.3f}')
        return error


    def evaluate_with_hint(self, hint=''):
        # Chi-square against zero correlation model
        if self.one_dimensional_distances is None or hint == 'rx' or hint == 'cx':
            self.one_dimensional_distances = np.absolute(np.subtract.outer(self.rx, self.cx))
        if self.products_of_multipliers is None or hint == 'rm' or hint == 'cm':
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
        t1 = time.time()
        rm = self.rm[i]
        self.rm[i] *= self.rm_delta[i]
        right_error = self.evaluate(hint='rm')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.rm_delta[i] *= 1.01
        else:
            self.rm[i] = rm / self.rm_delta[i]
            left_error = self.evaluate(hint='rm')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.rm_delta[i] /= 1.01    
            else:
                self.rm[i] = rm
                self.rm_delta[i] **= .5
        #print(f'rm: {1e6*(time.time()-t1)}')
        #return(('rm', i, self.rm[i], self.rm_delta[i]))

    def twiddle_column_multiplier(self, i):
        cm = self.cm[i]
        self.cm[i] *= self.cm_delta[i]
        right_error = self.evaluate(hint='cm')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.cm_delta[i] *= 1.01        
        else:
            self.cm[i] = cm / self.cm_delta[i]
            left_error = self.evaluate(hint='cm')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.cm_delta[i] /= 1.01
            else:
                self.cm[i] = cm
                self.cm_delta[i] **= .5
        #return(('cm', i, self.cm[i], self.cm_delta[i]))

    def twiddle_row_coordinate(self, i):
        rx = self.rx[i]
        self.rx[i] += self.rx_delta[i]
        right_error = self.evaluate(hint='rx')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.rx_delta[i] *= 1.1
        else:
            self.rx[i] = rx - self.rx_delta[i]
            left_error = self.evaluate(hint='rx')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.rx_delta[i] *= -1.1
            else:
                self.rx[i] = rx
                self.rx_delta[i] *= .5
        #return(('rx', i, self.rx[i], self.rx_delta[i]))

    def twiddle_column_coordinate(self, i):
        cx = self.cx[i]
        self.cx[i] += self.cx_delta[i]
        right_error = self.evaluate(hint='cx')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.cx_delta[i] *= 1.1        
        else:
            self.cx[i] = cx - self.cx_delta[i]
            left_error = self.evaluate(hint='cx')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.cx_delta[i] *= -1.1
            else:
                self.cx[i] = cx
                self.cx_delta[i] *= .5
        #return(('cx', i, self.cx[i], self.cx_delta[i]))

    def twiddle_a(self, i):
        a = self.a
        self.a += self.a_delta
        right_error = self.evaluate(hint='a')
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.a_delta += .0001       
        else:
            self.a = a - self.a_delta
            left_error = self.evaluate(hint='a')
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.a_delta = - (self.a_delta +.0001)  
            else:
                self.a = a
                self.a_delta += .0001
        #return(('a', i, self.a, self.a_delta))


    def initialize_deltas(self):
        self.rx_delta = np.zeros_like(self.rx) + .1
        self.cx_delta = np.zeros_like(self.cx) + .1
        self.rm_delta = np.ones_like(self.rm) * 1.1
        self.cm_delta = np.ones_like(self.cm) * 1.1
        self.a_delta = .001


    def update_solution(self, msg):
        print(f'update solution: {msg}')
        self.rx = np.array(msg['solution']['rx'])
        self.cx = np.array(msg['solution']['cx'])
        self.rm = np.array(msg['solution']['rm'])
        self.cm = np.array(msg['solution']['cm'])
        self.a = msg['solution']['a']
        self.evaluate()


    def perturb_array(self, array, proportion):
        perturbation = array * (np.random.random(len(array)) - .5) * proportion
        print(f'perturbing: {array} {perturbation}')
        return array + perturbation


    def perturb_solution(self, msg):
        print(f'perturb solution: {msg}')
        self.rx = self.perturb_array(self.rx, msg['proportion'])
        self.cx = self.perturb_array(self.cx, msg['proportion'])
        self.rm = self.perturb_array(self.rm, msg['proportion'])
        self.cm = self.perturb_array(self.cm, msg['proportion'])
        self.a  = self.perturb_array([self.a], msg['proportion'])[0]
        self.evaluate()


    def solve(self, iterations=1):
        #print('Solving...', iterations)
        self.t_solve_start = time.time()
        #cutoff_ratio = .999995

        #random.seed()
        self.initialize_deltas()
        self.error_list = []
        for self.iteration in range(iterations):
            self.t_start = time.time()
            last_error = self.minimum_error = self.evaluate()
            self.update_parameter_list()
            for parameter in self.parameters:
                parameter[0](parameter[1])      # call the parameter stepping function
            self.error_list.append([self.iteration, self.minimum_error])
            self.t_end = time.time()
            if self.iteration and (self.iteration % 1000) == 0:
                self.show_state(f'Iteration: {self.iteration} dt:{self.t_end-self.t_start:.4f}')
                if last_error != None and self.iteration != 0:
                    ratio = self.minimum_error / last_error
                    print(f'ratio: {ratio}')
                    #if ratio > cutoff_ratio: break
                    last_error = self.minimum_error

        self.t_solve_end = time.time()
        return (self.minimum_error, self.save_solution())



if __name__ == "__main__":

    solver = FrequencyTableSolver()
    solver.read_csv_data("degree by family income_6x12.csv")
    solver.initialize_starting_point()
    solver.show_state('STARTING POINT SOLUTION')

    profile = False
    if profile:
        import cProfile, io, pstats
        pr = cProfile.Profile()
        pr.enable()
        solver.solve(iterations=1000)
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats(pstats.SortKey.CUMULATIVE)
        ps.print_stats()
        print(s.getvalue())
    else:
        solver.solve(iterations=100*150)

    solver.show_state('ENDING POINT SOLUTION')

    print(f'error_list: {solver.error_list}')
    print(f'data: {solver.data}')
    print(f'fitted_frequencies: {solver.fitted_frequencies}')
    print(f'iterations/second: {(solver.iteration+1)/(solver.t_solve_end-solver.t_solve_start):.1f}')
