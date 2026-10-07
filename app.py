# app.py
import datetime
from abc import ABC, abstractmethod

import streamlit as st
import extra_streamlit_components as stx

from models import (AuthService, CategoryCatalog, Institution, LostAndFoundService,
                    Status, SupabaseImageStorage, SupabasePostRepository, ValidationError, get_gateway)


# ---------------------------------------------------------------- session + cookies

class SessionField:
    """Descriptor: an attribute stored in st.session_state."""

    def __init__(self, default=None):
        self._default = default

    def __set_name__(self, owner, name):
        self._key = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return st.session_state.setdefault(self._key, self._default)

    def __set__(self, obj, value):
        st.session_state[self._key] = value


class AppState:
    current_user = SessionField()
    logged_out = SessionField(False)
    pending_token = SessionField()
    pending_delete = SessionField(False)
    status_msg = SessionField()
    report_n = SessionField(0)
    report_msg = SessionField()
    service = SessionField()

    def reset_navigation(self):
        st.session_state.pop("nav", None)


class CookieSession:
    NAME = "foundit_refresh_token"
    DAYS = 7

    def __init__(self, state, auth):
        self._state = state
        self._auth = auth
        self._cookies = stx.CookieManager()

    def restore(self):  # auto-login, survives page refresh
        state = self._state
        if state.current_user or state.logged_out:
            return
        token = self._cookies.get(self.NAME)
        if token:
            result = self._auth.restore(token)
            if result.success:
                state.current_user = result.user
                state.pending_token = result.refresh_token
                st.rerun()

    def sync(self):  # write / clear the cookie safely
        state = self._state
        if state.pending_token and state.current_user:
            self._cookies.set(
                self.NAME,
                state.pending_token,
                expires_at=datetime.datetime.now() + datetime.timedelta(days=self.DAYS),
            )
            state.pending_token = None
        if state.pending_delete and not state.current_user:
            self._cookies.delete(self.NAME)
            state.pending_delete = False


# ---------------------------------------------------------------- pages

class Page(ABC):
    title = ""
    section = ""  # matches the names returned by User.sections()
    ALL_CAMPUSES = "All Campuses"

    def __init__(self, service, state):
        self._service = service
        self._state = state

    def _campus_filter(self, key):
        options = [self.ALL_CAMPUSES] + self._service.institution.campuses
        choice = st.selectbox("Campus", options, key=key)
        return None if choice == self.ALL_CAMPUSES else choice

    @abstractmethod
    def render(self, user):
        ...


class AdminPage(Page):
    def render(self, user):
        if not user.can_manage_items():
            st.error("Only administrators can open this page.")
            return
        self._render(user)

    @abstractmethod
    def _render(self, user):
        ...


class FeedPage(Page):
    title = "View Feed"
    section = "Feed"

    def render(self, user):
        st.header("Recent Dashboard Feed")
        col_search, col_campus = st.columns([2, 1])
        with col_search:
            query = st.text_input("Search feed (title, category, description):", "").strip()
        with col_campus:
            campus = self._campus_filter("feed_campus")

        posts = self._service.active(campus, query)
        if not posts:
            st.info("No items match your search or filter.")
            return
        for post in posts:
            self._render_card(post)

    @staticmethod
    def _render_card(post):
        with st.container():
            st.subheader(post.item.name)
            if post.item.image_url:
                st.image(post.item.image_url, width=300)
            st.write(f"**Status:** `{post.item.tracking.status.value}`")
            st.write(f"**Campus Location:** `{post.item.campus_location}`")
            st.write(f"**Category:** {post.item.category.name}")
            st.write(f"**Description:** {post.item.description}")
            st.caption(f"Posted by {post.user.username} on {post.date_posted}")
            st.markdown("---")


class ClaimedPage(Page):
    title = "Claimed Items"
    section = "Claimed"

    def render(self, user):
        st.header("Claimed Items")
        st.caption(f"Claimed items stay here for {self._service.RETENTION_DAYS} days, then are removed automatically.")
        campus = self._campus_filter("claimed_campus")

        posts = self._service.claimed(campus)
        if not posts:
            st.info("No claimed items.")
            return
        for post in posts:
            st.subheader(post.item.name)
            if post.item.image_url:
                st.image(post.item.image_url, width=300)
            st.write(f"**Campus Location:** `{post.item.campus_location}`")
            st.write(f"**Category:** {post.item.category.name}")
            remaining = post.item.tracking.days_left(self._service.RETENTION_DAYS)
            if remaining is not None:
                st.caption(f"Removed in {remaining} day(s)")
            st.markdown("---")


class ReportItemPage(AdminPage):
    title = "Report Item"
    section = "Report"

    def _render(self, user):
        rk = self._state.report_n  # new key per post, so the form comes back empty
        st.header("Report a Lost Item")

        if self._state.report_msg:  # message saved before the rerun
            st.success(self._state.report_msg)
            self._state.report_msg = None

        with st.form("report_form"):
            name = st.text_input("Item Name", key=f"r_name_{rk}")
            description = st.text_area("Description / Distinguishing Features", key=f"r_desc_{rk}")
            campus = st.selectbox("Campus Holding Office", self._service.institution.campuses, key=f"r_campus_{rk}")
            category = st.selectbox("Category", self._service.catalog.names(), key=f"r_cat_{rk}")
            image = st.file_uploader("Upload Item Photo", type=["jpg", "jpeg", "png"], key=f"r_photo_{rk}")

            if st.form_submit_button("Post Item"):
                try:
                    self._service.report(user, name, description, category, campus, image)
                except ValidationError as e:
                    st.warning(str(e))
                else:
                    self._state.report_n += 1
                    self._state.report_msg = "Item posted successfully and saved to Supabase!"
                    st.rerun()


class UpdateStatusPage(AdminPage):
    title = "Update Tracking Status"
    section = "Update status"

    @staticmethod
    def _label(post):
        return f"{post.item.name} ({post.item.tracking.status.value}) - {post.user.username}"

    def _render(self, user):
        st.header("Update Item Status")

        if self._state.status_msg:  # message saved before the rerun
            st.success(self._state.status_msg)
            self._state.status_msg = None

        posts = list(reversed(self._service.posts))  # newest first
        if not posts:
            st.info("No items available to update.")
            return

        by_id = {p.post_id: p for p in posts}
        selected_id = st.selectbox(
            "Select Item to Update", list(by_id.keys()), format_func=lambda pid: self._label(by_id[pid])
        )
        new_status = st.radio("Select New Status", [s.value for s in Status])

        if st.button("Apply Status Update"):
            self._service.set_status(user, selected_id, new_status)
            self._state.status_msg = f"Status updated to **{new_status}** in Supabase!"
            st.rerun()


# ---------------------------------------------------------------- application

class FoundItApp:
    PAGES = (FeedPage, ClaimedPage, ReportItemPage, UpdateStatusPage)

    def __init__(self):
        self._gateway = get_gateway()
        self._state = AppState()
        self._auth = AuthService(self._gateway)
        self._cookies = CookieSession(self._state, self._auth)
        self._institution = Institution("Mapúa Malayan Colleges Mindanao", "Davao City", ["RSY Building", "RG Birrey"])

    def _service(self):
        if self._state.service is None:  # built after login, so visitors never hit the database
            catalog = CategoryCatalog.default()
            repository = SupabasePostRepository(
                self._gateway, catalog, SupabaseImageStorage(self._gateway), self._institution.default_campus
            )
            self._state.service = LostAndFoundService(repository, catalog, self._institution)
        return self._state.service

    def _logout(self):
        self._state.current_user = None
        self._state.logged_out = True
        self._state.pending_delete = True
        self._state.service = None  # drop cached posts
        self._state.reset_navigation()
        st.rerun()

    def _render_login(self):
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Institutional Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                result = self._auth.login(email, password)
                if result.success:
                    self._state.current_user = result.user
                    self._state.logged_out = False
                    self._state.pending_token = result.refresh_token
                    st.rerun()
                else:
                    st.error(f"Authentication failed: {result.error}")

    def _render_main(self, user):
        service = self._service()
        service.refresh_if_stale()

        st.sidebar.write(f"**{user.username}**")
        st.sidebar.caption(f"Role: {user.role_label}")

        if st.sidebar.button("Logout"):
            self._logout()

        st.sidebar.markdown("---")

        allowed = user.sections()
        pages = [cls(service, self._state) for cls in self.PAGES if cls.section in allowed]
        choice = st.sidebar.radio("Navigation", [p.title for p in pages], key="nav")
        if not user.can_manage_items():
            st.sidebar.info(
                "You are logged in as a standard user. "
                "Only authorized administrators can report or update items."
            )

        next(p for p in pages if p.title == choice).render(user)

    def run(self):
        self._cookies.restore()
        self._cookies.sync()

        st.title("FoundIt: Campus Lost & Found Hub")
        st.caption(self._institution.get_details())
        st.markdown("---")

        user = self._state.current_user
        if user is None:
            self._render_login()
        else:
            self._render_main(user)


def main():
    st.set_page_config(page_title="FoundIt - Campus Lost & Found", page_icon="", layout="centered")
    FoundItApp().run()


main()
