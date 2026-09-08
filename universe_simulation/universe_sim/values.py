"""Small immutable value objects for the physical model."""
from __future__ import annotations

from dataclasses import dataclass
from math import acos, cos, sin, sqrt
from typing import Iterable


@dataclass(frozen=True, slots=True)
class GrandeurPhysique:
    """A scalar physical quantity stored in SI.

    `unit` documents the SI unit carried by `value`. This class intentionally
    does not become an entity in the physical MCD: it is a value object.
    """

    value: float
    unit: str
    uncertainty: float | None = None

    def require_non_negative(self) -> "GrandeurPhysique":
        if self.value < 0:
            raise ValueError(f"Expected non-negative {self.unit}, got {self.value}")
        return self

    def __float__(self) -> float:
        return float(self.value)


@dataclass(frozen=True, slots=True)
class Vecteur3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @staticmethod
    def zero() -> "Vecteur3":
        return Vecteur3()

    @staticmethod
    def from_iterable(values: Iterable[float]) -> "Vecteur3":
        x, y, z = values
        return Vecteur3(float(x), float(y), float(z))

    def __add__(self, other: "Vecteur3") -> "Vecteur3":
        return Vecteur3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vecteur3") -> "Vecteur3":
        return Vecteur3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self) -> "Vecteur3":
        return Vecteur3(-self.x, -self.y, -self.z)

    def __mul__(self, scalar: float) -> "Vecteur3":
        return Vecteur3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar: float) -> "Vecteur3":
        return self * scalar

    def __truediv__(self, scalar: float) -> "Vecteur3":
        if scalar == 0:
            raise ZeroDivisionError("Vector division by zero")
        return Vecteur3(self.x / scalar, self.y / scalar, self.z / scalar)

    def dot(self, other: "Vecteur3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vecteur3") -> "Vecteur3":
        return Vecteur3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def norm2(self) -> float:
        return self.dot(self)

    def norm(self) -> float:
        return sqrt(self.norm2())

    def normalized(self) -> "Vecteur3":
        n = self.norm()
        if n == 0:
            raise ValueError("Cannot normalize a zero vector")
        return self / n

    def distance_to(self, other: "Vecteur3") -> float:
        return (self - other).norm()

    def angle_with(self, other: "Vecteur3") -> float:
        denom = self.norm() * other.norm()
        if denom == 0:
            raise ValueError("Angle undefined for zero vector")
        c = max(-1.0, min(1.0, self.dot(other) / denom))
        return acos(c)

    def as_tuple(self) -> tuple[float, float, float]:
        return self.x, self.y, self.z


@dataclass(frozen=True, slots=True)
class Quaternion:
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @staticmethod
    def identity() -> "Quaternion":
        return Quaternion()

    @staticmethod
    def from_axis_angle(axis: Vecteur3, angle: float) -> "Quaternion":
        a = axis.normalized()
        s = sin(angle / 2.0)
        return Quaternion(cos(angle / 2.0), a.x * s, a.y * s, a.z * s)

    def __add__(self, other: "Quaternion") -> "Quaternion":
        return Quaternion(self.w + other.w, self.x + other.x, self.y + other.y, self.z + other.z)

    def __mul__(self, other: float | "Quaternion") -> "Quaternion":
        if isinstance(other, (float, int)):
            return Quaternion(self.w * other, self.x * other, self.y * other, self.z * other)
        a, b = self, other
        return Quaternion(
            a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
            a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
            a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
            a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
        )

    def __rmul__(self, scalar: float) -> "Quaternion":
        return self * scalar

    def norm(self) -> float:
        return sqrt(self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self) -> "Quaternion":
        n = self.norm()
        if n == 0:
            raise ValueError("Cannot normalize a zero quaternion")
        return Quaternion(self.w / n, self.x / n, self.y / n, self.z / n)

    def conjugate(self) -> "Quaternion":
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def rotate(self, vector: Vecteur3) -> Vecteur3:
        q = self.normalized()
        p = Quaternion(0.0, vector.x, vector.y, vector.z)
        r = q * p * q.conjugate()
        return Vecteur3(r.x, r.y, r.z)

    def derivative(self, omega: Vecteur3) -> "Quaternion":
        omega_q = Quaternion(0.0, omega.x, omega.y, omega.z)
        return 0.5 * (self * omega_q)


@dataclass(frozen=True, order=True, slots=True)
class Instant:
    seconds: float

    def shifted(self, duration: "Duree") -> "Instant":
        return Instant(self.seconds + duration.seconds)


@dataclass(frozen=True, slots=True)
class Duree:
    seconds: float

    def __float__(self) -> float:
        return float(self.seconds)
