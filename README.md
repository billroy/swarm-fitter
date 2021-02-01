Swarm Fitter


HOWTO

Get the code:
    git clone https://github.com/billroy/swarm-fitter.git
    cd swarm-fitter

Install required modules:

    pip3 install -r requirements.txt

In one terminal, start the swarm controller with one of these commands:
    (These load the EDU_INC data file by default...)
    # start just the controller (add workers manually below)
    python3 swarm.py

    # or start the controller and 12 worker subprocesses
    python3 swarm.py --workers=12

    # start with a different input file
    python3 swarm.py --input_file='data/Revere254X7.csv'

Start additional workers in separate terminals for better log visibility,
    or on different machines for scaling

    # start a bot connected to the swarm controller on this machine
    python3 swarm_bot.py

    # or start a bot connected to the swarm controller on machine foobar.local
    python3 swarm_bot.py --url=http://foobar.local
    

Tricks:
-------

Use 'jq' in --slurp mode to parse the line-by-line json output file

    # find the best error in a solution file:
    cat 'output/degree by family income_6x12.json' | jq --slurp '.[].error' | sort -n | head -n 1

    # show the values of 'a':
    cat 'output/degree by family income_6x12.json' | jq --slurp '.[].solution.a' | sort -n | head

Use 'tail' to pluck out a particular solution by line number

    # use 'tail' to pluck out the last saved solution and send it to jq to display the error:
    tail -n 1 'output/Senate_Votes 115-v2.json' | jq '.error'

Use 'pysparklines' to look at a thumbnail graph

    # sparkline of errors
    cat 'output/Senate_Votes 115-v2.json' | jq '.error' | sparkline
    ▇▃▃▃▃▃▃▃▃▃▂▂▂▂▂▂▂▂▂▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁

    # alternate form: sparkline of errors
    jq '.error' 'output/Senate_Votes 115-v2.json'| sparkline
    ▇▃▃▃▃▃▃▃▃▃▂▂▂▂▂▂▂▂▂▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁

    # sparkline of 'a' values
    cat 'output/Senate_Votes 115-v2.json' | jq '.solution.a' | sparkline
    ▁▁▁▁▁▁▁▁▂▂▂▂▂▂▂▂▂▂▂▂▄▄▄▄▄▄▄▄▄▄▄▆▆▆▆▆▆▆▆▆▆▆▆█████████████████████

    # sparkline of rx[0] values
    cat 'output/Senate_Votes 115-v2.json' | jq '.solution.rx[0]' | sparkline
    ██▁██████████████████████████▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄

Use 'termgraph' to make quick plots in the terminal

    # plot error vs. a across solutions
    jq -r '. |  "\(.error) \(.solution.a)"' 'output/Senate_Votes 115-v2.json' | termgraph

     jq -r '. |  "\(input_line_number) \(.error)"' 'output/Senate_Votes 115-v2.json' | termgraph
