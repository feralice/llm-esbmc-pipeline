def update_position(x: int, y: int, z: int, vx: int, vy: int, vz: int, dt: int) -> int:
    return x + y + z + vx * dt + vy * dt + vz * dt