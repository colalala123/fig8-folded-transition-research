"""Offline building block for a separately authorized recovery.

Keep native historical messages as evidence, but only decide a stage on the
messages it emitted. Preserve multiplicity so repeated errors aren't hidden.
"""
from collections import Counter

def new_messages(before, after):
    previous=Counter(before)
    new=[]
    for message in after:
        if previous[message]>0:
            previous[message]-=1
        else:
            new.append(message)
    return new
