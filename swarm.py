# Swarm solver boss

import argparse
from copy import deepcopy
from datetime import datetime
from flask import Flask, Response, redirect, render_template, request, session, send_file
from flask_socketio import SocketIO, join_room, leave_room, rooms
import glob
import json
import numpy as np
import os
import sys
import threading
import time
import traceback

# parse command line arguments
parser = argparse.ArgumentParser('swarm controller')
parser.add_argument('--update_interval', default=5, type=int)
parser.add_argument('--bot_update_interval', default=5, type=int)
parser.add_argument('--input_file', default='degree by family income_6x12.csv')
parser.add_argument('--output_file', default='output.json')
parser.add_argument('--port', default=5000, type=int)

args = parser.parse_args()
print('args:', args)


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
        app = CustomFlask(__name__)
        app.config['SECRET_KEY'] = 'secret-sauce!'

        self.job_data = self.read_csv_data(args.input_file)
        print(f'job_data: {self.job_data}')
        self.solution = None
        self.best_error = None
        self.last_best_error = None
        self.last_update_time = time.time()

        self.init_socketio()


    # initialize data
    def read_csv_data(file_name):
        print(f'loading file: {file_name}')
        with open(file_name, 'r') as infile:
            text = infile.read()
        lines = text.split('\n')                    # split file in to lines separated by the invisible character \r
        lines = [line.split(',') for line in lines] # convert each line to a list of its column values
        input_as_array = np.array(lines)            # convert to np array format
        column_labels = input_as_array[0,1:]   # first column of array (from second row to end)
        row_labels = input_as_array[1:,0]      # first row of array (from second column to endd)
        data = input_as_array[1:, 1:].astype("float")
        nrow, ncol = np.shape(data)
        return (nrow, ncol, column_labels.tolist(), row_labels.tolist(), data.tolist())


    def init_socketio(self):
        socketio.on('connect', handle_connect)
        socketio.on('command', handle_command)
        socketio = SocketIO(app, always_connect=True)


    # socket event handlers
    def handle_connect():
        print(datetime.now(), 'connect::', request.sid, request.host_url, request.headers, request.remote_addr, request.remote_user)

    def handle_command(msg):
        try:
            global best_error, solution
            print('command:', msg)

            if msg['cmd'] == 'iam':
                socketio.emit('command', {'cmd': 'update_job_data', 'job_data': job_data})
                if solution is not None:
                    socketio.emit('command', {'cmd': 'update_solution', 'error': best_error, 'solution': solution})
                else:
                    socketio.emit('command', {'cmd': 'random_start'})

            elif msg['cmd'] == 'error':
                print(f'error: best_error: {best_error}')
                if best_error == None or msg['error'] < best_error:
                    print(f"new best_error: {msg['error']}")
                    socketio.send('command', {'cmd': 'send_solution'})
                else:
                    print(f'ignoring inferior error: {best_error} {msg["error"]}')
            
            elif msg['cmd'] == 'solution':
                if best_error == None or msg['error'] < best_error:
                    best_error = msg['error']
                    solution = msg['solution']

        except Exception as e:
            print('exception in dispatch_command')
            print(str(e))
            print(sys.exc_info()[0])
            print(traceback.format_exc())

@app.route('/')
def index():
    return render_template('index.html')

def solver_task():
    while True:
        global best_error, last_best_error, last_update_time, solution

        #now = datetime.now()
        #now_str = str(now)[0:19]
        #msg = {'cmd': 'tick', 'time': now_str}
        #socketio.emit('time', msg, broadcast=True)
        print(f'solver task {best_error} {last_best_error}')
        now = time.time()
        if (now - last_update_time) > args.update_interval:
            print(f'timer fired {best_error} {last_best_error}')
            last_update_time = now
            if best_error != None and (last_best_error == None or best_error < last_best_error):
                last_best_error = best_error
                print(f'sending updated solution: {best_error}')
                socketio.emit('command', {'cmd': 'update_solution', 'error': best_error, 'solution': solution}, broadcast=True)

        socketio.sleep(1)


if __name__ == '__main__':

    # start the 1Hz thread
    solver_thread = threading.Thread(target=solver_task)
    solver_thread.start()

    # run the server (never returns)
    if os.environ.get('PORT'):
        port = int(os.environ.get('PORT'))
        print('starting with port from environment 0.0.0.0:' + str(port))
        socketio.run(app, debug=False, port=port, host='0.0.0.0')
    else:
        print(f'starting on 0.0.0.0:{args.port}')
        socketio.run(app, port=args.port, host='0.0.0.0')
