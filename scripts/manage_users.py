import argparse
import getpass # For securely getting password from prompt
from auth import create_user, get_user # Assuming auth.py is in the same directory or PYTHONPATH

def main():
    parser = argparse.ArgumentParser(description="Manage analyst user accounts.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add user command
    parser_adduser = subparsers.add_parser("adduser", help="Add a new user")
    parser_adduser.add_argument("--username", required=True, help="Username for the new user")
    parser_adduser.add_argument("--password", help="Password for the new user (will be prompted if not provided)")
    parser_adduser.add_argument("--role", default="analyst", help="Role for the new user (e.g., analyst, admin)")

    # (Future command: listusers, deluser, passwd)
    # parser_listusers = subparsers.add_parser("listusers", help="List all users")
    # parser_deluser = subparsers.add_parser("deluser", help="Delete a user")
    # parser_deluser.add_argument("--username", required=True, help="Username of the user to delete")

    args = parser.parse_args()

    if args.command == "adduser":
        password = args.password
        if not password:
            password = getpass.getpass(f"Enter password for user '{args.username}': ")
            password_confirm = getpass.getpass("Confirm password: ")
            if password != password_confirm:
                print("Passwords do not match. User not created.")
                return

        if create_user(args.username, password, args.role):
            print(f"User '{args.username}' added successfully.")
        else:
            print(f"Failed to add user '{args.username}'.")

    # elif args.command == "listusers":
    #     print("User listing not implemented yet.")
    # elif args.command == "deluser":
    #     print("User deletion not implemented yet.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
