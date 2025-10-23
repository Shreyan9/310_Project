import tkinter as tk
from tkinter import messagebox
import mysql.connector

# Connect to local MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="sunitha80",
    database="project"  # make sure this matches your database name
)

import tkinter as tk
from tkinter import messagebox
import requests

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
    username = entry_login_username.get()
    password = entry_login_password.get()
    response = requests.post("http://localhost:5000/login", json={
        "username": username,
        "password": password
    })
    if response.status_code == 200:
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
    root.withdraw()  # hide login window
    customer_window = tk.Toplevel(root)
    customer_window.title("Customer Dashboard")
    tk.Label(customer_window, text=f"Welcome, {username}!", font=("Arial", 16)).pack(padx=20, pady=20)
    tk.Button(customer_window, text="Browse Books", command=lambda: messagebox.showinfo("Feature", "Coming soon!")).pack(pady=10)
    tk.Button(customer_window, text="View Orders", command=lambda: messagebox.showinfo("Feature", "Coming soon!")).pack(pady=10)
    tk.Button(customer_window, text="Logout", command=lambda: logout(customer_window)).pack(pady=10)

def logout(customer_window):
    customer_window.destroy()
    root.deiconify()  # show login window again

root = tk.Tk()
root.title("Bookstore App Login/Registration")

# Registration Frame
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

# Login Frame
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