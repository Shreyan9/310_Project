import tkinter as tk
from tkinter import messagebox
from tkinter import ttk  
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
        data = response.json()
        jwt_token = data['token']
        role = data.get('role', 'customer')  # Get role from response
        entry_login_username.delete(0, tk.END)
        entry_login_password.delete(0, tk.END)
        
        if role == 'manager':
            show_manager_page(username)
        else:
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

def show_manager_page(username):
    root.withdraw()
    manager_window = tk.Toplevel(root)
    manager_window.title("Manager Dashboard")
    manager_window.geometry("900x700")
    
    tk.Label(manager_window, text=f"Manager Dashboard - {username}", font=("Arial", 16, "bold")).pack(pady=10)
    
    # Store orders data globally for quick access
    orders_data = {}
    
    # Create notebook for tabs
    notebook = ttk.Notebook(manager_window)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Tab 1: View Orders
    orders_tab = ttk.Frame(notebook)
    notebook.add(orders_tab, text="View Orders")
    
    tk.Label(orders_tab, text="All Orders", font=("Arial", 14, "bold")).pack(pady=5)
    
    # Create Treeview for orders
    columns = ("Order ID", "Customer", "Date", "Status", "Total")
    orders_tree = ttk.Treeview(orders_tab, columns=columns, show="headings", height=12)
    orders_tree.pack(padx=10, pady=5, fill="both", expand=True)
    
    orders_tree.heading("Order ID", text="Order ID")
    orders_tree.heading("Customer", text="Customer")
    orders_tree.heading("Date", text="Date")
    orders_tree.heading("Status", text="Status")
    orders_tree.heading("Total", text="Total")

    # Set column widths
    orders_tree.column("Order ID", width=80)
    orders_tree.column("Customer", width=150)
    orders_tree.column("Date", width=180)
    orders_tree.column("Status", width=100)
    orders_tree.column("Total", width=100)
    
    # Order details text widget - positioned better
    details_frame = tk.Frame(orders_tab)
    details_frame.pack(padx=10, pady=5, fill="both")
    
    tk.Label(details_frame, text="Order Items:").pack(anchor="w")
    order_details = tk.Text(details_frame, height=8, width=80)
    order_details.pack(pady=5, fill="both", expand=True)
    
    def load_orders():
        response = requests.get(
            "http://localhost:5000/view_all_orders",
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        
        # Clear existing items
        for item in orders_tree.get_children():
            orders_tree.delete(item)
        orders_data.clear()
        
        if response.status_code == 200:
            orders = response.json().get("orders", [])
            for order in orders:
                # Store order data for quick access
                orders_data[order["order_id"]] = order["items"]
                
                # Insert into tree
                orders_tree.insert("", "end", values=(
                    order["order_id"],
                    order["username"],
                    order["order_date"],
                    order["status"],
                    f"${order['total_amount']:.2f}"
                ))
    
    def show_order_details(event):
        selection = orders_tree.selection()
        if selection:
            item = orders_tree.item(selection[0])
            order_id = item['values'][0]
            
            # Use stored data instead of making another API call
            order_details.delete(1.0, tk.END)
            if order_id in orders_data:
                for item in orders_data[order_id]:
                    order_details.insert(tk.END, 
                        f"- {item['title']} ({item['type']}) - ${item['price']:.2f}\n")
    
    orders_tree.bind("<<TreeviewSelect>>", show_order_details)
    
    # Update status section - more compact layout
    status_frame = tk.Frame(orders_tab)
    status_frame.pack(padx=10, pady=5)
    
    tk.Label(status_frame, text="Update Status:").grid(row=0, column=0, padx=5)
    status_var = tk.StringVar(value="Paid")
    status_menu = ttk.Combobox(status_frame, textvariable=status_var, values=["Pending", "Paid"], width=10)
    status_menu.grid(row=0, column=1, padx=5)
    
    def update_order_status():
        selection = orders_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select an order")
            return
        
        order_id = orders_tree.item(selection[0])['values'][0]
        new_status = status_var.get()
        
        response = requests.post(
            "http://localhost:5000/update_order_status",
            json={"order_id": order_id, "status": new_status},
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        
        if response.status_code == 200:
            messagebox.showinfo("Success", f"Order {order_id} status updated to {new_status}")
            load_orders()
        else:
            messagebox.showerror("Error", "Failed to update order status")
    
    tk.Button(status_frame, text="Update Status", command=update_order_status).grid(row=0, column=2, padx=5)
    tk.Button(status_frame, text="Refresh Orders", command=load_orders).grid(row=0, column=3, padx=5)
    
    # Tab 2: Manage Books
    books_tab = ttk.Frame(notebook)
    notebook.add(books_tab, text="Manage Books")
    
    # Add book section
    add_frame = tk.LabelFrame(books_tab, text="Add New Book", padx=10, pady=10)
    add_frame.pack(padx=10, pady=10, fill="x")
    
    tk.Label(add_frame, text="Title:").grid(row=0, column=0, sticky="w")
    entry_title = tk.Entry(add_frame, width=30)
    entry_title.grid(row=0, column=1, padx=5)
    
    tk.Label(add_frame, text="Author:").grid(row=0, column=2, sticky="w")
    entry_author = tk.Entry(add_frame, width=30)
    entry_author.grid(row=0, column=3, padx=5)
    
    tk.Label(add_frame, text="Buy Price:").grid(row=1, column=0, sticky="w")
    entry_buy_price = tk.Entry(add_frame, width=15)
    entry_buy_price.grid(row=1, column=1, padx=5)
    
    tk.Label(add_frame, text="Rent Price:").grid(row=1, column=2, sticky="w")
    entry_rent_price = tk.Entry(add_frame, width=15)
    entry_rent_price.grid(row=1, column=3, padx=5)
    
    tk.Label(add_frame, text="Availability:").grid(row=2, column=0, sticky="w")
    entry_availability = tk.Entry(add_frame, width=15)
    entry_availability.insert(0, "1")
    entry_availability.grid(row=2, column=1, padx=5)
    
    def add_book():
        title = entry_title.get()
        author = entry_author.get()
        
        try:
            buy_price = float(entry_buy_price.get())
            rent_price = float(entry_rent_price.get())
            availability = int(entry_availability.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid price or availability value")
            return
        
        response = requests.post(
            "http://localhost:5000/add_book",
            json={
                "title": title,
                "author": author,
                "price_buy": buy_price,
                "price_rent": rent_price,
                "availability": availability
            },
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        
        if response.status_code == 201:
            messagebox.showinfo("Success", "Book added successfully")
            # Clear fields
            entry_title.delete(0, tk.END)
            entry_author.delete(0, tk.END)
            entry_buy_price.delete(0, tk.END)
            entry_rent_price.delete(0, tk.END)
            entry_availability.delete(0, tk.END)
            entry_availability.insert(0, "1")
        else:
            messagebox.showerror("Error", "Failed to add book")
    
    tk.Button(add_frame, text="Add Book", command=add_book).grid(row=2, column=2, columnspan=2, pady=10)
    
    # Update book section
    update_frame = tk.LabelFrame(books_tab, text="Update Book", padx=10, pady=10)
    update_frame.pack(padx=10, pady=10, fill="x")
    
    tk.Label(update_frame, text="Book ID:").grid(row=0, column=0, sticky="w")
    entry_book_id = tk.Entry(update_frame, width=10)
    entry_book_id.grid(row=0, column=1, padx=5)
    
    tk.Label(update_frame, text="New Title:").grid(row=1, column=0, sticky="w")
    entry_new_title = tk.Entry(update_frame, width=30)
    entry_new_title.grid(row=1, column=1, padx=5)
    
    tk.Label(update_frame, text="New Author:").grid(row=1, column=2, sticky="w")
    entry_new_author = tk.Entry(update_frame, width=30)
    entry_new_author.grid(row=1, column=3, padx=5)
    
    tk.Label(update_frame, text="New Buy Price:").grid(row=2, column=0, sticky="w")
    entry_new_buy = tk.Entry(update_frame, width=15)
    entry_new_buy.grid(row=2, column=1, padx=5)
    
    tk.Label(update_frame, text="New Rent Price:").grid(row=2, column=2, sticky="w")
    entry_new_rent = tk.Entry(update_frame, width=15)
    entry_new_rent.grid(row=2, column=3, padx=5)
    
    tk.Label(update_frame, text="New Availability:").grid(row=3, column=0, sticky="w")
    entry_new_avail = tk.Entry(update_frame, width=15)
    entry_new_avail.grid(row=3, column=1, padx=5)
    
    def update_book():
        book_id = entry_book_id.get()
        if not book_id:
            messagebox.showerror("Error", "Book ID is required")
            return
        
        update_data = {"book_id": int(book_id)}
        
        if entry_new_title.get():
            update_data["title"] = entry_new_title.get()
        if entry_new_author.get():
            update_data["author"] = entry_new_author.get()
        if entry_new_buy.get():
            update_data["price_buy"] = float(entry_new_buy.get())
        if entry_new_rent.get():
            update_data["price_rent"] = float(entry_new_rent.get())
        if entry_new_avail.get():
            update_data["availability"] = int(entry_new_avail.get())
        
        response = requests.post(
            "http://localhost:5000/update_book",
            json=update_data,
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        
        if response.status_code == 200:
            messagebox.showinfo("Success", "Book updated successfully")
            # Clear fields
            entry_book_id.delete(0, tk.END)
            entry_new_title.delete(0, tk.END)
            entry_new_author.delete(0, tk.END)
            entry_new_buy.delete(0, tk.END)
            entry_new_rent.delete(0, tk.END)
            entry_new_avail.delete(0, tk.END)
        else:
            messagebox.showerror("Error", "Failed to update book")
    
    tk.Button(update_frame, text="Update Book", command=update_book).grid(row=3, column=2, columnspan=2, pady=10)
    
    # Load orders on startup
    load_orders()
    
    # Logout button
    tk.Button(manager_window, text="Logout", command=lambda: logout(manager_window)).pack(pady=10)


def logout(customer_window):
    customer_window.destroy()
    root.deiconify()

def login_manager():
    global jwt_token
    username = entry_manager_username.get()
    password = entry_manager_password.get()

    response = requests.post("http://localhost:5000/manager_login", json={
        "username": username,
        "password": password
    })

    if response.status_code == 200:
        jwt_token = response.json()['token']
        entry_manager_username.delete(0, tk.END)
        entry_manager_password.delete(0, tk.END)
        show_manager_page(username)
    else:
        messagebox.showerror("Error", "Invalid manager credentials")


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

frame_manager = tk.LabelFrame(root, text="Manager Login")
frame_manager.grid(row=1, column=0, columnspan=2, padx=20, pady=10)

tk.Label(frame_manager, text="Username:").grid(row=0, column=0)
entry_manager_username = tk.Entry(frame_manager)
entry_manager_username.grid(row=0, column=1)

tk.Label(frame_manager, text="Password:").grid(row=1, column=0)
entry_manager_password = tk.Entry(frame_manager, show="*")
entry_manager_password.grid(row=1, column=1)

tk.Button(frame_manager, text="Manager Login", command=login_manager).grid(row=2, column=0, columnspan=2, pady=5)

root.mainloop()
