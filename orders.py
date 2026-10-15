"""Order processing logic."""
import sqlite3

import database
import auth

TAX = 0.15
SEPARATOR = "=" * 30


def _item_total(item):
    """Add a valid item's cost and update its available stock."""
    book = database.get_book(item["book_id"])
    if book is None:
        print("Book not found")
        return 0

    quantity = item["qty"]
    if quantity <= 0:
        print("Invalid quantity")
        return 0
    if quantity > book[3]:
        if book[3] > 0:
            print("Only " + str(book[3]) + " units available for " + book[1])
        else:
            print("Book out of stock: " + book[1])
        return 0

    database.update_stock(book[0], book[3] - quantity)
    return book[2] * quantity


def _apply_coupon(total, coupon, token):
    """Apply the selected discount, enforcing STAFF authorization."""
    if coupon == "WELCOME10":
        return total * 0.9
    if coupon == "BLACKFRIDAY":
        return total * 0.5
    if coupon == "STAFF":
        if auth.is_admin(token):
            return total * 0.7
        print("STAFF coupon requires admin access.")
    return total


def _next_order_id():
    """Read the next order ID without depending on a shared default list."""
    conn = database.get_connection()
    try:
        row = conn.execute("SELECT MAX(id) FROM orders").fetchone()
        return (row[0] or 0) + 1
    finally:
        conn.close()


def process_order(token, items, coupon=None, shipping="standard", log=None):
    """Process an order and record its total."""
    if log is None:
        log = []
    username = auth.sessions.get(token)
    if username is None:
        print("Invalid session")
        return None
    if not items:
        print("Empty order")
        return None

    total = sum(_item_total(item) for item in items)
    total = _apply_coupon(total, coupon, token)
    if shipping == "express":
        total += 10
    elif shipping == "standard":
        total += 3
    total += total * TAX

    order_id = _next_order_id()
    database.save_order(order_id, username, total, "PENDING")
    log.append(order_id)
    return round(total, 2)


def _print_document(username, items, title, quote=False):
    """Print item lines and totals shared by invoices and quotes."""
    print(SEPARATOR)
    print(title)
    print("Customer: " + username)
    print(SEPARATOR)
    subtotal = 0
    for item in items:
        book = database.get_book(item["book_id"])
        line_total = book[2] * item["qty"]
        subtotal += line_total
        print(book[1] + " x" + str(item["qty"]) + " = " + str(line_total))
    tax = subtotal * TAX
    print("Subtotal: " + str(round(subtotal, 2)))
    print("Tax: " + str(round(tax, 2)))
    print("Total: " + str(round(subtotal + tax, 2)))
    if quote:
        print("This quote is valid for 7 days.")
    print(SEPARATOR)


def print_invoice(username, items):
    """Display an invoice for a customer's items."""
    _print_document(username, items, "BOOKSTORE INVOICE")


def print_quote(username, items):
    """Display a quote, including its validity period."""
    _print_document(username, items, "BOOKSTORE QUOTE", quote=True)


def cancel_order(order_id):
    try:
        conn = database.get_connection()
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            ("CANCELLED", order_id),
        )
        conn.commit()
    except sqlite3.Error as error:
        print(f"Could not cancel order: {error}")
