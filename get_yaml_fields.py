import argparse
import os

import ruamel.yaml

parser = argparse.ArgumentParser()
parser.add_argument("path")
parser.add_argument("variable")
args = parser.parse_args()

if os.path.isfile(args.path):
    yaml = ruamel.yaml.YAML()
    with open(args.path) as file:
        value = yaml.load(file)
    keys = args.variable.split(".")
    wrong_key = False
    for i, el in enumerate(keys):
        value = value.get(el, None)
        if value is None:
            wrong_key = True
            break
    if not wrong_key:
        print(value)
    else:
        print("")
else:
    print("")
