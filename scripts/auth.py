import sqlite3
import hashlib
import os

DATABASE_NAME = "data/social_media_analysis.db" # Use the determined database file

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

def hash_password(password, salt=None):
    """Hashes a password with SHA256 and a salt."""
    if salt is None:
        salt = os.urandom(16)  # Generate a new salt

    # Ensure password is bytes
    if isinstance(password, str):
        password = password.encode('utf-8')

    salted_password = salt + password
    hashed_password = hashlib.sha256(salted_password).hexdigest()
    return salt.hex(), hashed_password

def verify_password(stored_salt_hex, stored_hash_hex, provided_password):
    """Verifies a provided password against the stored salt and hash."""
    try:
        salt = bytes.fromhex(stored_salt_hex)
        # Ensure provided_password is bytes
        if isinstance(provided_password, str):
            provided_password = provided_password.encode('utf-8')

        salted_provided_password = salt + provided_password
        hashed_provided_password = hashlib.sha256(salted_provided_password).hexdigest()
        return hashed_provided_password == stored_hash_hex
    except (ValueError, TypeError) as e:
        print(f"Error during password verification (likely salt/hash format issue): {e}")
        return False


def create_user(username, password, role='analyst'):
    """Creates a new user in the analyst_accounts table."""
    conn = get_db_connection()
    cursor = conn.cursor()

    salt_hex, hashed_password_hex = hash_password(password)

    try:
        cursor.execute("""
            INSERT INTO analyst_accounts (username, salt, hashed_password, role)
            VALUES (?, ?, ?, ?)
        """, (username, salt_hex, hashed_password_hex, role))
        conn.commit()
        print(f"User '{username}' created successfully with role '{role}'.")
        return True
    except sqlite3.IntegrityError:
        print(f"Error: Username '{username}' already exists.")
        return False
    except sqlite3.Error as e:
        print(f"Database error creating user: {e}")
        return False
    finally:
        conn.close()

def get_user(username):
    """Retrieves a user's details (including salt and hashed_password) from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, username, salt, hashed_password, role FROM analyst_accounts WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        return user_data # Returns a Row object or None
    except sqlite3.Error as e:
        print(f"Database error getting user: {e}")
        return None
    finally:
        conn.close()

if __name__ == '__main__':
    # Basic test for auth functions (not a replacement for manage_users.py)
    print("Testing auth.py functions...")
    # Ensure the database and table exist by running database_setup.py first
    # This is just for a quick check if run directly.
    if not os.path.exists(DATABASE_NAME):
        print(f"Database {DATABASE_NAME} not found. Please run database_setup.py first.")
    else:
        # Test user creation (will fail if user exists, that's fine for a test)
        # In a real scenario, use manage_users.py to add users.
        print("\nAttempting to create a test user 'auth_test_user' (ignore if already exists error)...")
        create_user("auth_test_user", "testpassword123")

        print("\nFetching user 'auth_test_user'...")
        user = get_user("auth_test_user")
        if user:
            print(f"User found: {user['username']}, Role: {user['role']}")
            print("Verifying password 'testpassword123':")
            is_valid = verify_password(user['salt'], user['hashed_password'], "testpassword123")
            print(f"Password valid: {is_valid}")

            print("Verifying incorrect password 'wrongpassword':")
            is_invalid = verify_password(user['salt'], user['hashed_password'], "wrongpassword")
            print(f"Password valid: {is_invalid}")
        else:
            print("User 'auth_test_user' not found. Create it manually or via manage_users.py for full test.")
    print("\nauth.py testing finished.")
