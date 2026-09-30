"""
Copyright (c) 2025 Ahmed R. Sadik, Honda Research Institute Europe GmbH 

This source code is licensed under the MIT License found in the
LICENSE file in the root directory of this source tree. This dataset contains smelly code for research and refactoring purposes.
"""

class Drink:
    # Data Class
    def __init__(self):
        self.drink_type = None
        
    # Primitive Obsession
    def create_order(self, drink_type):
        self.drink_type = drink_type
        print(f"Creating order for {drink_type} drink.")
    # Primitive Obsession
    def add_to_order(self):
        print(f"Adding {self.drink_type} to the order.")

    def confirm_order(self):
        print(f"Order for {self.drink_type} confirmed.")
