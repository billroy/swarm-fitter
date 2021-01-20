# Swarm solver boss

import argparse
from datetime import datetime
from flask import Flask, Response, redirect, render_template, request, session, send_file
from flask_socketio import Namespace, SocketIO, join_room, leave_room, rooms
import json
import multiprocessing as mp
import numpy as np
import os
from subprocess import DEVNULL, Popen
import sys
import threading
import time
import traceback

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
        self.socketio = SocketIO(self.app, always_connect=True)
        self.socketio.on_namespace(BossIO('/'))

        self.job_data = self.read_csv_data(args.input_file)
        print(f'job_data: {self.job_data}')
        self.solution = None
        self.best_error = None
        self.last_best_error = None
        self.last_update_time = time.time()

        self.workers = []
        if args.workers > 0:
            self.start_workers(args.workers)


    # initialize data
    def read_csv_data(self, file_name):
        print(f'loading file: {file_name}')
        with open(file_name, 'r') as infile:
            text = infile.read()
        lines = text.split('\n')                    # split file in to lines separated by the invisible character \r
        lines = [line.split(',') for line in lines] # convert each line to a list of its column values
        input_as_array = np.array(lines)            # convert to np array format
        column_labels = input_as_array[0,1:]   # first column of array (from second row to end)
        row_labels = input_as_array[1:,0]      # first row of array (from second column to endd)
        data = input_as_array[1:, 1:].astype('float')
        nrow, ncol = np.shape(data)
        return (nrow, ncol, column_labels.tolist(), row_labels.tolist(), data.tolist())


    def start_workers(self, num_workers):
        command = [
            'python3', 'swarm_bot.py'
        ]
        for worker in range(num_workers):
            self.workers.append(Popen(command, stdout=DEVNULL, stderr=DEVNULL))


    def serve_index(self):
        return render_template('index.html')


    # socket event handlers
    def handle_connect(self):
        print(datetime.now(), 'connect::', request.sid, request.host_url, request.headers, request.remote_addr, request.remote_user)

    def handle_command(self, msg):
        try:
            print('command:', msg)

            if msg['cmd'] == 'iam':
                self.socketio.emit('command', {'cmd': 'update_job_data', 'job_data': self.job_data})
                if self.solution is not None:
                    self.socketio.emit('command', {'cmd': 'update_solution', 'error': self.best_error, 'solution': self.solution})
                else:
                    self.socketio.emit('command', {'cmd': 'random_start'})

            elif msg['cmd'] == 'error':
                print(f'error: best_error: {self.best_error}')
                if self.best_error == None or msg['error'] < self.best_error:
                    print(f"new best_error candidate: {msg['error']}")
                    self.socketio.emit('command', {'cmd': 'send_solution'})
                else:
                    print(f'ignoring inferior error: {self.best_error} {msg["error"]}')
            
            elif msg['cmd'] == 'solution':
                if self.best_error == None or msg['error'] < self.best_error:
                    self.best_error = msg['error']
                    self.solution = msg['solution']

        except Exception as e:
            print('exception in dispatch_command')
            print(str(e))
            print(sys.exc_info()[0])
            print(traceback.format_exc())

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
                    self.socketio.emit('command', {'cmd': 'update_solution', 'error': self.best_error, 'solution': self.solution}, broadcast=True)

            self.socketio.sleep(1)


#@app.route('/')
#def index():
#    return render_template('index.html')


if __name__ == '__main__':

    # parse command line arguments
    default_workers = mp.cpu_count()
    parser = argparse.ArgumentParser('swarm controller')
    parser.add_argument('--update_interval', default=5, type=int)
    parser.add_argument('--workers', default=0, type=int)
    parser.add_argument('--bot_update_interval', default=5, type=int)
    parser.add_argument('--input_file', default='degree by family income_6x12.csv')
    parser.add_argument('--output_file', default='output.json')
    parser.add_argument('--port', default=5000, type=int)

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
        boss.socketio.run(boss.app, port=args.port, host='0.0.0.0')
