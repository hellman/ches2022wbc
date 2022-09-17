class Location(tuple):
    DIVS = ":.|$@~"

    def __str__(self):
        return _address_to_str(self, self.DIVS)

    def __add__(self, other):
        return Location(tuple(self) + tuple(other))

    def __getitem__(self, pos):
        res = super().__getitem__(pos)
        if isinstance(pos, slice):
            return Location(res)
        return res


def _address_to_str(addr, divs):
    ret = []
    for v in addr:
        if isinstance(v, tuple):
            ret.append(_address_to_str(v, divs[1:]))
        else:
            ret.append(str(v))
    return divs[0].join(ret)
