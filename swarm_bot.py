# swarm optimizer worker

import argparse
from datetime import datetime
import os
from subprocess import DEVNULL, Popen
import random
import sys
import socketio
import threading
import time
import traceback
from frequencytablesolver import FrequencyTableSolver

class SwarmBot():

    def __init__(self, url='localhost:5000'):
        #print('Starting bot...')
        random.seed()
        self.server_url = url
        self.verbose = True
        self.name = 'Solver-' + str(random.randrange(1000))
        self.last_update_time = time.time()
        self.update_interval = 2
        self.best_error = None
        self.last_best_error = None
        self.solution_update = None
        self.solver = FrequencyTableSolver()

        self.sio = None
        self.init_socketio()

        self.running = False
        self.solver_thread = threading.Thread(target=self.solver_task)
        self.solver_thread.start()
    
    def init_socketio(self):
        self.sio = socketio.Client(logger=False, request_timeout=61)
        self.sio.eio.ping_interval = 62
        self.sio.eio.ping_timeout = 63

        self.sio.on('connect', self.handle_connect)
        self.sio.on('connect_error', self.handle_connect_error)
        self.sio.on('disconnect', self.handle_disconnect)
        self.sio.on('error', self.handle_error)

        self.sio.on('time', self.handle_time)
        self.sio.on('command', self.handle_command)
        #self.sio.connect(self.server_url, headers={'iam':'bot', 'name':self.name, 'pid': os.getpid()}, transports=['polling'])
        self.sio.connect(self.server_url, transports=['polling'])

    def now(self):
        return str(datetime.now())

    def log(self, *args):
        if self.verbose:
            out = ''
            for arg in args:
                out = out + ' ' + str(arg)
            print(self.now(), out)
            sys.stdout.flush()

    def handle_connect(self):
        print(self.now(), 'Connected:', self.name, self.sio.sid, self.sio.reconnection_delay, self.sio.reconnection_delay_max)
        self.log('sio:', dir(self.sio))
        self.send_iam('command')
        return True

    def handle_connect_error(self, msg):
        print('Connection failed', self.name, self.sio.connected, msg)
        #if not self.sio.connected:
        #    self.sio.connect(self.server_url)

    def handle_disconnect(self):
        #print(self.now(), 'Disconnected', self.name, self.sio.connected, traceback.format_stack())
        print(self.now(), 'Disconnected', self.name, self.sio.connected)
        #if not self.sio.connected:
        #    self.sio.connect(self.server_url)
        #self.terminate()
        return True

    def handle_error(self, err):
        print('handle_error:', err)

    def handle_time(self, msg):
        print('tick:', msg)
        pass

    def send(self, channel, msg):
        print(self.now(), 'sending:', self.name, channel, msg)
        self.sio.eio.ping_timeout = 63
        self.sio.emit(channel, msg)

    def send_iam(self, room):
        if not self.name:
            print('Error: No name in send_iam')
            return
        self.send('command', {
            'cmd': 'iam',
            'name': self.name,
            'bot': 'v1'
        })

    def handle_command(self, msg):
        try:
            self._handle_command(msg)
        except Exception as e:        
            print('exception in handle_command')
            print(str(e))
            print(sys.exc_info()[0])
            print(traceback.format_exc())
    
    def _handle_command(self, msg):

        #self.log('handle_lobby')
        print(self.now(), 'handle_command:', self.name, msg['cmd'], msg)

        if msg['cmd'] == 'update_job_data':
            self.solver.update_job_data(msg['job_data'])
            self.solver.initialize_parameter_list()
            if not hasattr(self.solver, 'rx'):
                self.solver.get_random_starting_point()
                self.running = True

        elif msg['cmd'] == 'update_solution':
            print(f'update_solution: solver.minimum_error: {self.solver.minimum_error}')
            if self.solver.minimum_error == None or msg['solution']['error'] < self.solver.minimum_error:
                self.solution_update = msg
                self.best_error = self.last_best_error = msg['solution']['error']
                print(f'updated solution: {self.solver.minimum_error} {self.best_error}')
            self.running = True

        elif msg['cmd'] == 'random_start':
            self.solver.initialize_starting_point()
            self.send('command', {
                'cmd': 'error',
                'name': self.name,
                'error': self.solver.evaluate()
            });
            self.running = True

        elif msg['cmd'] == 'send_solution':
            solution = {
                'cmd': 'solution',
                'name': self.name,
                'error': self.solver.minimum_error,
                'solution': {
                    'rx': self.solver.rx.tolist(),
                    'cx': self.solver.cx.tolist(),
                    'rm': self.solver.rm.tolist(),
                    'cm': self.solver.cm.tolist(),
                    'a': self.solver.a
                }
            }
            #print(f'sending solution: {solution}')
            self.send('command', solution)

        elif msg['cmd'] == 'run':
            self.running = True

        elif msg['cmd'] == 'stop':
            self.running = False
    
        elif msg['cmd'] == 'quit':
            self.sio.disconnect()
            os._exit(os.EX_OK)

        else:
            self.log('ignoring unrecognized message:', msg)

    def solver_task(self):

        while True:
            if self.running:

                t1 = time.time()
                iterations = 10
                random.seed()
                self.solver.solve(iterations=iterations)
                t2 = time.time()
                print(f'solver iterations/sec:{iterations/(t2-t1)} error {self.solver.minimum_error}')

                now = time.time()
                if self.solution_update != None:
                    print(f'solver_task: updating solution {self.solution_update}')
                    if self.solution_update['error'] < self.solver.minimum_error:
                        print(f'updating solution from server')
                        self.solver.update_solution(self.solution_update['solution'])
                        self.solution_update = None
                        self.last_update_time = now

                elif now - self.last_update_time > self.update_interval:
                    if self.last_best_error == None or self.solver.minimum_error < self.last_best_error:
                        self.last_update_time = now
                        self.last_best_error = self.solver.minimum_error
                        self.send('command', {
                            'cmd': 'error',
                            'name': self.name,
                            'error': self.solver.minimum_error
                        });

            self.sio.sleep(.020)


if __name__ == '__main__':

    parser = argparse.ArgumentParser('swarm bot')
    parser.add_argument('--update_interval', default=2, type=int)
    parser.add_argument('--url', default='http://localhost:5000')
    parser.add_argument('--workers', default=1, type=int)
    args = parser.parse_args()
    print('args:', args)

    if args.workers > 1:
        workers = []
        command = ['python3', 'swarm_bot.py']
        for worker in range(args.workers):
            workers.append(Popen(command, stdout=DEVNULL, stderr=DEVNULL))
            for worker in workers:
                worker.wait()

    else:
        swarm_bot = SwarmBot(url=args.url)
        #sio.wait()
