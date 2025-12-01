def colorise(col, s):
    color = {}
    color["red"] = "\033[0;31m"
    color["green"] = "\033[0;32m"
    color["yellow"] = "\033[1;33m"
    color["blue"] = "\033[0;34m"
    color["violet"] = "\033[0;35m"
    reset = "\033[0m"
    return color[col] + s + reset

def printcol(col, s, end="\n", flush=False):
    print(colorise(col, s), end=end, flush=flush)