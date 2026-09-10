import pyodbc
from datetime import datetime

# -----------------------------
# SQL Server Connection
# -----------------------------
def get_connection():
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=172.19.31.12;"
        "DATABASE=Concept_Tracking_QA;"
        "UID=medintelx_user;"
        "PWD=M3d12131;"
    )
    return conn


# -----------------------------
# Insert Role
# -----------------------------
def insert_role(conn):
    role_name = input("Role Name: ")

    query = """
    INSERT INTO user_role (role_name)
    VALUES (?)
    """

    cursor = conn.cursor()
    cursor.execute(query, (role_name,))
    conn.commit()

    print("✅ Role inserted successfully")


# -----------------------------
# Insert User
# -----------------------------
def insert_user(conn):
    username = input("Username: ")
    hashed_password = input("Hashed Password: ")
    name = input("Full Name: ")
    is_active = int(input("Active (1/0): "))

    query = """
    INSERT INTO users
    (username, hashed_password, name, is_active)
    VALUES (?, ?, ?, ?)
    """

    cursor = conn.cursor()
    cursor.execute(
        query,
        (
            username,
            hashed_password,
            name,
            is_active
        )
    )
    conn.commit()

    print("✅ User inserted successfully")


# -----------------------------
# Assign Role to User
# -----------------------------
def insert_user_access(conn):
    user_id = int(input("User ID: "))
    role_id = int(input("Role ID: "))

    query = """
    INSERT INTO user_access
    (user_id, role_id)
    VALUES (?, ?)
    """

    cursor = conn.cursor()
    cursor.execute(query, (user_id, role_id))
    conn.commit()

    print("✅ User role assigned successfully")


def show_roles(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT role_id, role_name FROM user_role")
    rows = cursor.fetchall()

    print("\n--- Existing Roles ---")
    if not rows:
        print("No roles found.")
        return

    for r in rows:
        print(f"{r[0]} - {r[1]}")


def show_users(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, name, is_active FROM users")
    rows = cursor.fetchall()

    print("\n--- Existing Users ---")
    if not rows:
        print("No users found.")
        return

    for u in rows:
        status = "Active" if u[3] == 1 else "Inactive"
        print(f"{u[0]} - {u[1]} ({u[2]}) [{status}]")

def insert_user_access(conn):
    show_users(conn)
    user_id = int(input("User ID: "))

    show_roles(conn)
    role_id = int(input("Role ID: "))

    query = """
    INSERT INTO user_access
    (user_id, role_id)
    VALUES (?, ?)
    """

    cursor = conn.cursor()
    cursor.execute(query, (user_id, role_id))
    conn.commit()

    print("✅ User role assigned successfully")

# -----------------------------
# Menu
# -----------------------------
def main():
    try:
        conn = get_connection()

        while True:
            print("\n=========================")
            print(" USER MANAGEMENT MENU")
            print("========================")

            show_users(conn)
            show_roles(conn)

            print("\n========================")
            print(" SELECT FROM BELOW OPTIONS ")
            print("========================")

            print("\n1. Add Role")
            print("2. Add User")
            print("3. Assign Role to User")
            print("4. Exit")

            choice = input("Enter Choice: ")

            if choice == "1":
                insert_role(conn)

            elif choice == "2":
                insert_user(conn)

            elif choice == "3":
                insert_user_access(conn)

            elif choice == "4":
                print("Exiting...")
                break

            else:
                print("❌ Invalid choice")

    except Exception as e:
        print("❌ Error:", e)

    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    main()