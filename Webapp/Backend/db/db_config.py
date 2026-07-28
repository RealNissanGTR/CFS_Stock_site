from db_init import init_db, add_user_full, get_user


def main():
    init_db()
    print("Initialized DB stock.db in backend folder")
    
    test_user = "admin"
    test_pass = "admin"
    test_email = "admin@example.com"
    is_admin = True

    if get_user(test_user):
        print(f"User '{test_user}' already exists")
    else:
        ok = add_user_full(test_user, test_pass, test_email, is_admin)
        if ok:
            print(f"Created admin user '{test_user}' with email {test_email}")
        else:
            print(f"Failed to create test user '{test_user}'")


if __name__ == "__main__":
    main()