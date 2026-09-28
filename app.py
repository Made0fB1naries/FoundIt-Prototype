# app.py
import streamlit as st
import datetime
from models import Institution, User, Category, Tracking, Item, Post

# Page Config
st.set_page_config(page_title="FoundIt - Campus Lost & Found", page_icon="🔍", layout="centered")

# Initialize School Context
school = Institution("Mapúa Malayan Colleges Mindanao", "Davao City")

# Initialize Categories in Session State if not present
if "categories" not in st.session_state:
    st.session_state.categories = [
        Category("Electronics", "CAT-01"),
        Category("Tumblers/Bottles", "CAT-02"),
        Category("IDs/Cards", "CAT-03"),
        Category("Others", "CAT-04")
    ]

# Initialize Posts and User Session State
if "posts" not in st.session_state:
    st.session_state.posts = []

if "current_user" not in st.session_state:
    st.session_state.current_user = None

st.title("📍 FoundIt: Campus Lost & Found Hub")
st.caption(f"{school.get_details()}")
st.markdown("---")

# --- 1. USER AUTHENTICATION / LOGIN UI ---
if not st.session_state.current_user:
    st.subheader("Institutional Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        institutional_id = st.text_input("Institutional ID")
        submit_login = st.form_submit_button("Login")
        
        if submit_login:
            temp_user = User(username, institutional_id)
            if temp_user.login():
                st.session_state.current_user = temp_user
                st.success(f"Welcome, {temp_user.username}!")
                st.rerun()
            else:
                st.error("Please enter a valid username.")
else:
    # Sidebar for User Info & Logout
    st.sidebar.write(f"👤 **{st.session_state.current_user.username}**")
    st.sidebar.caption(f"ID: {st.session_state.current_user.institutional_id}")
    if st.sidebar.button("Logout"):
        st.session_state.current_user = st.session_state.current_user.logout()
        st.rerun()

    st.sidebar.markdown("---")
    navigation = st.sidebar.radio("Navigation", ["View Feed", "Report Item", "Filter by Category", "Update Tracking Status"])

    # --- 2. VIEW FEED UI ---
    if navigation == "View Feed":
        st.header("📋 Recent Dashboard Feed")
        if not st.session_state.posts:
            st.info("No items posted yet. Be the first to report one!")
        else:
            for idx, post in enumerate(st.session_state.posts):
                with st.container():
                    st.subheader(f"{idx + 1}. {post.item.item_name}")
                    st.write(f"**Status:** `{post.item.tracking.current_status}`")
                    st.write(f"**Category:** {post.item.category.category_name}")
                    st.write(f"**Description:** {post.item.description}")
                    st.caption(f"Posted by {post.user.username} on {post.date_posted}")
                    st.markdown("---")

    # --- 3. REPORT ITEM UI ---
    elif navigation == "Report Item":
        st.header("📝 Report a Lost Item")
        with st.form("report_form"):
            item_name = st.text_input("Item Name")
            description = st.text_area("Description / Distinguishing Features")
            
            cat_names = [cat.category_name for cat in st.session_state.categories]
            selected_cat_name = st.selectbox("Category", cat_names)
            
            submit_post = st.form_submit_button("Post Item")
            
            if submit_post:
                if item_name.strip():
                    # Find selected Category object
                    selected_cat = next(cat for cat in st.session_state.categories if cat.category_name == selected_cat_name)
                    
                    # Instantiate objects from your classes
                    new_item = Item(item_name, description, selected_cat)
                    today_date = datetime.date.today().strftime("%Y-%m-%d")
                    new_post = Post(f"POST-{len(st.session_state.posts)+1}", today_date, st.session_state.current_user, new_item)
                    
                    st.session_state.posts.append(new_post)
                    st.success("Item posted successfully to the feed!")
                else:
                    st.warning("Please provide an item name.")

    # --- 4. SEARCH & FILTER UI ---
    elif navigation == "Filter by Category":
        st.header("🔍 Filter Feed by Category")
        cat_names = [cat.category_name for cat in st.session_state.categories]
        filter_choice = st.selectbox("Select Category to View", cat_names)
        
        target_cat = next(cat for cat in st.session_state.categories if cat.category_name == filter_choice)
        all_items = [p.item for p in st.session_state.posts]
        filtered_items = target_cat.filter_by_category(all_items)
        
        if not filtered_items:
            st.info(f"No items found under category: {filter_choice}")
        else:
            for item in filtered_items:
                st.markdown(f"- **{item.item_name}** (`{item.tracking.current_status}`) - {item.description}")

    # --- 5. UPDATE TRACKING STATUS UI ---
    elif navigation == "Update Tracking Status":
        st.header("⚙️ Update Item Status")
        if not st.session_state.posts:
            st.info("No items available to update.")
        else:
            post_options = {f"{i+1}. {p.item.item_name} ({p.item.tracking.current_status})": i for i, p in enumerate(st.session_state.posts)}
            selected_option = st.selectbox("Select Item to Update", list(post_options.keys()))
            
            post_idx = post_options[selected_option]
            target_post = st.session_state.posts[post_idx]
            
            new_status = st.radio("Select New Status", ["Lost", "Pending Claim", "Claimed"])
            
            if st.button("Apply Status Update"):
                target_post.item.tracking.update_tracking_status(new_status)
                st.success(f"Status updated to **{new_status}**!")
                st.rerun()
