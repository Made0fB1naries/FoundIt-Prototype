# models.py
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import streamlit as st
from supabase import create_client, Client

CLAIMED_RETENTION_DAYS = 7


class Status:
    """Allowed tracking statuses."""
    LOST = "Lost"
    PENDING_CLAIM = "Pending Claim"
    CLAIMED = "Claimed"
    ALL = [LOST, PENDING_CLAIM, CLAIMED]


class Institution:
    def __init__(self, institution_name, campus_location):
        self.institution_name = institution_name
        self.campus_location = campus_location

    def get_details(self):
        return f"{self.institution_name} - {self.campus_location}"


class User:
    def __init__(self, username, institutional_id, is_admin=False):
        self.username = username
        self.institutional_id = institutional_id
        self.is_admin = is_admin

    @classmethod
    def from_email(cls, email, is_admin=False):
        return cls(username=email.split("@")[0], institutional_id=email, is_admin=is_admin)

    @property
    def role_label(self):
        return "Administrator" if self.is_admin else "Student/Faculty"


class Category:
    def __init__(self, category_name, category_code):
        self.category_name = category_name
        self.category_code = category_code


class CategoryRegistry:
    """Holds the known categories and resolves them by name."""
    FALLBACK_NAME = "Others"

    def __init__(self, categories=None):
        self._categories = categories or [
            Category("Electronics", "CAT-01"),
            Category("Tumblers/Bottles", "CAT-02"),
            Category("IDs/Cards", "CAT-03"),
            Category(self.FALLBACK_NAME, "CAT-04"),
        ]

    @property
    def names(self):
        return [c.category_name for c in self._categories]

    def get(self, name):
        for c in self._categories:
            if c.category_name == name:
                return c
        return self.get(self.FALLBACK_NAME) if name != self.FALLBACK_NAME else self._categories[-1]


class Tracking:
    def __init__(self, tracking_id, current_status=Status.LOST, date_claimed=None):
        self.tracking_id = tracking_id
        self.current_status = current_status
        self.date_claimed = date_claimed

    @property
    def is_claimed(self):
        return self.current_status == Status.CLAIMED

    def update_tracking_status(self, new_status):
        self.current_status = new_status
        self.date_claimed = datetime.now(timezone.utc).isoformat() if new_status == Status.CLAIMED else None

    def days_left(self):
        """Days before a claimed item is purged, or None if unknown."""
        try:
            claimed_at = datetime.fromisoformat(self.date_claimed)
            if claimed_at.tzinfo is None:
                claimed_at = claimed_at.replace(tzinfo=timezone.utc)
            remaining = claimed_at + timedelta(days=CLAIMED_RETENTION_DAYS) - datetime.now(timezone.utc)
            return max(remaining.days, 0)
        except (TypeError, ValueError):
            return None


class Item:
    DEFAULT_CAMPUS = "RSY Building"

    def __init__(self, item_name, description, category, campus_location=DEFAULT_CAMPUS, image_url=None):
        self.item_name = item_name
        self.description = description
        self.category = category
        self.campus_location = campus_location
        self.image_url = image_url
        self.tracking = Tracking(tracking_id=f"TRK-{id(self)}")

    def matches(self, query):
        """Case-insensitive search over name, category and description."""
        q = query.strip().lower()
        return (
            q in self.item_name.lower()
            or q in self.category.category_name.lower()
            or q in (self.description or "").lower()
        )


class Post:
    def __init__(self, post_id, date_posted, user, item):
        self.post_id = post_id
        self.date_posted = date_posted
        self.user = user
        self.item = item

    @staticmethod
    def new_id():
        return f"POST-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"

    @classmethod
    def create(cls, user, item):
        return cls(cls.new_id(), date.today().strftime("%Y-%m-%d"), user, item)

    @property
    def is_claimed(self):
        return self.item.tracking.is_claimed

    def to_record(self, image_url=None):
        """Row dict for the `posts` table."""
        return {
            "post_id": self.post_id,
            "date_posted": self.date_posted,
            "username": self.user.username,
            "institutional_id": self.user.institutional_id,
            "item_name": self.item.item_name,
            "description": self.item.description,
            "category_name": self.item.category.category_name,
            "campus_location": self.item.campus_location,
            "image_url": image_url,
            "status": self.item.tracking.current_status,
            "date_claimed": self.item.tracking.date_claimed,
        }

    @classmethod
    def from_record(cls, record, registry):
        user = User(record["username"], record["institutional_id"])
        item = Item(
            record["item_name"],
            record["description"],
            registry.get(record["category_name"]),
            campus_location=record.get("campus_location", Item.DEFAULT_CAMPUS),
            image_url=record.get("image_url"),
        )
        item.tracking.current_status = record.get("status", Status.LOST)
        item.tracking.date_claimed = record.get("date_claimed")
        return cls(record["post_id"], record["date_posted"], user, item)


# ----------------------------------------------------------------------------
# Supabase: auth + persistence
# ----------------------------------------------------------------------------
@st.cache_resource
def _anon_client() -> Client:  # reads only
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


@st.cache_resource
def _admin_client() -> Client:  # service role, writes only
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])


@dataclass
class AuthResult:
    success: bool
    email: str = None
    is_admin: bool = False
    refresh_token: str = None
    error: str = None


class AuthService:
    def __init__(self):
        raw = st.secrets.get("ADMIN_EMAILS", "")
        self._admins = {e.strip().lower() for e in raw.split(",") if e.strip()}

    def is_admin(self, email):
        return bool(email) and email.strip().lower() in self._admins

    @staticmethod
    def _new_client() -> Client:  # throwaway, per login
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

    def _to_result(self, response):
        user, session = response.user, response.session
        if not user or not session:
            return AuthResult(False, error="No user/session returned")
        return AuthResult(True, user.email, self.is_admin(user.email), session.refresh_token)

    def sign_in(self, email, password) -> AuthResult:
        try:
            response = self._new_client().auth.sign_in_with_password({"email": email, "password": password})
            return self._to_result(response)
        except Exception as e:
            return AuthResult(False, error=str(e))

    def restore(self, refresh_token) -> AuthResult:
        try:
            return self._to_result(self._new_client().auth.refresh_session(refresh_token))
        except Exception as e:
            return AuthResult(False, error=str(e))


class PostRepository:
    TABLE = "posts"
    BUCKET = "item-images"

    def __init__(self, reader: Client = None, writer: Client = None):
        self._reader = reader or _anon_client()
        self._writer = writer or _admin_client()

    # --- reads ---
    def load_all(self, registry):
        self.purge_expired_claims()
        rows = self._reader.table(self.TABLE).select("*").execute().data
        return [Post.from_record(r, registry) for r in rows]

    # --- writes ---
    def save(self, post, image_file=None):
        image_url = self._upload_image(post.post_id, image_file) if image_file is not None else None
        self._writer.table(self.TABLE).insert(post.to_record(image_url)).execute()

    def update_status(self, post_id, new_status):
        claimed_at = datetime.now(timezone.utc).isoformat() if new_status == Status.CLAIMED else None
        self._writer.table(self.TABLE).update(
            {"status": new_status, "date_claimed": claimed_at}
        ).eq("post_id", post_id).execute()

    def purge_expired_claims(self):
        threshold = (datetime.now(timezone.utc) - timedelta(days=CLAIMED_RETENTION_DAYS)).isoformat()
        expired = (
            self._writer.table(self.TABLE)
            .select("post_id, image_url")
            .eq("status", Status.CLAIMED)
            .lt("date_claimed", threshold)
            .execute()
        )
        for row in expired.data or []:
            self.delete(row["post_id"], row.get("image_url"))

    def delete(self, post_id, image_url=None):
        if image_url:
            try:
                self._writer.storage.from_(self.BUCKET).remove([image_url.split("/")[-1]])
            except Exception as e:
                print(f"Error deleting image from storage: {e}")
        self._writer.table(self.TABLE).delete().eq("post_id", post_id).execute()

    # --- helpers ---
    def _upload_image(self, post_id, image_file):
        path = f"{post_id}.{image_file.name.split('.')[-1]}"
        bucket = self._writer.storage.from_(self.BUCKET)
        bucket.upload(
            path=path,
            file=image_file.getvalue(),
            file_options={"content-type": image_file.type, "upsert": "true"},
        )
        return bucket.get_public_url(path)
