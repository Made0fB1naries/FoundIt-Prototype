# models.py

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
