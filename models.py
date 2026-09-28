# models.py
import json
import os

DB_FILE = "database.json"

def save_database(posts_list):
    data = []
    for p in posts_list:
        data.append({
            "post_id": p.post_id,
            "date_posted": p.date_posted,
            "username": p.user.username,
            "institutional_id": p.user.institutional_id,
            "item_name": p.item.item_name,
            "description": p.item.description,
            "category_name": p.item.category.category_name,
            "category_code": p.item.category.category_code,
            "status": p.item.tracking.current_status
        })
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_database(categories_list):
    if not os.path.exists(DB_FILE):
        return []
    
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
        
        loaded_posts = []
        for d in data:
            # Re-instantiate your OOP classes from raw data
            user = User(d["username"], d["institutional_id"])
            cat = next((c for c in categories_list if c.category_name == d["category_name"]), categories_list[3])
            item = Item(d["item_name"], d["description"], cat)
            item.tracking.current_status = d["status"]
            post = Post(d["post_id"], d["date_posted"], user, item)
            loaded_posts.append(post)
        return loaded_posts
    except Exception:
        return []
        
class Institution:
    def __init__(self, institution_name, campus_location):
        self.institution_name = institution_name
        self.campus_location = campus_location

    def get_details(self):
        return f"{self.institution_name} - {self.campus_location}"


class User:
    def __init__(self, username, institutional_id):
        self.username = username
        self.institutional_id = institutional_id

    def login(self):
        return bool(self.username.strip())

    def logout(self):
        return None


class Category:
    def __init__(self, category_name, category_code):
        self.category_name = category_name
        self.category_code = category_code

    def filter_by_category(self, items):
        return [item for item in items if item.category.category_name == self.category_name]


class Tracking:
    def __init__(self, tracking_id, current_status="Lost"):
        self.tracking_id = tracking_id
        self.current_status = current_status  # "Lost", "Pending", "Claimed"

    def update_tracking_status(self, new_status):
        self.current_status = new_status


class Item:
    def __init__(self, item_name, description, category):
        self.item_name = item_name
        self.description = description
        self.category = category  # Category object
        self.tracking = Tracking(tracking_id=f"TRK-{id(self)}")

    def get_item_info(self):
        return f"{self.item_name} [{self.tracking.current_status}]"


class Post:
    def __init__(self, post_id, date_posted, user, item):
        self.post_id = post_id
        self.date_posted = date_posted
        self.user = user        # User object
        self.item = item        # Item object

    def create_post(self):
        return True

    def remove_post(self):
        return True
