"""Text formatting shared by the SQL and ORM query scripts."""


def show_count(value):
    """Whole number with commas, like 19,290."""
    return f"{int(value):,}"


def show_percent(value):
    """Two decimals and a percent sign, like 50.09%."""
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def show_average(value):
    """Two decimals, like 3.79."""
    if value is None:
        return "N/A"
    return f"{value:.2f}"
