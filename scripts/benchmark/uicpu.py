import os, time, sys
def find():
    for p in os.listdir('/proc'):
        if p.isdigit():
            try:
                if open(f'/proc/{p}/comm', errors='replace').read().strip().startswith('love'): return p
            except (OSError, UnicodeDecodeError): pass
pid = find(); hz = os.sysconf('SC_CLK_TCK')
print('pid', pid, open(f'/proc/{pid}/cmdline').read().replace('\0',' ')[:120])
def ticks():
    f = open(f'/proc/{pid}/stat').read().rsplit(')',1)[1].split(); return int(f[11]) + int(f[12])
def rss():
    for l in open(f'/proc/{pid}/status'):
        if l.startswith('VmRSS'): return int(l.split()[1]) // 1024
for w in range(int(sys.argv[1]) if len(sys.argv) > 1 else 3):
    a, t0 = ticks(), time.monotonic(); time.sleep(60); b, t1 = ticks(), time.monotonic()
    print(f'janela {w+1}: {100*(b-a)/hz/(t1-t0):.2f}% CPU · RSS {rss()} MB', flush=True)
