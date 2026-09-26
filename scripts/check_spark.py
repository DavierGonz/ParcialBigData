import json
import sys
from urllib.request import urlopen

with urlopen('http://127.0.0.1:8080/json/', timeout=5) as response:
    state = json.load(response)
if sys.argv[1] == 'master':
    assert state['status'] == 'ALIVE'
else:
    assert state['masterurl'] == 'spark://spark-master-internal:7077'
