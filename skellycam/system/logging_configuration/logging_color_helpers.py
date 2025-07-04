def ensure_min_brightness(value: int, threshold=100):
    """Ensure the RGB value is above a certain threshold."""
    return max(value, threshold)


def ensure_not_grey(r: int, g: int, b: int, threshold_diff: int = 100):
    """Ensure that the color isn't desaturated grey by making one color component dominant."""
    max_val = max(r, g, b)
    if abs(r - g) < threshold_diff and abs(r - b) < threshold_diff and abs(g - b) < threshold_diff:
        if max_val == r:
            r = 255
        elif max_val == g:
            g = 255
        else:
            b = 255
    return r, g, b


def ensure_not_red(r: int, g: int, b: int, threshold_diff: int = 100):
    """Ensure that the color isn't too red (which looks like an error)."""
    if r - g > threshold_diff and r - b > threshold_diff:
        r = int(r / 2)
        if g > b:
            g = 255
        else:
            b = 255
    return r, g, b


def get_hashed_color(value: int):
    """Generate a consistent random color for the given value."""
    # Use modulo to ensure it's within the range of normal terminal colors.
    hashed = hash(value) % 0xFFFFFF  # Keep within RGB 24-bit color
    red = ensure_min_brightness(hashed >> 16 & 255)
    green = ensure_min_brightness(hashed >> 8 & 255)
    blue = ensure_min_brightness(hashed & 255)

    red, green, blue = ensure_not_grey(red, green, blue)
    red, green, blue = ensure_not_red(red, green, blue)

    return "\033[38;2;{};{};{}m".format(red, green, blue)
