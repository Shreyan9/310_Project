import tkinter as tk
from tkinter import messagebox
import requests
import mysql.connector

# Connect to local MySQL (only needed for initial DB connection check, REST handles logic)
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="sunitha80",
    database="project"
)

cart = []   # local cart memory
jwt_token = None


def register_user():
    username = entry_reg_username.get()
    password = entry_reg_password.get()
    email = entry_reg_email.get()

    if not username or not password or not email:
        messagebox.showerror("Error", "All fields required!")
        return

    response = requests.post("http://localhost:5000/register", json={
        "username": username,
        "password": password,
        "email": email
    })

    if response.status_code == 201:
        show_success_screen("Registration successful!")
        entry_reg_username.delete(0, tk.END)
        entry_reg_password.delete(0, tk.END)
        entry_reg_email.delete(0, tk.END)
    else:
        messagebox.showerror("Error", response.json().get("message", "Registration failed"))


def login_user():
    global jwt_token
    username = entry_login_username.get()
    password = entry_login_password.get()

    response = requests.post("http://localhost:5000/login", json={
        "username": username,
        "password": password
    })

    if response.status_code == 200:
        jwt_token = response.json()['token']
        entry_login_username.delete(0, tk.END)
        entry_login_password.delete(0, tk.END)
        show_customer_page(username)
    else:
        messagebox.showerror("Error", response.json().get("message", "Login failed"))


def show_success_screen(msg):
    success = tk.Toplevel(root)
    success.title("Success")
    tk.Label(success, text=msg, font=("Arial", 14)).pack(padx=20, pady=20)
    tk.Button(success, text="Close", command=success.destroy).pack(pady=10)


def show_customer_page(username):
    root.withdraw()
    customer_window = tk.Toplevel(root)
    customer_window.title("Customer Dashboard")

    tk.Label(customer_window, text=f"Welcome, {username}!", font=("Arial", 16)).pack(padx=20, pady=10)

    # ---------------- SEARCH UI ---------------- #

    search_frame = tk.Frame(customer_window)
    search_frame.pack(padx=10, pady=10)

    tk.Label(search_frame, text="Search Books:").grid(row=0, column=0)
    entry_search = tk.Entry(search_frame)
    entry_search.grid(row=0, column=1)

    results_list = tk.Listbox(customer_window, width=90, height=15)
    results_list.pack(padx=10, pady=10)

    # Scrollbar
    scrollbar = tk.Scrollbar(customer_window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    results_list.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=results_list.yview)

    def load_books(keyword=""):
        response = requests.get("http://localhost:5000/search_books", params={"keyword": keyword})
        results_list.delete(0, tk.END)

        if response.status_code == 200:
            books = response.json().get("books", [])
            for book in books:
                display = (
                    f"{book['title']} | {book['author']} | "
                    f"Buy: ${book['price_buy']} | Rent: ${book['price_rent']} | "
                    f"Availability: {'Yes' if book['availability'] else 'No'}"
                )
                results_list.insert(tk.END, display)

    def on_search(event=None):
        keyword = entry_search.get()
        load_books(keyword)

    # Load all books initially
    load_books()

    tk.Button(search_frame, text="Search", command=on_search).grid(row=0, column=2, padx=5)

    # ---------------- CART FUNCTIONS ---------------- #

    def add_to_cart():
        selection = results_list.get(tk.ACTIVE)
        if not selection:
            messagebox.showerror("Error", "Select a book first")
            return

        title = selection.split(" | ")[0]

        choice = tk.messagebox.askquestion("Choose Option", "Do you want to BUY this book?\nClick No to RENT.")
        buy_or_rent = "buy" if choice == "yes" else "rent"

        resp = requests.get("http://localhost:5000/get_book", params={"title": title})
        if resp.status_code != 200:
            messagebox.showerror("Error", "Book not found")
            return

        data = resp.json()
        price = data["price_buy"] if buy_or_rent == "buy" else data["price_rent"]

        cart.append({
            "title": title,
            "book_id": data["book_id"],
            "type": buy_or_rent,
            "price": price
        })

        messagebox.showinfo("Cart", f"{title} added to cart as {buy_or_rent.upper()}.")

    def open_cart_window():
        cart_window = tk.Toplevel(customer_window)
        cart_window.title("My Cart")

        tk.Label(cart_window, text="Items in Cart", font=("Arial", 14)).pack(pady=5)

        cart_list = tk.Listbox(cart_window, width=60)
        cart_list.pack(padx=10, pady=10)

        for item in cart:
            cart_list.insert(tk.END, f"{item['title']} | {item['type']} | ${item['price']}")

        def remove_item():
            idx = cart_list.curselection()
            if not idx:
                return

            cart.pop(idx[0])
            cart_list.delete(idx[0])

        def place_order():
            if not cart:
                messagebox.showerror("Error", "Cart is empty")
                return

            items = [{"book_id": i["book_id"], "type": i["type"]} for i in cart]

            res = requests.post(
                "http://localhost:5000/place_order",
                json={"items": items},
                headers={"Authorization": f"Bearer {jwt_token}"}
            )

            if res.status_code == 200:
                messagebox.showinfo("Success", "Order placed successfully!")
                cart.clear()
                cart_window.destroy()
            else:
                messagebox.showerror("Error", "Failed to place order")

        tk.Button(cart_window, text="Remove Selected", command=remove_item).pack(pady=5)
        tk.Button(cart_window, text="Place Order", command=place_order).pack(pady=5)

    # Buttons
    tk.Button(customer_window, text="Add to Cart", command=add_to_cart).pack(pady=5)
    tk.Button(customer_window, text="View Cart / Checkout", command=open_cart_window).pack(pady=5)
    tk.Button(customer_window, text="Logout", command=lambda: logout(customer_window)).pack(pady=10)


def logout(customer_window):
    customer_window.destroy()
    root.deiconify()


# ---------------- MAIN WINDOW ---------------- #
root = tk.Tk()
root.title("Bookstore App Login/Registration")

frame_reg = tk.LabelFrame(root, text="Register")
frame_reg.grid(row=0, column=0, padx=20, pady=10)

tk.Label(frame_reg, text="Username:").grid(row=0, column=0)
entry_reg_username = tk.Entry(frame_reg)
entry_reg_username.grid(row=0, column=1)

tk.Label(frame_reg, text="Password:").grid(row=1, column=0)
entry_reg_password = tk.Entry(frame_reg, show="*")
entry_reg_password.grid(row=1, column=1)

tk.Label(frame_reg, text="Email:").grid(row=2, column=0)
entry_reg_email = tk.Entry(frame_reg)
entry_reg_email.grid(row=2, column=1)

tk.Button(frame_reg, text="Register", command=register_user).grid(row=3, column=0, columnspan=2, pady=5)

frame_login = tk.LabelFrame(root, text="Login")
frame_login.grid(row=0, column=1, padx=20, pady=10)

tk.Label(frame_login, text="Username:").grid(row=0, column=0)
entry_login_username = tk.Entry(frame_login)
entry_login_username.grid(row=0, column=1)

tk.Label(frame_login, text="Password:").grid(row=1, column=0)
entry_login_password = tk.Entry(frame_login, show="*")
entry_login_password.grid(row=1, column=1)

tk.Button(frame_login, text="Login", command=login_user).grid(row=2, column=0, columnspan=2, pady=5)

root.mainloop()
