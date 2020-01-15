import glob
import sys

sys.path.append("/itassets")
import itassets

inputs = glob.glob(sys.argv[1])
cmd = '--output /outputs --theme light --assets'.split() + inputs
itassets.do_commandline(itassets.get_options(cmd))
cmd = '--output /outputs/dark --theme dark --assets'.split() + inputs
itassets.do_commandline(itassets.get_options(cmd))
