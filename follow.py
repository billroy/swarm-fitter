import json
from pygtail import Pygtail
thing = None

for line in Pygtail('output.csv'):
    thing = json.loads(line.strip())
    iteration = thing['iteration']
    error = thing['error']
    print(f'iteration: {iteration} error: {error}')
