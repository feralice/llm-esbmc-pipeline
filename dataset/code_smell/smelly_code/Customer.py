"""
Copyright (c) 2025 Ahmed R. Sadik, Honda Research Institute Europe GmbH 

This source code is licensed under the MIT License found in the
LICENSE file in the root directory of this source tree. This dataset contains smelly code for research and refactoring purposes.
"""

from Drink import Drink

class Customer:
    def __init__(self, pizza_shop):
        self.pizza_shop = pizza_shop  # Dependency Injection (Control Coupling)
        self.frequent_customer_discount = False  # Primitive Obsession

        # Data Clumps
        self.first_name = None
        self.last_name = None
        self.address = None
        self.phone_number = None
        self.email = None

        # Temporary Fields
        self.temp_discount_code = None
        self.temp_order_note = None

        # Lazy Class
        self.drink_order = Drink()

    def order_pizza(self, pizza_type: str):
        print(f"Customer is placing an order for {pizza_type} pizza.")
        self.pizza_shop.receive_order(pizza_type)  # Feature Envy (refers to another class to do its work)

    def complain(self, complaint: str):
        print(f"Customer is complaining: {complaint}")
        self.pizza_shop.casher.calm_customer_down()  # Inappropriate Intimacy (accessing another object's internal details)
        self.pizza_shop.casher.chef.clean_kitchen()  # Inappropriate Intimacy (accessing another object's internal details)

    def ask_for_receipt(self):
        print("Customer is asking for a receipt.")  # Speculative Generality (unused method)

    def another_unused_method(self):
        pass  # Dead Code (method is never called)

    def yet_another_unused_method(self):
        pass  # More Dead Code

    def long_complaint_method(self):
        # Long Method (too many complaints handled in one method)
        print("Customer is complaining about many things")
        self.complain("Pizza is cold")
        self.complain("Pizza is late")
        self.complain("Wrong pizza delivered")
        self.complain("Pizza is burnt")
        self.complain("Too little cheese")
        self.complain("Pizza is undercooked")
        self.ask_for_receipt()

    def order_with_unnecessary_details(self):
        # Long Parameter List (too many parameters in the method)
        print("Customer is placing a detailed order")
        self.order_pizza("Veggie", "Large", "Whole Wheat", "Veggies", False, True, False, False, "Olives", "Mushrooms", "Pesto", "Thick", False, False, True, True, True, False, False, False)

    def duplicate_complaint(self):
        # Duplicate Code (repeating complaint functionality)
        print("Customer is complaining about duplicate issues")
        self.complain("Pizza is cold")
        self.complain("Pizza is cold")
        self.complain("Pizza is late")
        self.complain("Pizza is late")

    def chain_of_methods(self):
        # Message Chain (calling methods on objects returned by another method)
        print("Customer is initiating a message chain")
        self.pizza_shop.casher.chef.clean_kitchen()

    def middleman_method(self):
        # Middle Man (methods that delegate to other methods)
        print("Customer is calling a middleman method")
        self.middle_method()

    def middle_method(self):
        print("Middleman method delegating to another method")
        self.real_method()

    def real_method(self):
        print("Real method doing the actual work")

    def access_internal_details(self):
        # Inappropriate Intimacy (accessing internal details of another class)
        print(f"Accessing internal details of Shop: {self.pizza_shop.casher.chef.busy}")

    def update_contact_info(self, first_name, last_name, address, phone_number, email):
        # Shotgun Surgery (changing multiple methods to update contact info)
        self.first_name = first_name
        self.last_name = last_name
        self.address = address
        self.phone_number = phone_number
        self.email = email

    def update_name(self, first_name, last_name):
        # Shotgun Surgery (separate method to update name)
        self.first_name = first_name
        self.last_name = last_name

    def update_address(self, address):
        # Shotgun Surgery (separate method to update address)
        self.address = address

    def update_phone_number(self, phone_number):
        # Shotgun Surgery (separate method to update phone number)
        self.phone_number = phone_number

    def update_email(self, email):
        # Shotgun Surgery (separate method to update email)
        self.email = email

    def notify_for_promotion(self):
        # Divergent Change (method to notify for promotion)
        print("Notifying customer for promotion")

    def notify_for_discount(self):
        # Divergent Change (method to notify for discount)
        print("Notifying customer for discount")

    def notify_for_new_arrivals(self):
        # Divergent Change (method to notify for new arrivals)
        print("Notifying customer for new arrivals")

    def apply_discount(self):
        # Parallel Inheritance Hierarchies (method to apply discount)
        print("Applying discount for customer")

    def apply_loyalty_points(self):
        # Parallel Inheritance Hierarchies (method to apply loyalty points)
        print("Applying loyalty points for customer")

    def handle_complaint(self, complaint):
        # Switch Statements (using if-else to simulate switch)
        if complaint == "cold pizza":
            self.complain("Pizza is cold")
        elif complaint == "late delivery":
            self.complain("Pizza is late")
        elif complaint == "wrong order":
            self.complain("Wrong pizza delivered")
        else:
            self.complain("General complaint")

    def refused_bequest(self):
        # Refused Bequest (method that should be inherited but is empty)
        pass  # This method is intended to be overridden but isn't used in the base class

    def order_drink(self, drink_type: str):
        # Unnecessary Comments (explaining what each line does)
        # Create a new drink order
        print(f"Customer is ordering a {drink_type} drink.")
        self.drink_order.create_order(drink_type)
        # Add the drink order to the current order
        print("Adding the drink order to the current order.")
        self.drink_order.add_to_order()
        # Confirm the drink order
        print("Confirming the drink order.")
        self.drink_order.confirm_order()
