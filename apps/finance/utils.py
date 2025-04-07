from decimal import Decimal


def floatify(data):
    """
    Рекурсивно преобразует все Decimal значения в float
    """
    if isinstance(data, dict):
        return {k: floatify(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [floatify(v) for v in data]
    elif isinstance(data, tuple):
        return tuple(floatify(v) for v in data)
    elif isinstance(data, Decimal):
        return float(data)
    else:
        return data