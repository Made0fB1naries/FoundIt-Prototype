# models.py

class User:
    def __init__(self, name):
        self.name = name

class Item:
    def __init__(self, name, category, location, desc, owner):
        self.name = name
        self.category = category
        self.location = location
        self.desc = desc
        self.owner = owner
        self.status = "Lost"

class LostAndFoundSystem:
    def __init__(self):
        self.items = []
        self.current_user = None

    def login(self, name):
        if name.strip():
            self.current_user = User(name.strip())
            return True
        return False

    def logout(self):
        self.current_user = None

    def add_item(self, name, category, location, desc):
        if self.current_user:
            new_item = Item(name, category, location, desc, self.current_user.name)
            self.items.append(new_item)
            return True
        return False

    def search_items(self, keyword):
        keyword = keyword.lower()
        results = []
        for item in self.items:
            if keyword in item.name.lower() or keyword in item.location.lower():
                results.append(item)
        return results

    def claim_item(self, index, verification_answer):
        if 0 <= index < len(self.items):
            item = self.items[index]
            if verification_answer:
                item.status = "Claimed"
                return True
        return False
