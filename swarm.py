# Swarm solver boss

import argparse
from datetime import datetime
from flask import Flask, Response, redirect, render_template, request, session, send_file
from flask_socketio import Namespace, SocketIO, join_room, leave_room, rooms
import json
import multiprocessing as mp
import numpy as np
import os
import random
from subprocess import DEVNULL, Popen
import sys
import threading
import time
import traceback

# use matplotlib without gui
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker

class BossIO(Namespace):

    def on_connect(self):
        global boss
        boss.handle_connect()

    def on_disconnect(self):
        pass
        #global boss
        #boss.handle_disconect()
    
    def on_command(self, msg):
        global boss
        boss.handle_command(msg)


class SwarmBoss():

    def __init__(self, args):

        self.args = args

        # Make Flask play nice with Vue templates by redefining the Flask/ Jinja
        # start and end tags so they don't conflict (both default to {{ }})
        class CustomFlask(Flask):
            jinja_options = Flask.jinja_options.copy()
            jinja_options.update(dict(
                variable_start_string='%%',  # Default is '{{', I'm changing this because Vue.js uses '{{' / '}}'
                variable_end_string='%%',
            ))
        self.app = CustomFlask(__name__)
        self.app.config['SECRET_KEY'] = 'secret-sauce!'
        self.app.route('/')(self.serve_index)
        self.app.route('/chart')(self.serve_chart)
        self.socketio = SocketIO(self.app, always_connect=True)
        self.socketio.on_namespace(BossIO('/'))

        self.job_data = self.read_csv_data(args.input_file)
        print(f'job_data: {self.job_data}')
        self.solution = None
        self.best_error = None
        self.last_best_error = None
        self.last_update_time = time.time()
        self.chart_number = 0

        self.workers = []
        if args.workers > 0:
            self.start_workers(args.workers)


    # initialize data
    def read_csv_data(self, file_name):
        self.input_file_name = file_name
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
        return (self.nrow, self.ncol, self.column_labels.tolist(), self.row_labels.tolist(), self.data.tolist())


    def start_workers(self, num_workers):
        command = [
            'python3', 'swarm_bot.py'
        ]
        for worker in range(num_workers):
            self.workers.append(Popen(command, stdout=DEVNULL, stderr=DEVNULL))
            #self.workers.append(Popen(command))


    def serve_index(self):
        return render_template('index.html')


    def serve_chart(self):
        print(f'serve_chart: {self.chart_file_name}')
        return send_file('output/' + self.chart_file_name, mimetype='image/png')


    # socket event handlers
    def handle_connect(self):
        print(datetime.now(), 'connect::', request.sid, request.host_url, request.headers, request.remote_addr, request.remote_user)


    def handle_command(self, msg):
        try:
            print('command:', msg)

            if msg['cmd'] == 'iam':
                if self.args.kill_bots:
                    self.socketio.emit('command', {'cmd': 'quit'}, room=request.sid)
                    return
                self.socketio.emit('command', {'cmd': 'update_job_data', 'filename': self.input_file_name, 'job_data': self.job_data}, room=request.sid)
                if self.solution is not None:
                    self.socketio.emit('command', {'cmd': 'update_solution', 'error': self.best_error, 'solution': self.solution}, room=request.sid)
                else:
                    self.socketio.emit('command', {'cmd': 'random_start'}, room=request.sid)

            elif msg['cmd'] == 'error':
                print(f'error: best_error: {self.best_error}')
                self.socketio.emit('error', {'cmd': 'error', 'name': msg['name'], 'error': msg['error']})
                if self.best_error == None or msg['error'] < self.best_error:
                    print(f"new best_error candidate: {msg['error']}")
                    self.socketio.emit('command', {'cmd': 'send_solution'}, room=request.sid)
                else:
                    print(f'ignoring inferior error: {self.best_error} {msg["error"]}')
            
            elif msg['cmd'] == 'solution':
                if self.best_error == None or msg['error'] < self.best_error:
                    self.best_error = msg['error']

                    # pull off the fitted_frequencies and delete them; the workers don't need it, and it's big
                    self.fitted_frequencies = msg['solution']['fitted_frequencies']
                    self.solution = msg
                    del self.solution['solution']['fitted_frequencies']

                    # could immediately update the other workers here
                    #self.socketio.emit('command', {'cmd': 'update_solution', 'solution': self.solution}, broadcast=True)

        except Exception as e:
            print('exception in dispatch_command')
            print(str(e))
            print(sys.exc_info()[0])
            print(traceback.format_exc())


    def log_solution(self):
        log_file = self.input_file_name.split('/')[-1].replace('.csv', '.json')
        print(f'saving solution: {log_file}')
        with open('output/' + log_file, 'a') as f:
            f.write(json.dumps(self.solution) + '\n')


    def update_chart(self):

        if not self.solution:
            print('aborting update_chart: no solution')
            return ''

        t_start = time.time()
        self.chart_number += 1
        self.chart_file_name = self.input_file_name.split('/')[-1].replace('.csv', '.png').replace(' ', '_')
        print(f'updating chart: {self.chart_file_name}')
        solution = self.solution['solution']

        fig = plt.figure()
        fig.set_size_inches(14, 14, forward=True)
        fig.subplots_adjust(hspace=.3)
        fig.suptitle(f'Swarm solution {self.chart_number}: error={self.solution["error"]} a={solution["a"]}', fontsize='xx-large')
        #loc = plticker.MultipleLocator(base=30)

        # column analysis
        ax = fig.add_subplot(3,1,1,
            title = 'Column Coordinates and Multipliers',
            xlabel = 'Column Coordinate',
            ylabel = 'Column Multiplier')
        ax.scatter(solution['cx'], solution['cm'])
        props = {'color':'black'}
        bottom, top = ax.get_ylim()
        text_base = bottom + 0.05 * (top-bottom)
        for i in range(len(solution['cx'])):
            cm = solution['cm'][i]
            ax.text(solution['cx'][i], text_base, f'{self.column_labels[i]} ({i} : {cm:0.3f})', props, rotation=90)

        # row analysis
        ax2 = fig.add_subplot(3,1,2, 
            title = 'Row Coordinates and Multipliers',
            xlabel = 'Row Coordinate',
            ylabel = 'Row Multiplier')
        ax2.scatter(solution['rx'], solution['rm'])
        props = {'color':'black'}
        bottom, top = ax2.get_ylim()
        text_base = bottom + 0.05 * (top-bottom)
        for i in range(len(solution['rx'])):
            rm = solution['rm'][i]
            ax2.text(solution['rx'][i], text_base, f'{self.row_labels[i]} ({i} : {rm:0.3f})', props, rotation=90)

        # data heatmap
        ax3 = fig.add_subplot(3,1,3, 
            title = 'Error Heat Map',
            xlabel = 'Column',
            ylabel = 'Row')
        ax3.imshow(self.data - self.fitted_frequencies, cmap='bwr', interpolation='nearest')
    
        plt.savefig('output/' + self.chart_file_name)
        plt.close()
        t_end = time.time()
        print(f'chart update time: {t_end-t_start} {self.chart_file_name}')
        return self.chart_file_name


    def solver_task(self):
        while True:
            print(f'solver task {self.best_error} {self.last_best_error}')
            now = time.time()
            if (now - self.last_update_time) > args.update_interval:
                print(f'solver task timer fired {self.best_error} {self.last_best_error}')
                self.last_update_time = now
                if self.best_error != None and (self.last_best_error == None or self.best_error < self.last_best_error):
                    self.last_best_error = self.best_error
                    print(f'sending updated solution: {self.best_error}')
                    self.socketio.emit('command', {'cmd': 'update_solution', 'solution': self.solution}, broadcast=True)
                    self.log_solution()
                    if self.update_chart():
                        self.socketio.emit('chart', {
                            'cmd': 'update_chart', 
                            'chart_url': '/chart?id=' + str(random.random())
                        }, broadcast=True)

            self.socketio.sleep(1)



if __name__ == '__main__':

    # parse command line arguments
    default_workers = mp.cpu_count()
    parser = argparse.ArgumentParser('python3 swarm.py')
    parser.add_argument('--update_interval', default=5, type=int)
    parser.add_argument('--workers', default=0, type=int)
    parser.add_argument('--input_file', default='data/degree by family income_6x12.csv')
    parser.add_argument('--port', default=5000, type=int)
    parser.add_argument('--kill_bots', default=0, type=int)

    args = parser.parse_args()
    print('args:', args)

    boss = SwarmBoss(args)

    # start the 1Hz thread
    solver_thread = threading.Thread(target=boss.solver_task)
    solver_thread.start()

    # run the server (never returns)
    if os.environ.get('PORT'):
        port = int(os.environ.get('PORT'))
        print('starting with port from environment 0.0.0.0:' + str(port))
        boss.socketio.run(boss.app, debug=False, port=port, host='0.0.0.0')
    else:
        print(f'starting on 0.0.0.0:{args.port}')
        boss.socketio.run(boss.app, debug=False, port=args.port, host='0.0.0.0')
