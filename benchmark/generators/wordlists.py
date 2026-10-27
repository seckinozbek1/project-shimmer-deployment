"""Neutral words for headings, names and text values. Letters only, no digit anywhere,
so no identifier or name ever becomes a figure (INPUT_FORMAT section 2)."""
import random

TREES = ("Alder Aspen Birch Cedar Elder Hazel Holly Larch Maple Rowan Willow Yew Beech Linden "
         "Poplar Spruce Juniper Laurel Myrtle Olive Hawthorn Hornbeam Sorrel Tamarisk Acacia "
         "Banyan Cypress Fir Ginkgo Hickory Magnolia Mulberry Pine Redwood Sequoia Teak Walnut "
         "Wisteria Catalpa Locust").split()
BIRDS = ("Heron Kestrel Plover Wren Finch Lark Swift Egret Osprey Petrel Robin Starling "
         "Tern Thrush Curlew Dunlin Gannet Harrier Ibis Jay Kite Linnet Merlin Nightjar "
         "Oriole Pipit Quail Rail Siskin Twite Warbler Avocet Bittern Crane Dipper Eider "
         "Fulmar Grebe Hobby Knot Lapwing Martin Nuthatch Ouzel Puffin Raven Shrike").split()
FIRST = ("Ada Basil Clara Dorian Edith Felix Greta Hugo Irene Jonas Klara Leon Mara Nils "
         "Olga Pavel Rosa Stefan Tilda Viktor Wanda Yara").split()
LAST = ("Arden Brook Carver Dale Ellis Frost Garner Hale Irving Keller Lowe Marsh Noble "
        "Orton Pryce Quinn Rhodes Sutton Thorne Vance Webb York").split()
PLACES = ("North Basin|East Weir|South Reach|West Bank|Upper Ford|Lower Ford|Mill Race|"
          "Stone Pool|Reed Bed|Old Sluice|Long Pond|Bridge Pier").split("|")


def pick(rng, pool, n):
    if n > len(pool):
        raise ValueError("word pool too small")
    return rng.sample(list(pool), n)


def person(rng):
    return "%s %s" % (rng.choice(FIRST), rng.choice(LAST))


def letters_tag(rng, n=3):
    return "".join(rng.choice("BCDFGHJKLMNPQRSTVWXZ") for _ in range(n))


def reorder(n, rng, keep_together=()):
    """A permutation of range(n) that moves whole blocks, cut only where no pair in
    keep_together (unit indices that must stay adjacent) would be separated."""
    safe = [c for c in range(1, n)
            if not any(min(i, j) < c <= max(i, j) for i, j in keep_together)]
    if len(safe) < 2:
        raise ValueError("no safe cuts to reorder")
    a, b = sorted(rng.sample(safe, 2))
    order = list(range(b, n)) + list(range(a, b)) + list(range(0, a))
    if order == list(range(n)):
        raise ValueError("identity reorder")
    return order


def make_rng(family, seed):
    return random.Random("%s:%d" % (family, int(seed)))
