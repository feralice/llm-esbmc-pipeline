"""
Copyright (c) 2025 Ahmed R. Sadik, Honda Research Institute Europe GmbH 

This source code is licensed under the MIT License found in the
LICENSE file in the root directory of this source tree. This dataset contains smelly code for research and refactoring purposes.
"""


from Pizza import Pizza

class Chef:
    def __init__(self):
        self.pizza = None
        self.busy = False
        self.completed_orders = 0
        self.breaks_taken = 0
        self.kitchen_clean = True

        # Primitive Obsession
        self.frequent_customer_discount = False

        # Data Clumps
        self.first_name = None
        self.last_name = None
        self.address = None
        self.phone_number = None
        self.email = None

        # Temporary Fields
        self.temp_discount_code = None
        self.temp_order_note = None

    def bake_pizza(self, pizza_type: str):
        print(f"Chef is baking {pizza_type} pizza.")
        self.pizza = Pizza("Unknown", "Unknown", pizza_type)  # Creating a Pizza instance
        self.cut_pizza_and_put_in_box()

    def cut_pizza_and_put_in_box(self):
        print(f"Chef is cutting the {self.pizza.topping} pizza and putting it in a box.")
        self.deliver_pizza()

    def deliver_pizza(self):
        print("Chef is delivering the pizza to the cashier.")

    def hurry_up(self):
        print("Chef is hurrying up.")

    def clean_kitchen(self):
        print("Chef is cleaning the kitchen.")
        self.kitchen_clean = True

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
            self.clean_kitchen()
        elif complaint == "late delivery":
            self.clean_kitchen()
        elif complaint == "wrong order":
            self.clean_kitchen()
        else:
            self.clean_kitchen()

    def ask_for_receipt(self):
        print("Customer is asking for a receipt.")  # Speculative Generality (unused method)

    def another_unused_method(self):
        pass  # Dead Code (method is never called)

    def yet_another_unused_method(self):
        pass  # More Dead Code

    def long_method(self):
        # Long Method (too many tasks in a single method)
        print("Chef is handling many tasks in a single method")
        self.bake_pizza("Cheese")
        self.cut_pizza_and_put_in_box()
        self.deliver_pizza()
        self.hurry_up()
        self.clean_kitchen()
        self.update_contact_info("John", "Doe", "123 Street", "555-5555", "john.doe@example.com")
        self.notify_for_promotion()
        self.notify_for_discount()
        self.notify_for_new_arrivals()
        self.apply_discount()
        self.apply_loyalty_points()
        self.handle_complaint("cold pizza")

    def order_with_unnecessary_details(self, pizza_type, size, crust_type, toppings, extra_cheese, discount_code):
        # Long Parameter List (too many parameters in the method)
        print(f"Placing a detailed order for {pizza_type} pizza with {size}, {crust_type}, {toppings}, extra cheese: {extra_cheese}, discount code: {discount_code}")
        self.bake_pizza(pizza_type)
        self.apply_discount(discount_code)
        self.deliver_pizza()

    def duplicate_method(self):
        # Duplicate Code (repeating functionality)
        print("Customer is making a duplicate order")
        self.bake_pizza("Cheese")
        self.bake_pizza("Cheese")

    def chain_of_methods(self):
        # Message Chain (calling methods on objects returned by another method)
        print("Chef is initiating a message chain")
        self.clean_kitchen()

    def middleman_method(self):
        # Middle Man (methods that delegate to other methods)
        print("Chef is calling a middleman method")
        self.middle_method()

    def middle_method(self):
        print("Middleman method delegating to another method")
        self.real_method()

    def real_method(self):
        print("Real method doing the actual work")

    def access_internal_details(self):
        # Inappropriate Intimacy (accessing internal details of another class)
        print(f"Accessing internal details: {self.pizza}")

    def refused_bequest(self):
        # Refused Bequest (method that should be inherited but is empty)
        pass  # This method is intended to be overridden but isn't used in the base class
