"""Independent tests of Calculator using equivalence classes and boundaries."""

import pytest

from calculator import Calculator


@pytest.mark.parametrize(
    "a, b, expected",
    [(2, 3, 5), (-1, 1, 0), (0, 0, 0), (100, -40, 60),
     (10**30, 10**30, 2 * 10**30)],
    ids=["positive", "opposite-signs", "zeros", "negative-second", "large-integers"],
)
def test_add_integers(a, b, expected):
    calc = Calculator()  # Arrange
    result = calc.add(a, b)  # Act
    assert result == expected  # Assert


@pytest.mark.parametrize("a, b, expected", [(0.1, 0.2, 0.3), (1.5, -2.25, -0.75)])
def test_add_floats(a, b, expected):
    calc = Calculator()
    result = calc.add(a, b)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    "a, b, expected",
    [(8, 3, 5), (0, 0, 0), (0, 5, -5), (-5, -2, -3),
     (10**30, 1, 10**30 - 1)],
    ids=["positive", "zeros", "zero-first", "negatives", "large-integers"],
)
def test_subtract_integers(a, b, expected):
    calc = Calculator()
    result = calc.subtract(a, b)
    assert result == expected


@pytest.mark.parametrize("a, b, expected", [(0.3, 0.1, 0.2), (2, 0.5, 1.5)])
def test_subtract_floats(a, b, expected):
    calc = Calculator()
    result = calc.subtract(a, b)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    "a, b, expected",
    [(4, 3, 12), (0, 7, 0), (-4, 3, -12), (-4, -3, 12),
     (10**30, 10**30, 10**60)],
    ids=["positive", "zero", "opposite-signs", "negatives", "large-integers"],
)
def test_multiply_integers(a, b, expected):
    calc = Calculator()
    result = calc.multiply(a, b)
    assert result == expected


@pytest.mark.parametrize("a, b, expected", [(0.1, 0.2, 0.02), (3, -0.5, -1.5)])
def test_multiply_floats(a, b, expected):
    calc = Calculator()
    result = calc.multiply(a, b)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    "a, b, expected",
    [(10, 2, 5.0), (0, 5, 0.0), (-9, 3, -3.0), (-9, -3, 3.0),
     (1, 3, 0.3333333333333333), (10**12, 10**6, 10**6)],
    ids=["positive", "zero-numerator", "opposite-signs", "negatives",
         "fraction", "large-numbers"],
)
def test_divide(a, b, expected):
    calc = Calculator()
    result = calc.divide(a, b)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    "a, b", [(10, 0), (0, 0), (-7, 0.0), (1.5, -0.0)],
    ids=["positive-numerator", "zero-numerator", "float-zero", "negative-float-zero"],
)
def test_divide_by_zero(a, b):
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.divide(a, b)
