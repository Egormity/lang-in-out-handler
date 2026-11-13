"""Immutable ordered pen input shared by the canvas and stroke recognizers."""

from dataclasses import dataclass

InkPoint = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class InkSnapshot:
    """Pixel coordinates with elapsed milliseconds, grouped by pen-down stroke."""

    width: float
    height: float
    strokes: tuple[tuple[InkPoint, ...], ...]

    def __post_init__(self):
        # Do not retain mutable lists supplied by callers or live canvas events.
        object.__setattr__(self, "width", float(self.width))
        object.__setattr__(self, "height", float(self.height))
        object.__setattr__(self, "strokes", tuple(
            tuple(tuple(float(value) for value in point) for point in stroke)
            for stroke in self.strokes
        ))

    def __bool__(self):
        return any(self.strokes)
