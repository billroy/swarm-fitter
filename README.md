Swarm Fitter


HOWTO

Get the code:
    git clone https://github.com/billroy/swarm-fitter.git
    cd swarm-fitter

Install required modules:

    pip3 install -r requirements.txt

In one terminal, start the swarm controller with one of these commands:
    
    # start just the controller (add workers manually below)
    python3 swarm.py

    # or start the controller and 12 worker subprocesses
    python3 swarm.py --workers=12

Start additional workers in separate terminals for better log visibility:

    # start a bot connected to the swarm controller on this machine
    python3 swarm_bot.py

    # or start a bot connected to the swarm controller on machine foobar.local
    python3 swarm_bot.py --url=http://foobar.local
    

