import datetime

def log(rawlogfile, log, context="default", datet = None):
    f = open(rawlogfile, "a")
    if datet:
        print(f"--Log: {datet} --{context}--", file=f)
    else:
        print(f"--Log: {datetime.datetime.now()} --{context}--", file=f)
    print(log,file=f)
    f.close()

def inlog(log, context="default"):
    temp_str = f"--Internal: {datetime.datetime.now()} --{context}--"
    temp_str += f"\n{log}"
    return temp_str