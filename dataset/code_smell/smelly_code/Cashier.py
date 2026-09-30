"""
Copyright (c) 2025 Ahmed R. Sadik, Honda Research Institute Europe GmbH 

This source code is licensed under the MIT License found in the
LICENSE file in the root directory of this source tree. This dataset contains smelly code for research and refactoring purposes.
"""


from Pizza import Pizza

class Cashier:
    def __init__(self, chef):
        self.chef = chef  # Control Coupling
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

    def take_order(self, pizza_type: str):
        print(f"Cashier is taking order for {pizza_type} pizza.")
        self.chef.bake_pizza(pizza_type)  # Feature Envy

    def hurry_up_chef(self):
        print("Cashier is hurrying up the chef.")
        self.chef.hurry_up()

    def calm_customer_down(self):
        print("Cashier is calming the customer down.")
        self.chef.clean_kitchen()  # Inappropriate Intimacy

    def deliver_pizza_to_customer(self):
        print("Cashier is delivering pizza to the customer.")

    def ask_for_receipt(self):
        print("Customer is asking for a receipt.")  # Speculative Generality (unused method)

    def another_unused_method(self):
        pass  # Dead Code (method is never called)

    def yet_another_unused_method(self):
        pass  # More Dead Code

    def long_method(self):
        # Long Method (too many tasks in a single method)
        print("Cashier is handling many tasks in a single method")
        self.take_order("Cheese")
        self.hurry_up_chef()
        self.calm_customer_down()
        self.deliver_pizza_to_customer()
        self.ask_for_receipt()

    def order_with_unnecessary_details(self, pizza_type, size, crust_type, toppings, extra_cheese, discount_code):
        # Long Parameter List (too many parameters in the method)
        print(f"Placing a detailed order for {pizza_type} pizza with {size}, {crust_type}, {toppings}, extra cheese: {extra_cheese}, discount code: {discount_code}")
        self.take_order(pizza_type)
        self.apply_discount(discount_code)
        self.deliver_pizza_to_customer()

    def duplicate_method(self):
        # Duplicate Code (repeating functionality)
        print("Customer is making a duplicate order")
        self.take_order("Cheese")
        self.take_order("Cheese")

    def chain_of_methods(self):
        # Message Chain (calling methods on objects returned by another method)
        print("Cashier is initiating a message chain")
        self.chef.clean_kitchen()

    def middleman_method(self):
        # Middle Man (methods that delegate to other methods)
        print("Cashier is calling a middleman method")
        self.middle_method()

    def middle_method(self):
        print("Middleman method delegating to another method")
        self.real_method()

    def real_method(self):
        print("Real method doing the actual work")

    def access_internal_details(self):
        # Inappropriate Intimacy (accessing internal details of another class)
        print(f"Accessing internal details: {self.chef.busy}")

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

    def apply_discount(self, discount_code):
        # Parallel Inheritance Hierarchies (method to apply discount)
        print(f"Applying discount for customer with code {discount_code}")

    def apply_loyalty_points(self):
        # Parallel Inheritance Hierarchies (method to apply loyalty points)
        print("Applying loyalty points for customer")

    def handle_complaint(self, complaint):
        # Switch Statements (using if-else to simulate switch)
        if complaint == "cold pizza":
            self.calm_customer_down()
        elif complaint == "late delivery":
            self.calm_customer_down()
        elif complaint == "wrong order":
            self.calm_customer_down()
        else:
            self.calm_customer_down()

    def refused_bequest(self):
        # Refused Bequest (method that should be inherited but is empty)
        pass  # This method is intended to be overridden but isn't used in the base class

