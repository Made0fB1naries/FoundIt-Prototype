# main.py

from models import LostAndFoundSystem

def run_cli():
    system = LostAndFoundSystem()

    while True:
        # --- LOGIN INTERFACE ---
        if not system.current_user:
            name = input("Enter your username to login: ")
            if system.login(name):
                print("Logged in as:", system.current_user.name)
            else:
                print("Name cannot be empty.")
                continue

        # --- MENU DISPLAY ---
        print("\n--- FOUNDIT MENU ---")
        print("1. View Items")
        print("2. Report Item")
        print("3. Search Items")
        print("4. Claim Item")
        print("5. Logout")
        
        choice = input("Enter choice: ")

        # --- VIEW ITEMS (READ) ---
        if choice == "1":
            print("\n--- ALL ITEMS ---")
            if not system.items:
                print("No items reported yet.")
            else:
                for i, item in enumerate(system.items):
                    print(f"{i + 1}. {item.name} ({item.status}) - {item.location}")
                    print(f"   Category: {item.category} | Desc: {item.desc} | Posted by: {item.owner}")

        # --- REPORT ITEM (CREATE) ---
        elif choice == "2":
            print("\n--- REPORT ITEM ---")
            name = input("Item name: ")
            category = input("Category: ")
            location = input("Building location: ")
            desc = input("Description: ")
            
            system.add_item(name, category, location, desc)
            print("Item added successfully!")

        # --- SEARCH ITEMS (FILTER) ---
        elif choice == "3":
            print("\n--- SEARCH ---")
            if not system.items:
                print("No items to search.")
            else:
                keyword = input("Enter search keyword: ")
                results = system.search_items(keyword)
                if results:
                    for item in results:
                        print(f"- {item.name} found in {item.location} [Status: {item.status}]")
                else:
                    print("No matching items found.")

        # --- CLAIM ITEM & VERIFY (UPDATE STATUS) ---
        elif choice == "4":
            print("\n--- CLAIM ITEM ---")
            if not system.items:
                print("No items available to claim.")
            else:
                for i, item in enumerate(system.items):
                    print(f"{i + 1}. {item.name} - {item.status}")
                
                try:
                    idx = int(input("Enter item number to claim: ")) - 1
                    print("Description check:", system.items[idx].desc)
                    ans = input("Answer verification question (details): ")
                    if system.claim_item(idx, ans):
                        print("Item marked as Claimed!")
                    else:
                        print("Claim cancelled or invalid answer.")
                except ValueError:
                    print("Please enter a valid number.")

        # --- LOGOUT ---
        elif choice == "5":
            print("Logging out...")
            system.logout()
        else:
            print("Invalid choice, try again.")

if __name__ == "__main__":
    run_cli()
