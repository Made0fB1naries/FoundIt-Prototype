# app.py
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass

import extra_streamlit_components as stx
import streamlit as st

from models import (CLAIMED_RETENTION_DAYS, AuthService, CategoryRegistry, Institution,
                    Item, Post, PostRepository, Status, User)

CAMPUS_LOCATIONS = ["RSY Building", "RG Birrey"]


# ----------------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------------
class _Field:
    """Descriptor that maps an attribute to a st.session_state key."""

    def __set_name__(self, owner, name):
        self.key = name

    def __get__(self, obj, owner=None):
        return st.session_state[self.key]

    def __set__(self, obj, value):
        st.session_state[self.key] = value


class AppState:
    categories = _Field()
    posts = _Field()
    current_user = _Field()
    logged_out = _Field()
    pending_token = _Field()
    pending_delete = _Field()
    status_msg = _Field()

    def __init__(self, repo: PostRepository):
        s = st.session_state
        if "categories" not in s:
            s.categories = CategoryRegistry()
        if "posts" not in s:
            s.posts = repo.load_all(s.categories)
        s.setdefault("current_user", None)
        s.setdefault("logged_out", False)
        s.setdefault("pending_token", None)
        s.setdefault("pending_delete", False)
        s.setdefault("status_msg", None)

    @property
    def is_authenticated(self):
        return self.current_user is not None


# ----------------------------------------------------------------------------
# Login session + cookie handling
# ----------------------------------------------------------------------------
class SessionManager:
    COOKIE_NAME = "foundit_refresh_token"
    COOKIE_DAYS = 7

    def __init__(self, state: AppState, auth: AuthService):
        self.state = state
        self.auth = auth
        self.cookies = stx.CookieManager()

    def restore_from_cookie(self):
        """Auto-login after a page refresh."""
        if self.state.is_authenticated or self.state.logged_out:
            return
        token = self.cookies.get(self.COOKIE_NAME)
        if not token:
            return
        result = self.auth.restore(token)
        if result.success:
            self.state.current_user = User.from_email(result.email, result.is_admin)
            self.state.pending_token = result.refresh_token
            st.rerun()

    def sync_cookie(self):
        """Write / clear the cookie safely (after the rerun)."""
        if self.state.pending_token and self.state.is_authenticated:
            self.cookies.set(
                self.COOKIE_NAME,
                self.state.pending_token,
                expires_at=datetime.datetime.now() + datetime.timedelta(days=self.COOKIE_DAYS),
            )
            self.state.pending_token = None
        if self.state.pending_delete and not self.state.is_authenticated:
            self.cookies.delete(self.COOKIE_NAME)
            self.state.pending_delete = False

    def login(self, email, password):
        result = self.auth.sign_in(email, password)
        if not result.success:
            return result
        self.state.current_user = User.from_email(email, result.is_admin)
        self.state.logged_out = False
        self.state.pending_token = result.refresh_token
        return result

    def logout(self):
        self.state.current_user = None
        self.state.logged_out = True
        self.state.pending_delete = True


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
@dataclass
class PageContext:
    state: AppState
    repo: PostRepository


class Page(ABC):
    title: str = ""
    admin_only: bool = False

    def __init__(self, ctx: PageContext):
        self.ctx = ctx

    @property
    def state(self):
        return self.ctx.state

    def reload_posts(self):
        self.state.posts = self.ctx.repo.load_all(self.state.categories)

    def _newest_first(self, claimed):
        return [p for p in self.state.posts[::-1] if p.is_claimed == claimed]

    @abstractmethod
    def render(self):
        ...


class FeedPage(Page):
    title = "View Feed"

    def render(self):
        st.header("Recent Dashboard Feed")
        col_search, col_campus = st.columns([2, 1])
        with col_search:
            query = st.text_input("Search feed (title, category, description):", "").strip()
        with col_campus:
            campus = st.selectbox("Campus", ["All Campuses"] + CAMPUS_LOCATIONS, key="feed_campus")

        posts = self._newest_first(claimed=False)
        if campus != "All Campuses":
            posts = [p for p in posts if p.item.campus_location == campus]
        if query:
            posts = [p for p in posts if p.item.matches(query)]

        if not posts:
            st.info("No items match your search or filter.")
            return
        for post in posts:
            self._render_card(post)

    @staticmethod
    def _render_card(post):
        with st.container():
            st.subheader(post.item.item_name)
            if post.item.image_url:
                st.image(post.item.image_url, width=300)
            st.write(f"**Status:** `{post.item.tracking.current_status}`")
            st.write(f"**Campus Location:** `{post.item.campus_location}`")
            st.write(f"**Category:** {post.item.category.category_name}")
            st.write(f"**Description:** {post.item.description}")
            st.caption(f"Posted by {post.user.username} on {post.date_posted}")
            st.markdown("---")


class ClaimedPage(Page):
    title = "Claimed Items"

    def render(self):
        st.header("Claimed Items")
        st.caption(f"Claimed items stay here for {CLAIMED_RETENTION_DAYS} days, then are removed automatically.")
        campus = st.selectbox("Campus", ["All Campuses"] + CAMPUS_LOCATIONS, key="claimed_campus")

        posts = self._newest_first(claimed=True)
        if campus != "All Campuses":
            posts = [p for p in posts if p.item.campus_location == campus]

        if not posts:
            st.info("No claimed items.")
            return
        for post in posts:
            st.subheader(post.item.item_name)
            if post.item.image_url:
                st.image(post.item.image_url, width=300)
            st.write(f"**Campus Location:** `{post.item.campus_location}`")
            st.write(f"**Category:** {post.item.category.category_name}")
            remaining = post.item.tracking.days_left()
            if remaining is not None:
                st.caption(f"Removed in {remaining} day(s)")
            st.markdown("---")


class ReportItemPage(Page):
    title = "Report Item"
    admin_only = True

    def render(self):
        st.header("Report a Lost Item")
        with st.form("report_form"):
            name = st.text_input("Item Name")
            description = st.text_area("Description / Distinguishing Features")
            campus = st.selectbox("Campus Holding Office", CAMPUS_LOCATIONS)
            category_name = st.selectbox("Category", self.state.categories.names)
            image = st.file_uploader("Upload Item Photo", type=["jpg", "jpeg", "png"])

            if st.form_submit_button("Post Item"):
                if not name.strip():
                    st.warning("Please provide an item name.")
                    return
                item = Item(name, description, self.state.categories.get(category_name), campus_location=campus)
                post = Post.create(self.state.current_user, item)
                self.ctx.repo.save(post, image_file=image)
                self.reload_posts()
                st.success("Item posted successfully and saved to Supabase!")


class UpdateStatusPage(Page):
    title = "Update Tracking Status"
    admin_only = True

    def render(self):
        st.header("Update Item Status")

        if self.state.status_msg:
            st.success(self.state.status_msg)
            self.state.status_msg = None

        if not self.state.posts:
            st.info("No items available to update.")
            return

        options = {p.post_id: p for p in self.state.posts}
        selected_id = st.selectbox(
            "Select Item to Update",
            list(options.keys()),
            format_func=lambda pid: (
                f"{options[pid].item.item_name} "
                f"({options[pid].item.tracking.current_status}) - {options[pid].user.username}"
            ),
        )
        new_status = st.radio("Select New Status", Status.ALL)

        if st.button("Apply Status Update"):
            target = options[selected_id]
            target.item.tracking.update_tracking_status(new_status)
            self.ctx.repo.update_status(target.post_id, new_status)
            self.reload_posts()
            self.state.status_msg = f"Status updated to **{new_status}** in Supabase!"
            st.rerun()


# ----------------------------------------------------------------------------
# Application
# ----------------------------------------------------------------------------
class FoundItApp:
    PAGES = [FeedPage, ClaimedPage, ReportItemPage, UpdateStatusPage]

    def __init__(self):
        st.set_page_config(page_title="FoundIt - Campus Lost & Found", page_icon="", layout="centered")
        self.school = Institution("Mapúa Malayan Colleges Mindanao", "Davao City")
        self.repo = PostRepository()
        self.state = AppState(self.repo)
        self.session = SessionManager(self.state, AuthService())
        self.ctx = PageContext(self.state, self.repo)

    def run(self):
        self.session.restore_from_cookie()
        self.session.sync_cookie()

        st.title("FoundIt: Campus Lost & Found Hub")
        st.caption(self.school.get_details())
        st.markdown("---")

        if self.state.is_authenticated:
            self._render_main()
        else:
            self._render_login()

    def _render_login(self):
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Institutional Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                result = self.session.login(email, password)
                if result.success:
                    st.rerun()
                else:
                    st.error(f"Authentication failed: {result.error}")

    def _render_main(self):
        user = self.state.current_user
        st.sidebar.write(f"**{user.username}**")
        st.sidebar.caption(f"Role: {user.role_label}")

        if st.sidebar.button("Logout"):
            self.session.logout()
            st.rerun()

        st.sidebar.markdown("---")

        pages = [cls(self.ctx) for cls in self.PAGES if user.is_admin or not cls.admin_only]
        choice = st.sidebar.radio("Navigation", [p.title for p in pages])
        if not user.is_admin:
            st.sidebar.info(
                "You are logged in as a standard user. "
                "Only authorized administrators can report or update items."
            )

        next(p for p in pages if p.title == choice).render()


FoundItApp().run()
