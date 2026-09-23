"""
Geometry utilities inspired by FreeCAD's draftgeoutils module.
Pure Python — no heavy dependencies.
"""
import math
from typing import List, Tuple

Point2D = Tuple[float, float]


class GeometryCalculator:

    @staticmethod
    def point_distance(p1: Point2D, p2: Point2D) -> float:
        return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

    @staticmethod
    def polyline_length(points: List[Point2D], closed: bool = False) -> float:
        """Total length of a polyline (sum of segment lengths)."""
        total = 0.0
        for i in range(len(points) - 1):
            total += GeometryCalculator.point_distance(points[i], points[i + 1])
        if closed and len(points) > 2:
            total += GeometryCalculator.point_distance(points[-1], points[0])
        return total

    @staticmethod
    def polygon_area(points: List[Point2D]) -> float:
        """
        Shoelace formula for polygon area.
        Works for any simple (non-self-intersecting) polygon.
        """
        n = len(points)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2.0

    @staticmethod
    def centroid(points: List[Point2D]) -> Point2D:
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        return (cx, cy)

    @staticmethod
    def offset_polyline(points: List[Point2D], offset: float) -> List[Point2D]:
        """
        Offset a polyline by a perpendicular distance.
        Useful for: wall centerline → wall face, pipe → excavation boundary.
        """
        result = []
        n = len(points)
        for i in range(n):
            if i == 0:
                dx = points[1][0] - points[0][0]
                dy = points[1][1] - points[0][1]
            elif i == n - 1:
                dx = points[-1][0] - points[-2][0]
                dy = points[-1][1] - points[-2][1]
            else:
                dx = points[i + 1][0] - points[i - 1][0]
                dy = points[i + 1][1] - points[i - 1][1]

            length = math.sqrt(dx ** 2 + dy ** 2)
            if length == 0:
                result.append(points[i])
                continue

            nx, ny = -dy / length, dx / length
            result.append((points[i][0] + nx * offset, points[i][1] + ny * offset))
        return result

    @staticmethod
    def bbox(points: List[Point2D]) -> Tuple[float, float, float, float]:
        """Return (min_x, min_y, max_x, max_y) bounding box."""
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return min(xs), min(ys), max(xs), max(ys)
