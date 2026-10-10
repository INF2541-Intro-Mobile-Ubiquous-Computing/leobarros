"""Trajeto aleatório contínuo no disco, em coordenadas relativas ao centro."""

import math
import random


class RandomCoreMotion:
    def __init__(self, radius, speed, interval, initial_angle, rng=None):
        if any(not math.isfinite(value) or value <= 0 for value in (radius, speed, interval)):
            raise ValueError('Raio, velocidade e intervalo aleatórios devem ser positivos e finitos.')
        self.radius = radius
        self.speed = speed
        self.interval = interval
        self.rng = rng if rng is not None else random
        angle = math.radians(initial_angle)
        self.position = (radius * math.cos(angle), radius * math.sin(angle))
        self.time = 0.0
        self.next_turn = interval
        self.choose_direction()

    def choose_direction(self):
        x, y = self.position
        if math.hypot(x, y) >= self.radius - 1e-9:
            # Exclui tangentes para não repetir colisões de comprimento zero.
            angle = math.atan2(-y, -x) + self.rng.uniform(-math.pi / 2 + 1e-6, math.pi / 2 - 1e-6)
        else:
            angle = self.rng.uniform(0, 2 * math.pi)
        self.direction = (math.cos(angle), math.sin(angle))

    def position_at(self, time):
        if not math.isfinite(time) or time < self.time:
            raise ValueError('O tempo do movimento aleatório deve avançar monotonamente.')
        while self.time < time:
            x, y = self.position
            dx, dy = self.direction
            dot = x * dx + y * dy
            distance = -dot + math.sqrt(max(0.0, dot * dot + self.radius ** 2 - x * x - y * y))
            boundary_time = self.time + max(0.0, distance) / self.speed
            end = min(time, self.next_turn, boundary_time)
            travel = (end - self.time) * self.speed
            self.position = (x + travel * dx, y + travel * dy)
            self.time = end
            at_boundary = end == boundary_time
            at_turn = end == self.next_turn
            if at_boundary:
                length = math.hypot(*self.position)
                self.position = tuple(value * self.radius / length for value in self.position)
            if at_turn:
                self.next_turn += self.interval
            if at_boundary or at_turn:
                self.choose_direction()
        return self.position

    def mini_plan(self):
        """Snapshot do trecho já decidido, sem avançar o relógio ou sortear rumos."""
        x, y = self.position
        dx, dy = self.direction
        dot = x * dx + y * dy
        distance = -dot + math.sqrt(max(0.0, dot * dot + self.radius ** 2 - x * x - y * y))
        return dict(reference_time=self.time, relative_position=list(self.position),
                    velocity=[dx * self.speed, dy * self.speed],
                    valid_until=min(self.next_turn, self.time + max(0.0, distance) / self.speed))
