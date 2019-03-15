#!/usr/bin/env python3
import csv
from pathlib import Path
import typing

class Shrine(typing.NamedTuple):
    map_name: str
    title: str
    sub: str

root = Path(__file__).parent

def load_shrine_list():
    shrines: typing.List[Shrine] = []
    normal_shrines: typing.List[Shrine] = []
    blessing_shrines: typing.List[Shrine] = []
    combat_shrines: typing.List[Shrine] = []
    with (root/'shrine_list.csv').open('r') as f:
        for row in csv.DictReader(f):
            shrine = Shrine(row['map_name'], row['title'], row['sub'])
            if shrine.map_name in ['Dungeon009', 'Dungeon038', 'Dungeon041', 'Dungeon065', 'Dungeon099', 'Dungeon103']:
                shrines.append(shrine)
                continue
            if shrine.sub.endswith('Blessing'):
                blessing_shrines.append(shrine)
            elif shrine.sub.endswith('Test of Strength'):
                combat_shrines.append(shrine)
            else:
                normal_shrines.append(shrine)

    shrines.sort()
    normal_shrines.sort(reverse=True)
    blessing_shrines.sort(reverse=True)
    combat_shrines.sort(reverse=True)

    return (shrines, normal_shrines, blessing_shrines, combat_shrines)

def generate_shrines():
    shrines, normal_shrines, blessing_shrines, combat_shrines = load_shrine_list()

    counter = 0
    while normal_shrines or blessing_shrines or combat_shrines:
        m = counter % 5
        if normal_shrines and (m == 0 or m == 1 or m == 2):
            shrines.append(normal_shrines.pop())
        elif blessing_shrines and (m == 3):
            shrines.append(blessing_shrines.pop())
        elif combat_shrines and (m == 4):
            shrines.append(combat_shrines.pop())
        if counter == 60:
            shrines.append(blessing_shrines.pop())
        counter += 1

    return shrines

def main():
    shrines = generate_shrines()
    for i, shrine in enumerate(shrines):
        print(i, shrine)
    with (root/'shrine_rush_order.csv').open('w') as f:
        writer = csv.DictWriter(f, ['map_name', 'title', 'sub'])
        writer.writeheader()
        writer.writerows([shrine._asdict() for shrine in shrines])

if __name__ == '__main__':
    main()
