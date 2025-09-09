import typing

def parse_type(t):
    origin = typing.get_origin(t)
    if origin:
        base = t._name if hasattr(t, '_name') and t._name else origin.__name__
        args = typing.get_args(t)
        if origin in (list, set, tuple):
            subtypes = [parse_type(a) for a in args]
            return {"base": base, "subtypes": subtypes}
        elif origin is dict:
            key_type = parse_type(args[0]) if args else None
            value_type = parse_type(args[1]) if len(args) > 1 else None
            return {"base": base, "key_type": key_type, "value_type": value_type}
        elif origin is typing.Union:
            subtypes = [parse_type(a) for a in args]
            return {"base": "union", "subtypes": subtypes}
        else:
            subtypes = [parse_type(a) for a in args]
            return {"base": base, "subtypes": subtypes}
    else:
        name = getattr(t, "__name__", str(t))
        if name == "Any" or name.endswith(".Any"):
            return {"base": "any"}
        if t is list or t is set or t is tuple:
            return {"base": name, "subtypes": [{"base": "Any"}]}
        elif t is dict:
            return {"base": name, "key_type": {"base": "Any"}, "value_type": {"base": "Any"}}
        return {"base": name}
