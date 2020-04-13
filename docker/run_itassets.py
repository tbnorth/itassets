import glob
import sys

sys.path.append("/itassets")
import itassets


def update(inputs):
    inputs = glob.glob(inputs)
    cmd = '--output /outputs --theme light --assets'.split() + inputs
    itassets.generate_all(itassets.get_options(cmd))
    cmd = '--output /outputs/dark --theme dark --assets'.split() + inputs
    itassets.generate_all(itassets.get_options(cmd))


def main():
    inputs = (sys.argv[1])
    update(inputs)


if __name__ == "__main__":
    main()
