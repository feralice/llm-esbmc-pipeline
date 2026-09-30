"""
Copyright (c) 2025 Ahmed R. Sadik, Honda Research Institute Europe GmbH 

This source code is licensed under the MIT License found in the
LICENSE file in the root directory of this source tree. This dataset contains smelly code for research and refactoring purposes.
"""


import time
from Shop import Shop
from Customer import Customer

def measure_execution_time(runs=10):
    total_time = 0
    for _ in range(runs):
        start_time = time.time()

        shop = Shop()
        customer = Customer(shop)
        customer.order_pizza("Cheese")
        customer.complain("The pizza is too cold.")

        end_time = time.time()
        execution_time = end_time - start_time
        total_time += execution_time

    average_time = total_time / runs
    return average_time

if __name__ == "__main__":
    avg_time = measure_execution_time()
    print(f"Average execution time over multiple runs: {avg_time} seconds")
