# main.py
import datetime
from models import Institution, User, Category, Tracking, Item, Post

def run_cli():
    # Initialize basic campus institution context
    school = Institution("Mapúa Malayan Colleges Mindanao", "Davao City")
    
    # Global storage lists using the new classes
    posts = []
    categories = [
        Category("Electronics", "CAT-01"),
        Category("Tumblers/Bottles", "CAT-02"),
        Category("IDs/Cards", "CAT-03"),
        Category("Others", "CAT-04")
    ]
    
    current_user = None

    print(f"=== Welcome to FoundIt ({school.get_details()}) ===")

    while True:
        # --- LOGIN / SESSION MANAGEMENT ---
        if not current_user:
            print("\n--- INSTITUTIONAL LOGIN ---")
            username = input("Enter your username: ")
            institutional_id = input("Enter your Institutional ID: ")
            
            temp_user = User(username, institutional_id)
            if temp_user.login():
                current_user = temp_user
                print(f"Successfully logged in as: {current_user.username}")
            else:
                print("Invalid username. Try again.")
                continue

        # --- MAIN MENU ---
        print(f"\n--- FOUNDIT MENU ({school.institution_name}) ---")
        print("1. View Feed / Posts")
        print("2. Report Lost Item (Create Post)")
        print("3. Search & Filter by Category")
        print("4. Update Item Tracking Status")
        print("5. Logout")
        
        choice = input("Enter choice (1-5): ")

        if choice == "1":
            print("\n--- RECENT POSTS FEED ---")
            if not posts:
                print("No posts available.")
            else:
                for idx, p in enumerate(posts):
                    print(f"[{idx + 1}] Item: {p.item.item_name} | Status: {p.item.tracking.current_status}")
                    print(f"    Category: {p.item.category.category_name} | Desc: {p.item.description}")
                    print(f"    Posted by: {p.user.username} on {p.date_posted}")
                    print("-" * 40)

        elif choice == "2":
            print("\n--- REPORT A LOST ITEM ---")
            item_name = input("Enter item name: ")
            description = input("Enter brief description: ")
            
            print("\nSelect Category:")
            for idx, cat in enumerate(categories):
                print(f"[{idx + 1}] {cat.category_name}")
            
            try:
                cat_choice = int(input("Enter category number: ")) - 1
                selected_category = categories[cat_choice]
            except (ValueError, IndexError):
                print("Invalid category choice. Defaulting to 'Others'.")
                selected_category = categories[3]

            # Create objects using the new architecture
            new_item = Item(item_name, description, selected_category)
            today_date = datetime.date.today().strftime("%Y-%m-%d")
            new_post = Post(post_id=f"POST-{len(posts)+1}", date_posted=today_date, user=current_user, item=new_item)
            
            if new_post.create_post():
                posts.append(new_post)
                print("Item successfully posted to the dashboard feed!")

        elif choice == "3":
            print("\n--- FILTER BY CATEGORY ---")
            for idx, cat in enumerate(categories):
                print(f"[{idx + 1}] {cat.category_name}")
            
            try:
                cat_choice = int(input("Select category number to filter: ")) - 1
                target_cat = categories[cat_choice]
                
                # Extract items from posts and apply category filtering method
                all_items = [p.item for p in posts]
                filtered_items = target_cat.filter_by_category(all_items)
                
                print(f"\nResults for category: {target_cat.category_name}")
                if not filtered_items:
                    print("No items found under this category.")
                else:
                    for item in filtered_items:
                        print(f"- {item.item_name} | Status: {item.tracking.current_status} | Desc: {item.description}")
            except (ValueError, IndexError):
                print("Invalid selection.")

        elif choice == "4":
            print("\n--- UPDATE ITEM TRACKING STATUS ---")
            if not posts:
                print("No posts to update.")
            else:
                for idx, p in enumerate(posts):
                    print(f"[{idx + 1}] {p.item.item_name} (Current Status: {p.item.tracking.current_status})")
                
                try:
                    post_idx = int(input("Select post number to update: ")) - 1
                    target_post = posts[post_idx]
                    
                    print("Select New Status:")
                    print("[1] Lost")
                    print("[2] Pending Claim")
                    print("[3] Claimed")
                    status_choice = input("Enter choice (1-3): ")
                    
                    if status_choice == "1":
                        target_post.item.tracking.update_tracking_status("Lost")
                    elif status_choice == "2":
                        target_post.item.tracking.update_tracking_status("Pending Claim")
                    elif status_choice == "3":
                        target_post.item.tracking.update_tracking_status("Claimed")
                    else:
                        print("Invalid status option.")
                        continue
                        
                    print(f"Tracking status successfully updated to: {target_post.item.tracking.current_status}")
                except (ValueError, IndexError):
                    print("Invalid selection.")

        elif choice == "5":
            print(f"Logging out user: {current_user.username}...")
            current_user = current_user.logout()
        else:
            print("Invalid menu choice. Please select from 1 to 5.")

if __name__ == "__main__":
    run_cli()
