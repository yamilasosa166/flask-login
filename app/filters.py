from flask import Flask


def pyg(value) -> str:
    """Formato moneda PYG sin decimales con separador de miles (`.`).

    >>> pyg(1500000)
    'Gs. 1.500.000'
    """
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        n = 0
    return f"Gs. {n:,.0f}".replace(",", ".")


def register_filters(app: Flask) -> None:
    app.add_template_filter(pyg, "pyg")
