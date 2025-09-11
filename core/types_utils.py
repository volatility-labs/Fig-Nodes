import typing


def parse_type(t):
    origin = typing.get_origin(t)
    if origin:
        # typing constructs like List, Dict, Union
        base = t._name if getattr(t, "_name", None) else ("union" if origin is typing.Union else getattr(origin, "__name__", str(origin)))
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
            return {"base": "Any"}
        if t in (list, set, tuple):
            return {"base": name, "subtypes": [{"base": "Any"}]}
        elif t is dict:
            return {"base": name, "key_type": {"base": "Any"}, "value_type": {"base": "Any"}}
        return {"base": name}
