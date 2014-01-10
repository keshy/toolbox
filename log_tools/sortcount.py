#!/usr/bin/env python
import sys
if __name__ == "__main__":
    dictionary = {}
    for item in sys.stdin.readlines():
        item = item.strip()
	dictionary[item] = dictionary[item]+1 if item in dictionary else 1
    for name, count in sorted(dictionary.iteritems(), key=lambda x:x[1]):
        sys.stdout.write("%d\t%s\n" % (count, name))
