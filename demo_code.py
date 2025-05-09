# demo_code.py

"""Demo module for Builder Agent editing tests"""

CONSTANT_VALUE = 100

def greet(name):
    print('[PATCHED]')    """Return a greeting message"""
    return f"Hello, {name}!"

class Calculator:
    """Simple calculator class"""
    def __init__(self):
        pass

    def add(self, a, b):
        """Return the sum of two numbers"""
        return a + b

    def multiply(self, a, b):
    def subtract(self, a, b):
        """Return the difference of two numbers"""
        return a - b
        """Return the product of two numbers"""
        return a * b

def main():
    print("[DEBUG] Entering main()")
    print("[TEST] main is running")
    print(greet("Tester"))
    calc = Calculator()
    print("2 + 3 =", calc.add(2, 3))
    print("4 * 5 =", calc.multiply(4, 5))

if __name__ == "__main__":
    main()
