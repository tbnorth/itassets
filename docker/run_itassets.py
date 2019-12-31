import glob
import os
import sys

sys.path.append("/itassets")
import itassets

inputs = glob.glob(sys.argv[1])
sys.argv[1:] = ["--assets"] + inputs
os.chdir("/outputs")
itassets.main()
os.system("dot -Tpng -oassets.png -Tcmapx -oassets.map assets.dot")
with open("index.html", 'w') as out:
    out.write(open("/itassets/head.html").read())
    out.write(open("/outputs/assets.map").read())
    out.write(open("/itassets/tail.html").read())
