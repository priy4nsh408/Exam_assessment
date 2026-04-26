def get_pyq(bt=None, co=None, unit=None):
    from pyq_processing.pyq_store import pyqs

    for q in pyqs:
        if (
            (bt is None or q["bt"] == bt) and
            (co is None or q["co"] == co) and
            (unit is None or q["unit"] == unit)
        ):
            return q

    return pyqs[0]  # fallback