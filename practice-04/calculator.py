"""Four arithmetic operations for integer and floating-point numbers."""


class Calculator:
    """A stateless calculator; each operation depends only on its arguments."""

    def add(self, a: int | float, b: int | float) -> int | float:
        return a + b

    def subtract(self, a: int | float, b: int | float) -> int | float:
        return a - b

    def multiply(self, a: int | float, b: int | float) -> int | float:
        return a * b

    def divide(self, a: int | float, b: int | float) -> float:
        if b == 0:
            raise ValueError("Деление на ноль")
        return a / b
