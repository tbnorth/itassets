import glob
import os
import sys

sys.path.append("/itassets")
import itassets

inputs = glob.glob(sys.argv[1])
sys.argv[1:] = ["--assets"] + inputs
os.chdir("/outputs")
itassets.main()
