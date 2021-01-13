 # Simple Solver for a Small Rectangular Table of Frequencies in .csv format, using Chi-Square as the Objective Fiunction
from datetime import datetime
import json
import numpy as np
import random
import time

class FrequencyTableSolver():

    def __init__(self, input_file_name, output_file_name):

        #np.seterr(all='raise')
        self.iteration = None
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
        print(f'a: {self.a}')
        print(f'gof: {self.evaluate()}')


    def read_csv_data(self, file_name):
        with open(file_name, 'r') as infile:
            text = infile.read()
        lines = text.split('\n')                    # split file in to lines separated by the invisible character \r
        lines = [line.split(',') for line in lines] # convert each line to a list of its column values
        input_as_array = np.array(lines)            # convert to np array format
        self.column_labels = input_as_array[0,1:]   # first column of array (from second row to end)
        self.row_labels = input_as_array[1:,0]      # first row of array (from second column to endd)
        self.data = input_as_array[1:, 1:].astype("float")


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


    def initialize_starting_point(self, tries=2, iterations=2):
        best_gof = None
        best_solution = None
        for random_start in range(tries):
            self.get_random_starting_point()
            self.show_state(f'Random start: {random_start}')
            gof = self.solve(iterations=iterations)
            if best_gof is None or gof < best_gof:
                best_solution = self.save_solution()
                #self.file_best_parameters(best_solution)

        #Continue from the best of the semi_starts.   Add lots of iterations.
        if best_solution is None: raise('no starting point')
        self.restore_solution(best_solution)


    def save_solution(self):
        return (self.rx, self.cx, self.rm, self.cm, self.a)


    def restore_solution(self, solution):
       self.rx, self.cx, self.rm, self.cm, self.a = solution


    def get_fitted_frequencies(self):            #Implement Equation 1 from Prologue
        one_dimensional_distances = np.absolute(np.subtract.outer(self.rx, self.cx))
        products_of_multipliers = (np.outer(self.rm, self.cm))
        self.fitted_frequencies = products_of_multipliers * 2**(-(one_dimensional_distances**self.a))


    def evaluate(self):
        # Chi-square against zero correlation model
        self.get_fitted_frequencies()
        return np.sum(((self.data - self.fitted_frequencies)**2) / self.fitted_frequencies)


    def file_best_parameters(self):
        pass


    def save_output(self):
        print("Save output TBI")
        print(json.dumps(self))
        return


    # Solver optimization implementation

    def initialize_parameter_list(self):
        # Parameters are adjusted in random order, once per iteration
        # Build a list with one entry for each parameter; we shuffle the array below
        param_rx = [(self.step_row_coordinate, i) for i in range(self.nrow)]       # row coordinate i
        param_rm = [(self.step_row_multiplier, i) for i in range(self.nrow)]       # row multiplier i
        param_cx = [(self.step_column_coordinate, i) for i in range(self.ncol)]    # column ccoordinate i
        param_cm = [(self.step_column_multiplier, i) for i in range(self.ncol)]    # column multiplier i
        param_a  = [(self.step_a, 0)]                                              # attenuation and two dummy values
        self.parameters = param_rx + param_rm + param_cx + param_cm + param_a

    def update_parameter_list(self):
        # Shuffle the parameters so the solving proceeds in random order
        random.shuffle(self.parameters)

    # Methods to step each parameter type down the goodness-of-fit gradient

    def step_row_multiplier(self, i):
        self.rm[i] *= self.rm_delta[i]
        right_error = self.evaluate()
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.rm_delta[i] *= 1.01
        else:
            self.rm[i] /= self.rm_delta[i]**2
            left_error = self.evaluate()
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.rm_delta[i] /= 1.01    
            else:
                self.rm[i] *= self.rm_delta[i]
                self.rm_delta[i] **= .5

    def step_column_multiplier(self, i):
        self.cm[i] *= self.cm_delta[i]
        right_error = self.evaluate()
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.cm_delta[i] *= 1.01        
        else:
            self.cm[i] /= self.cm_delta[i]**2
            left_error = self.evaluate()
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.cm_delta[i] /= 1.01
            else:
                self.cm[i] *= self.cm_delta[i]
                self.cm_delta[i] **= .5

    def step_row_coordinate(self, i):
        self.rx[i] += self.rx_delta[i]
        right_error = self.evaluate()
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.rx_delta[i] *= 1.1
        else:
            self.rx[i] -= 2 * self.rx_delta[i]
            left_error = self.evaluate()
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.rx_delta[i] *= -1.1
            else:
                self.rx[i] += self.rx_delta[i]
                self.rx_delta[i] *= .5

    def step_column_coordinate(self, i):
        self.cx[i] += self.cx_delta[i]
        right_error = self.evaluate()
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.cx_delta[i] *= 1.1        
        else:
            self.cx[i] -= 2 * self.cx_delta[i]
            left_error = self.evaluate()
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.cx_delta[i] *= -1.1
            else:
                self.cx[i] += self.cx_delta[i]
                self.cx_delta[i] *= .5

    def step_a(self, i):
        self.a += self.a_delta
        right_error = self.evaluate()
        if right_error < self.minimum_error:
            self.minimum_error = right_error
            self.a_delta += .0001       
        else:
            self.a -= 2 * self.a_delta
            left_error = self.evaluate()
            if left_error < self.minimum_error:
                self.minimum_error = left_error
                self.a_delta = - (self.a_delta +.0001)  
            else:
                self.a = self.a + self.a_delta
                self.a_delta += .0001


    def initialize_deltas(self):
        self.rx_delta = np.zeros_like(self.rx) + .1
        self.cx_delta = np.zeros_like(self.cx) + .1
        self.rm_delta = np.ones_like(self.rm) *1.1
        self.cm_delta = np.ones_like(self.cm) *1.1
        self.a_delta = .001


    def solve(self, iterations=1):
        self.initialize_deltas()
        self.error_list = []
        for self.iteration in range(iterations):
            t_start = time.time()
            self.minimum_error = self.evaluate()
            self.update_parameter_list()
            for parameter in self.parameters:
                parameter[0](parameter[1])      # call the parameter stepping function
            self.error_list.append([self.iteration, self.evaluate()])
            if (self.iteration % 100) == 0:
                self.show_state(f'Iteration: {self.iteration}')
                print(self.error_list[-1], time.ctime())
            print('end iteration:', self.evaluate())
            t_end = time.time()
            print(f'iteration time: {t_end - t_start}')

if __name__ == "__main__":
    file_name = "degree by family income_6x12.csv"
    solver = FrequencyTableSolver(file_name, 'output.csv')
    solver.show_state('STARTING POINT SOLUTION')
    solver.solve(iterations=10000)
    solver.show_state('ENDING POINT SOLUTION')
    print(f'error_list: {solver.error_list}')
