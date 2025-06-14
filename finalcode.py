import mysql.connector
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import os
import hashlib# import hashlib for secure hashing
import random

# ===== MySQL Connection =====
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "socialmediadb"
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def username_exists(username):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", (username,))
    exists = cursor.fetchone()[0] > 0
    db.close()
    return exists

# ===== Account =====
class Account:
    def __init__(self, username, password, role, password_hash=None):
        self.username = username
        self.role = role
        self.__password_hash = password_hash if password_hash else self.hash_password(password)
        # alias for backward compatibility( i did this so i dont have to change every code block in the program that uses self._password_hash before making it private)
        self._password_hash = self.__password_hash

        self.session_expiry = None

    def login(self, password):
        # now compares against the private field
        if self.hash_password(password) == self.__password_hash:
            self.session_expiry = datetime.now() + timedelta(minutes=10)
            return True
        return False

    def logout(self):
        self.session_expiry = None

    def is_session_active(self):
        return self.session_expiry is not None and datetime.now() < self.session_expiry

    def hash_password(self, password):
        # Secure, persistent hash using sha256!
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    # if you ever need to expose the hash
    def get_password_hash(self):
        return self.__password_hash


# ===== User, RegisteredUser, ProfessionalUser =====
class User:
    def __init__(self, user_id, name, bio, profile_pic, account, **kwargs):
        # — truly protected internals
        self._followers = []
        self._following = []
        # — aliases for backward compatibility
        self.followers = self._followers
        self.following = self._following

        # public attributes
        self.user_id = user_id
        self.name = name
        self.bio = bio
        self.profile_pic = profile_pic
        self.account= account
        self.posts = []
        self.comments = []
        self.likes = []

    def follow(self, username, users):
        target = next((u for u in users if u.account.username == username), None)
        if target and username != self.account.username:
            if username not in self.following:
                self.following.append(username)
                target.followers.append(self.account.username)
                print(f"You are now following {username}.")
            else:
                print("You already follow this user.")
        else:
            print("User not found.")

    def unfollow(self, username, users):
        target = next((u for u in users if u.account.username == username), None)
        if target and username in self.following:
            self.following.remove(username)
            target.followers.remove(self.account.username)
            print(f"You unfollowed {username}.")
        else:
            print("User not found or not in following list.")

    def like_post(self, post):
        for i in getattr(post, "interactions", []):
            if isinstance(i, Like) and i.user == self:
                print("You already liked this post.")
                return
        post.interactions.append(Like(self, post))
        print("You liked the post.")

    def comment_on_post(self, post, content):
        post.interactions.append(Comment(self, post, content))
        print("Comment added.")


class RegisteredUser(User):
    def __init__(self, user_id, name, bio, profile_pic, account, **kwargs):
        super().__init__(user_id, name, bio, profile_pic, account, **kwargs)

class ProfessionalUser(RegisteredUser):
    def __init__(self, user_id, name, bio, profile_pic, account, **kwargs):
        super().__init__(user_id, name, bio, profile_pic, account, **kwargs)
        self.product_posts = []
        self.job_posts = []

# ===== Media =====
class Media:
    def __init__(self, media_id, media_type, url):
        self.media_id = media_id
        self.media_type = media_type
        self.url = url

    def __str__(self):
        return f"{self.media_type}: {self.url}"

# ===== Post and Subclasses =====
class Post(ABC):
    _id_counter = 1

    def __init__(self, caption, media, author, post_id=None, timestamp=None, **kwargs):
        self.post_id = post_id if post_id else Post._id_counter
        if post_id is None:
            Post._id_counter += 1

        self.caption   = caption
        self.media     = media
        self.author    = author
        self.timestamp = timestamp if timestamp else datetime.now()

        # — truly protected interactions list
        self._interactions = []
        # — alias for backward compatibility
        self.interactions = self._interactions

    @abstractmethod
    def display(self):
        pass

class NormalPost(Post):
    def __init__(self, caption, media, author, post_id=None, timestamp=None, **kwargs):
        super().__init__(caption, media, author, post_id=post_id, timestamp=timestamp, **kwargs)

    def display(self):
        return f"{self.author.name} posted: {self.caption} [{self.media}]"

class ProductPost(Post):
    def __init__(self, product_name, price, description, media, author, post_id=None, timestamp=None, **kwargs):
        caption = f"Buy: {product_name}"
        super().__init__(caption, media, author, post_id=post_id, timestamp=timestamp, **kwargs)
        self.product_name = product_name
        self.price = price
        self.description = description

    def display(self):
        return f"Product: {self.product_name} (${self.price}) by {self.author.name} | {self.description} | Media: {self.media}"

class JobPost(Post):
    def __init__(self, job_title, company, requirements, media, author, post_id=None, timestamp=None, **kwargs):
        caption = f"Job: {job_title}"
        super().__init__(caption, media, author, post_id=post_id, timestamp=timestamp, **kwargs)
        self.job_title = job_title
        self.company = company
        self.requirements = requirements

    def display(self):
        return f"Job: {self.job_title} at {self.company} by {self.author.name} | Req: {self.requirements} | Media: {self.media}"

# ===== Interaction and Subclasses =====
class Interaction(ABC):
    def __init__(self, user, post, timestamp=None, **kwargs):
        self.user = user
        self.post = post
        self.timestamp = timestamp if timestamp else datetime.now()

    @abstractmethod
    def get_summary(self):
        pass

class InteractionMixin:
    def get_actor(self):
        return self.user.name

    def get_timestamp(self):
        return self.timestamp

class Comment(Interaction, InteractionMixin):
    def __init__(self, user, post, content, timestamp=None, **kwargs):
        super().__init__(user, post, timestamp, **kwargs)
        self.content = content

    def get_summary(self):
        return f"{self.user.name} commented: {self.content}"

class Like(Interaction, InteractionMixin):
    def __init__(self, user, post, timestamp=None, **kwargs):
        super().__init__(user, post, timestamp, **kwargs)

    def get_summary(self):
        return f"{self.user.name} liked this post."

# ===== Message =====
class Message:
    def __init__(self, sender, receiver, content, timestamp=None):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.timestamp = timestamp if timestamp else datetime.now()

# ===== Marketplace =====
class Marketplace:
    def __init__(self):
        self.products = []

    def add_product(self, product):
        self.products.append(product)

    def search_by_keyword(self, keyword):
        return [p for p in self.products if keyword.lower() in p.product_name.lower()]

    def filter_by_price(self, min_price, max_price):
        return [p for p in self.products if min_price <= p.price <= max_price]

# --- USERS ---
def clear_users_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM users")
    db.commit()
    db.close()

def save_users_db(users):
    db = get_db_connection()
    cursor = db.cursor()
    sql = """
    INSERT INTO users
      (user_id, username, password_hash, role, name, bio, profile_pic)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      password_hash = VALUES(password_hash),
      role          = VALUES(role),
      name          = VALUES(name),
      bio           = VALUES(bio),
      profile_pic   = VALUES(profile_pic)
    """
    for user in users:
        cursor.execute(sql, (
            user.user_id,
            user.account.username,
            user.account._password_hash,
            user.account.role,
            user.name,
            user.bio,
            user.profile_pic
        ))
    db.commit()
    db.close()


def load_users_db():
    users = []
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    for row in cursor.fetchall():
        acc = Account(row['username'], "dummy", row['role'], password_hash=row['password_hash'])
        if row['role'] == "professional":
            user = ProfessionalUser(row['user_id'], row['name'], row['bio'], row['profile_pic'], acc)
        else:
            user = RegisteredUser(row['user_id'], row['name'], row['bio'], row['profile_pic'], acc)
        users.append(user)
    db.close()
    return users

def save_users_file(users, filename="users.txt"):
    with open(filename, "w") as f:
        for u in users:
            f.write(f"{u.user_id}|{u.account.username}|{u.account.role}|{u.account._password_hash}|{u.name}|{u.bio}|{u.profile_pic}\n")

def load_users_file(filename="users.txt"):
    users = []
    if not os.path.exists(filename):
        return users
    with open(filename, "r") as f:
        for line in f:
            user_id, username, role, password_hash, name, bio, pic = line.strip().split("|")
            acc = Account(username, "dummy", role)
            acc._password_hash = password_hash
            if role == "professional":
                user = ProfessionalUser(int(user_id), name, bio, pic, acc)
            else:
                user = RegisteredUser(int(user_id), name, bio, pic, acc)
            users.append(user)
    return users

# --- POSTS ---
def clear_posts_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM posts")
    db.commit()
    db.close()

def save_posts_db(posts):
    db = get_db_connection()
    cursor = db.cursor()
    for post in posts:
        if isinstance(post, NormalPost):
            cursor.execute(
                "INSERT INTO posts "
                "(post_id, post_type, caption, author_username, media_id, media_type, media_url, timestamp) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    post.post_id,
                    'normal',
                    post.caption,
                    post.author.account.username,
                    post.media.media_id,
                    post.media.media_type,
                    post.media.url,
                    post.timestamp
                )
            )
        elif isinstance(post, ProductPost):
            cursor.execute(
                "INSERT INTO posts "
                "(post_id, post_type, caption, author_username, media_id, media_type, media_url, "
                "product_name, price, description, timestamp) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    post.post_id,
                    'product',
                    post.caption,
                    post.author.account.username,
                    post.media.media_id,
                    post.media.media_type,
                    post.media.url,
                    post.product_name,
                    post.price,
                    post.description,
                    post.timestamp
                )
            )
        elif isinstance(post, JobPost):
            cursor.execute(
                "INSERT INTO posts "
                "(post_id, post_type, caption, author_username, media_id, media_type, media_url, "
                "job_title, company, requirements, timestamp) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    post.post_id,
                    'job',
                    post.caption,
                    post.author.account.username,
                    post.media.media_id,
                    post.media.media_type,
                    post.media.url,
                    post.job_title,
                    post.company,
                    post.requirements,
                    post.timestamp
                )
            )
    db.commit()
    db.close()

def load_posts_db(users):
    posts = []
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM posts")
    for row in cursor.fetchall():
        author = next((u for u in users if u.account.username == row['author_username']), None)
        media = Media(row['media_id'], row['media_type'], row['media_url'])
        if row['post_type'] == 'normal':
            post = NormalPost(row['caption'], media, author, post_id=row['post_id'], timestamp=row['timestamp'])
        elif row['post_type'] == 'product':
            post = ProductPost(row['product_name'], row['price'], row['description'], media, author, post_id=row['post_id'], timestamp=row['timestamp'])
        elif row['post_type'] == 'job':
            post = JobPost(row['job_title'], row['company'], row['requirements'], media, author, post_id=row['post_id'], timestamp=row['timestamp'])
        posts.append(post)
    db.close()
    return posts

def save_posts_file(posts, filename="posts.txt"):
    with open(filename, "w") as f:
        for p in posts:
            if isinstance(p, NormalPost):
                f.write(f"NormalPost|{p.post_id}|{p.caption}|{p.author.account.username}|{p.media.media_id},{p.media.media_type},{p.media.url}|{p.timestamp}\n")
            elif isinstance(p, ProductPost):
                f.write(f"ProductPost|{p.post_id}|{p.caption}|{p.author.account.username}|{p.media.media_id},{p.media.media_type},{p.media.url}|{p.product_name},{p.price},{p.description}|{p.timestamp}\n")
            elif isinstance(p, JobPost):
                f.write(f"JobPost|{p.post_id}|{p.caption}|{p.author.account.username}|{p.media.media_id},{p.media.media_type},{p.media.url}|{p.job_title},{p.company},{p.requirements}|{p.timestamp}\n")

def load_posts_file(users, filename="posts.txt"):
    posts = []
    if not os.path.exists(filename):
        return posts
    with open(filename, "r") as f:
        for line in f:
            parts = line.strip().split("|")
            ptype = parts[0]
            if ptype == "NormalPost":
                _, pid, caption, author_username, media_str, ts = parts
                media_id, media_type, media_url = media_str.split(",")
                media = Media(media_id, media_type, media_url)
                author = next((u for u in users if u.account.username == author_username), None)
                post = NormalPost(caption, media, author, post_id=int(pid), timestamp=ts)
                posts.append(post)
            elif ptype == "ProductPost":
                _, pid, caption, author_username, media_str, info, ts = parts
                media_id, media_type, media_url = media_str.split(",")
                product_name, price, description = info.split(",", 2)
                media = Media(media_id, media_type, media_url)
                author = next((u for u in users if u.account.username == author_username), None)
                post = ProductPost(product_name, float(price), description, media, author, post_id=int(pid), timestamp=ts)
                posts.append(post)
            elif ptype == "JobPost":
                _, pid, caption, author_username, media_str, info, ts = parts
                media_id, media_type, media_url = media_str.split(",")
                job_title, company, requirements = info.split(",", 2)
                media = Media(media_id, media_type, media_url)
                author = next((u for u in users if u.account.username == author_username), None)
                post = JobPost(job_title, company, requirements, media, author, post_id=int(pid), timestamp=ts)
                posts.append(post)
    return posts

# --- FOLLOWERS ---
def save_followers_file(users, filename="followers.txt"):
    with open(filename, "w") as f:
        for user in users:
            for followed_username in user.following:
                f.write(f"{user.account.username}|{followed_username}\n")

def load_followers_file(users, filename="followers.txt"):
    if not os.path.exists(filename):
        return
    for user in users:
        user.followers.clear()
        user.following.clear()
    with open(filename, "r") as f:
        for line in f:
            follower_username, followed_username = line.strip().split("|")
            follower = next((u for u in users if u.account.username == follower_username), None)
            followed = next((u for u in users if u.account.username == followed_username), None)
            if follower and followed:
                if followed_username not in follower.following:
                    follower.following.append(followed_username)
                if follower_username not in followed.followers:
                    followed.followers.append(follower_username)

def clear_followers_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM followers")
    db.commit()
    db.close()

def save_followers_db(users):
    db = get_db_connection()
    cursor = db.cursor()
    for user in users:
        for followed_username in user.following:
            cursor.execute(
                "INSERT INTO followers (follower_username, followed_username) VALUES (%s, %s)",
                (user.account.username, followed_username)
            )
    db.commit()
    db.close()

def load_followers_db(users):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM followers")
    data = cursor.fetchall()
    for user in users:
        user.followers.clear()
        user.following.clear()
    for row in data:
        follower = next((u for u in users if u.account.username == row['follower_username']), None)
        followed = next((u for u in users if u.account.username == row['followed_username']), None)
        if follower and followed:
            if row['followed_username'] not in follower.following:
                follower.following.append(row['followed_username'])
            if row['follower_username'] not in followed.followers:
                followed.followers.append(row['follower_username'])
    db.close()

# --- LIKES ---
def clear_likes_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM likes")
    db.commit()
    db.close()

def save_likes_db(posts):
    db = get_db_connection()
    cursor = db.cursor()
    for post in posts:
        for like in [i for i in getattr(post, "interactions", []) if isinstance(i, Like)]:
            cursor.execute(
                "INSERT INTO likes (post_id, username, timestamp) VALUES (%s, %s, %s)",
                (post.post_id, like.user.account.username, like.timestamp)
            )
    db.commit()
    db.close()

def load_likes_db(posts, users):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM likes")
    for post in posts:
        post.interactions = [i for i in getattr(post, "interactions", []) if not isinstance(i, Like)]
    for row in cursor.fetchall():
        post = next((p for p in posts if p.post_id == row['post_id']), None)
        user = next((u for u in users if u.account.username == row['username']), None)
        if post and user:
            like = Like(user, post, timestamp=row['timestamp'])
            post.interactions.append(like)
    db.close()

# --- COMMENTS ---
def clear_comments_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM comments")
    db.commit()
    db.close()

def save_comments_db(posts):
    db = get_db_connection()
    cursor = db.cursor()
    for post in posts:
        for comment in [i for i in getattr(post, "interactions", []) if isinstance(i, Comment)]:
            cursor.execute(
                "INSERT INTO comments (post_id, username, content, timestamp) VALUES (%s, %s, %s, %s)",
                (post.post_id, comment.user.account.username, comment.content, comment.timestamp)
            )
    db.commit()
    db.close()

def load_comments_db(posts, users):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM comments")
    for post in posts:
        post.interactions = [i for i in getattr(post, "interactions", []) if not isinstance(i, Comment)]
    for row in cursor.fetchall():
        post = next((p for p in posts if p.post_id == row['post_id']), None)
        user = next((u for u in users if u.account.username == row['username']), None)
        if post and user:
            comment = Comment(user, post, row['content'], timestamp=row['timestamp'])
            post.interactions.append(comment)
    db.close()

# --- MESSAGES ---
def clear_messages_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM messages")
    db.commit()
    db.close()

def save_messages_db(messages):
    db = get_db_connection()
    cursor = db.cursor()
    for m in messages:
        cursor.execute(
            "INSERT INTO messages (sender_username, receiver_username, content, timestamp) VALUES (%s, %s, %s, %s)",
            (m.sender.account.username, m.receiver.account.username, m.content, m.timestamp)
        )
    db.commit()
    db.close()

def load_messages_db(users):
    messages = []
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM messages")
    for row in cursor.fetchall():
        sender = next((u for u in users if u.account.username == row['sender_username']), None)
        receiver = next((u for u in users if u.account.username == row['receiver_username']), None)
        if sender and receiver:
            msg = Message(sender, receiver, row['content'], timestamp=row['timestamp'])
            messages.append(msg)
    db.close()
    return messages

# --- MARKETPLACE ---
def clear_marketplace_db():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM marketplace")
    db.commit()
    db.close()

def save_marketplace_db(marketplace):
    db = get_db_connection()
    cursor = db.cursor()
    for product in marketplace.products:
        cursor.execute(
            "INSERT INTO marketplace (post_id) VALUES (%s)",
            (product.post_id,)
        )
    db.commit()
    db.close()

def load_marketplace_db(posts):
    marketplace = Marketplace()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Optional: load existing post_ids from marketplace table
    cursor.execute("SELECT post_id FROM marketplace")
    existing_ids = set(row['post_id'] for row in cursor.fetchall())

    for p in posts:
        if isinstance(p, ProductPost):
            # Add to in-memory marketplace
            marketplace.add_product(p)
            # If not saved before, insert it now
            if p.post_id not in existing_ids:
                cursor2 = db.cursor()
                cursor2.execute("INSERT INTO marketplace (post_id) VALUES (%s)", (p.post_id,))
                db.commit()

    db.close()
    return marketplace

# --- GLUE LOGIC ---
def save_all(users, posts, messages, marketplace):
    clear_users_db()
    clear_posts_db()
    clear_followers_db()
    clear_likes_db()
    clear_comments_db()
    clear_messages_db()
    clear_marketplace_db()
    save_users_db(users)
    save_posts_db(posts)
    save_followers_db(users)
    save_likes_db(posts)
    save_comments_db(posts)
    save_messages_db(messages)
    save_marketplace_db(marketplace)
    save_users_file(users)
    save_posts_file(posts)
    save_followers_file(users)

def load_all():
    users = load_users_db()
    posts = load_posts_db(users)
    messages = load_messages_db(users)
    marketplace = load_marketplace_db(posts)
    load_followers_db(users)
    load_likes_db(posts, users)
    load_comments_db(posts, users)
    if not users:
        users = load_users_file()
    if not posts:
        posts = load_posts_file(users)
    load_followers_file(users)
    return users, posts, messages, marketplace

def find_user(users, identifier):
    identifier = identifier.strip().lower()
    # 1) exact username match
    for u in users:
        if u.account.username.lower() == identifier:
            return u
    # 2) exact display‐name match
    for u in users:
        if u.name.lower() == identifier:
            return u
    return None


def find_post(posts, post_id):
    return next((p for p in posts if int(p.post_id) == int(post_id)), None)

def print_user_menu(user):
    if isinstance(user, ProfessionalUser):
        print("\n--- {} (Professional) ---".format(user.name))
        print("1. Create Normal Post (business use)")
        print("2. Marketplace (View/Search/Add Products)")
        print("3. Job Board (View/Search/Add Jobs)")
        print("4. Follow User")
        print("5. Unfollow User")
        print("6. Like Post")
        print("7. Comment on Post")
        print("8. Show My Posts")
        print("9. Send Message")
        print("10. View Inbox")
        print("11. Logout")
    else:
        print("\n--- {} (Registered) ---".format(user.name))
        print("1. Create Normal Post")
        print("2. Marketplace (View/Search/Add Products)")
        print("3. Job Board (View/Search/Apply)")
        print("4. Follow User")
        print("5. Unfollow User")
        print("6. Like Post")
        print("7. Comment on Post")
        print("8. Show My Posts")
        print("9. Send Message")
        print("10. View Inbox")
        print("11. Logout")

def show_marketplace(current_user, users, posts, messages, marketplace):
    print("\n--- Marketplace: All Products ---")
    if not marketplace.products:
        print("No products yet.")
    else:
        products_list = marketplace.products[:]
        random.shuffle(products_list)
        for product in products_list:
            print(f"ID: {product.post_id} | {product.product_name} | ${product.price} | Seller: {product.author.name}")

    keyword = input("Search products (leave blank to skip): ").strip()
    if keyword:
        matches = marketplace.search_by_keyword(keyword)
        if not matches:
            print("No products matched your search.")
        else:
            random.shuffle(matches)
            for product in matches:
                print(f"ID: {product.post_id} | {product.product_name} | ${product.price} | Seller: {product.author.name}")

    # Add product prompt as before...
    while True:
        add_choice = input("Add a product? (y/n): ").strip().lower()
        if add_choice in ["y", "n"]:
            break
        print("Please enter 'y' for yes or 'n' for no.")
    if add_choice == "y":
        pname = input("Product name: ")
        while True:
            price_input = input("Price (numbers only, no $): ")
            try:
                price = float(price_input)
                break
            except ValueError:
                print("Please enter a valid number, without $ or text.")
        desc = input("Description: ")
        media = Media(1, "image", input("Media URL: "))
        post = ProductPost(pname, price, desc, media, current_user)
        posts.append(post)
        marketplace.add_product(post)
        save_all(users, posts, messages, marketplace)
        print("Product added!")


def show_job_board(current_user, users, posts, messages, marketplace):
    print("\n--- Job Board: All Jobs ---")
    job_posts = [p for p in posts if isinstance(p, JobPost)]
    if not job_posts:
        print("No job postings yet.")
    else:
        jobs_list = job_posts[:]
        random.shuffle(jobs_list)
        for job in jobs_list:
            print(f"ID: {job.post_id} | {job.job_title} at {job.company} | Poster: {job.author.name}")

    keyword = input("Search jobs (leave blank to skip): ").strip()
    if keyword:
        matches = [job for job in job_posts if keyword.lower() in job.job_title.lower()]
        if not matches:
            print("No jobs matched your search.")
        else:
            random.shuffle(matches)
            for job in matches:
                print(f"ID: {job.post_id} | {job.job_title} at {job.company} | Poster: {job.author.name}")

    if isinstance(current_user, ProfessionalUser):
        while True:
            add_job = input("Add a job? (y/n): ").strip().lower()
            if add_job in ["y", "n"]:
                break
            print("Please enter 'y' for yes or 'n' for no.")
        if add_job == "y":
            jtitle = input("Job title: ")
            company = input("Company: ")
            req = input("Requirements: ")
            media = Media(1, "image", input("Media URL: "))
            post = JobPost(jtitle, company, req, media, current_user)
            posts.append(post)
            save_all(users, posts, messages, marketplace)
            print("Job post added!")
    else:
        while True:
            apply_job = input("Apply to a job? (y/n): ").strip().lower()
            if apply_job in ["y", "n"]:
                break
            print("Please enter 'y' for yes or 'n' for no.")
        if apply_job == "y":
            pid = int(input("Enter Job Post ID to apply: "))
            job = next((j for j in job_posts if j.post_id == pid), None)
            if job:
                print("Application sent! (Feature can be expanded)")
            else:
                print("Invalid Job Post ID.")

def show_posts_menu(current_user, users, posts, messages, marketplace):
    print(f"\n--- {current_user.name}'s Posts ---")
    my_posts = [p for p in posts if p.author == current_user]
    if not my_posts:
        print("You haven't posted anything yet.")
        return

    for p in my_posts:
        print(f"ID: {p.post_id} | {p.caption} | Posted on: {p.timestamp.strftime('%Y-%m-%d %H:%M')}")
        for interaction in p.interactions:
            print("  -", interaction.get_summary())

    while True:
        delete_choice = input("Do you want to delete a post? (y/n): ").strip().lower()
        if delete_choice in ["y", "n"]:
            break
        print("Please enter 'y' or 'n'.")

    if delete_choice == "y":
        while True:
            try:
                pid = int(input("Enter Post ID to delete: "))
                post_to_delete = next((p for p in my_posts if p.post_id == pid), None)
                if post_to_delete:
                    posts.remove(post_to_delete)
                    if isinstance(post_to_delete, ProductPost) and post_to_delete in marketplace.products:
                        marketplace.products.remove(post_to_delete)
                    print("Post deleted.")
                    save_all(users, posts, messages, marketplace)
                    break
                else:
                    print("You don't have a post with that ID.")
            except ValueError:
                print("Invalid input. Please enter a valid post ID.")

def show_main_logo():
    width = 32
    print("=" * width)
    print("Blex".center(width))
    print("Where Business Meets Flex".center(width))
    print("=" * width)

def main():
    users, posts, messages, marketplace = load_all()
    if posts:
        Post._id_counter = max(int(p.post_id) for p in posts) + 1
    else:
        Post._id_counter = 1
    current_user = None

    while True:
        show_main_logo()

        if not current_user:
            print("\n1. Register\n2. Login\n3. Exit")
            choice = input("Choice: ").strip()
            if choice == "1":
                name = input("Name: ")
                while True:
                    username = input("Username: ")
                    if username_exists(username):
                        print("Username already exists. Please choose another username.")
                    else:
                        break
                password = input("Password: ")
                role = input("Role (regular/professional): ").strip().lower()
                while role not in ["regular", "professional"]:
                    print("Invalid role. Please enter 'regular' or 'professional'.")
                    role = input("Role (regular/professional): ").strip().lower()
                acc = Account(username, password, role)
                user = ProfessionalUser(len(users)+1, name, "", "", acc) if role == "professional" else RegisteredUser(len(users)+1, name, "", "", acc)
                users.append(user)
                save_all(users, posts, messages, marketplace)
                print("Registered. Now login.")
            elif choice == "2":
                username = input("Username: ")
                password = input("Password: ")
                user = find_user(users, username)
                if user and user.account.login(password):
                    print(f"Logged in as {user.name}")
                    if not user.bio:
                        user.bio = input("Bio: ")
                    if not user.profile_pic:
                        user.profile_pic = input("Profile Pic URL: ")
                    save_all(users, posts, messages, marketplace)
                    current_user = user
                else:
                    print("Invalid login. Try again.")
            elif choice == "3":
                print("Bye!")
                break
        else:
            print_user_menu(current_user)
            choice = input("Choice: ").strip()
            try:
                # Both user types: Create Normal Post
                if choice == "1":
                    cap = input("Caption: ")
                    media = Media(1, "image", input("Media URL: "))
                    post = NormalPost(cap, media, current_user)
                    posts.append(post)
                    save_all(users, posts, messages, marketplace)

                elif isinstance(current_user, ProfessionalUser):
                    if choice == "2":  # Marketplace
                        print("\n--- Marketplace: All Products ---")
                        if not marketplace.products:
                            print("No products yet.")
                        else:
                            products_list = marketplace.products[:]
                            random.shuffle(products_list)
                            for product in products_list:
                                print(f"ID: {product.post_id} | {product.product_name} | ${product.price} | Seller: {product.author.name}")

                        keyword = input("Search products (leave blank to skip): ").strip()
                        if keyword:
                            matches = marketplace.search_by_keyword(keyword)
                            if not matches:
                                print("No products matched your search.")
                            else:
                                random.shuffle(matches)
                                for product in matches:
                                    print(f"ID: {product.post_id} | {product.product_name} | ${product.price} | Seller: {product.author.name}")

                        while True:
                            add_choice = input("Add a product? (y/n): ").strip().lower()
                            if add_choice in ["y", "n"]:
                                break
                            print("Please enter 'y' for yes or 'n' for no.")
                        if add_choice == "y":
                            pname = input("Product name: ")
                            while True:
                                price_input = input("Price (numbers only, no $): ")
                                try:
                                    price = float(price_input)
                                    break
                                except ValueError:
                                    print("Please enter a valid number, without $ or text.")
                            desc = input("Description: ")
                            media = Media(1, "image", input("Media URL: "))
                            post = ProductPost(pname, price, desc, media, current_user)
                            posts.append(post)
                            marketplace.add_product(post)
                            save_all(users, posts, messages, marketplace)
                            print("Product added!")

                    elif choice == "3":  # Job Board
                        print("\n--- Job Board: All Jobs ---")
                        job_posts = [p for p in posts if isinstance(p, JobPost)]
                        if not job_posts:
                            print("No job postings yet.")
                        else:
                            jobs_list = job_posts[:]
                            random.shuffle(jobs_list)
                            for job in jobs_list:
                                print(f"ID: {job.post_id} | {job.job_title} at {job.company} | Poster: {job.author.name}")

                        keyword = input("Search jobs (leave blank to skip): ").strip()
                        if keyword:
                            matches = [job for job in job_posts if keyword.lower() in job.job_title.lower()]
                            if not matches:
                                print("No jobs matched your search.")
                            else:
                                random.shuffle(matches)
                                for job in matches:
                                    print(f"ID: {job.post_id} | {job.job_title} at {job.company} | Poster: {job.author.name}")

                        while True:
                            add_job = input("Add a job? (y/n): ").strip().lower()
                            if add_job in ["y", "n"]:
                                break
                            print("Please enter 'y' for yes or 'n' for no.")
                        if add_job == "y":
                            jtitle = input("Job title: ")
                            company = input("Company: ")
                            req = input("Requirements: ")
                            media = Media(1, "image", input("Media URL: "))
                            post = JobPost(jtitle, company, req, media, current_user)
                            posts.append(post)
                            save_all(users, posts, messages, marketplace)
                            print("Job post added!")

                    elif choice == "4":
                        uname = input("Follow who: ")
                        current_user.follow(uname, users)
                        save_all(users, posts, messages, marketplace)
                    elif choice == "5":
                        uname = input("Unfollow who: ")
                        current_user.unfollow(uname, users)
                        save_all(users, posts, messages, marketplace)
                    elif choice == "6":
                        uname = input("Enter username of post author: ")
                        user = find_user(users, uname)
                        if user:
                            user_posts = [p for p in posts if p.author == user]
                            if not user_posts:
                                print("This user has no posts.")
                            else:
                                user_posts_list = user_posts[:]
                                random.shuffle(user_posts_list)
                                print("Posts by", uname)
                                for p in user_posts_list:
                                    print(f"ID: {p.post_id} | {p.caption}")
                                pid = int(input("Enter Post ID to like: "))
                                post = find_post(user_posts, pid)
                                if post:
                                    current_user.like_post(post)
                                    save_all(users, posts, messages, marketplace)
                                else:
                                    print("Invalid Post ID.")
                        else:
                            print("User not found.")
                    elif choice == "7":
                        uname = input("Enter username of post author: ")
                        user = find_user(users, uname)
                        if user:
                            user_posts = [p for p in posts if p.author == user]
                            if not user_posts:
                                print("This user has no posts.")
                            else:
                                user_posts_list = user_posts[:]
                                random.shuffle(user_posts_list)
                                print("Posts by", uname)
                                for p in user_posts_list:
                                    print(f"ID: {p.post_id} | {p.caption}")
                                pid = int(input("Enter Post ID to comment on: "))
                                post = find_post(user_posts, pid)
                                if post:
                                    content = input("Your comment: ")
                                    current_user.comment_on_post(post, content)
                                    save_all(users, posts, messages, marketplace)
                                else:
                                    print("Invalid Post ID.")
                        else:
                            print("User not found.")
                    elif choice == "8":
                        # If you want to randomize "Show My Posts" and "Show Posts by Others" menus here, update that logic as above.
                        show_posts_menu(current_user, users, posts, messages, marketplace)
                    elif choice == "9":
                        receiver_name = input("Send to username: ")
                        receiver = find_user(users, receiver_name)
                        if receiver:
                            content = input("Message: ")
                            msg = Message(current_user, receiver, content)
                            messages.append(msg)
                            save_all(users, posts, messages, marketplace)
                            print("Message sent.")
                        else:
                            print("User not found.")
                    elif choice == "10":
                        inbox = [m for m in messages if m.receiver == current_user]
                        if not inbox:
                            print("No messages.")
                        else:
                            print("Your inbox:")
                            for m in inbox:
                                print(f"From {m.sender.name} ({m.sender.account.username}) at {m.timestamp.strftime('%Y-%m-%d %H:%M')}:\n  {m.content}\n")
                    elif choice == "11":
                        current_user.account.logout()
                        save_all(users, posts, messages, marketplace)
                        current_user = None
                        print("Logged out.")

                else:  # RegisteredUser
                    if choice == "2":  # Marketplace
                        print("\n--- Marketplace: All Products ---")
                        if not marketplace.products:
                            print("No products yet.")
                        else:
                            products_list = marketplace.products[:]
                            random.shuffle(products_list)
                            for product in products_list:
                                print(f"ID: {product.post_id} | {product.product_name} | ${product.price} | Seller: {product.author.name}")

                        keyword = input("Search products (leave blank to skip): ").strip()
                        if keyword:
                            matches = marketplace.search_by_keyword(keyword)
                            if not matches:
                                print("No products matched your search.")
                            else:
                                random.shuffle(matches)
                                for product in matches:
                                    print(f"ID: {product.post_id} | {product.product_name} | ${product.price} | Seller: {product.author.name}")

                        while True:
                            add_choice = input("Add a product? (y/n): ").strip().lower()
                            if add_choice in ["y", "n"]:
                                break
                            print("Please enter 'y' for yes or 'n' for no.")
                        if add_choice == "y":
                            pname = input("Product name: ")
                            while True:
                                price_input = input("Price (numbers only, no $): ")
                                try:
                                    price = float(price_input)
                                    break
                                except ValueError:
                                    print("Please enter a valid number, without $ or text.")
                            desc = input("Description: ")
                            media = Media(1, "image", input("Media URL: "))
                            post = ProductPost(pname, price, desc, media, current_user)
                            posts.append(post)
                            marketplace.add_product(post)
                            save_all(users, posts, messages, marketplace)
                            print("Product added!")

                    elif choice == "3":  # Job Board
                        print("\n--- Job Board: All Jobs ---")
                        job_posts = [p for p in posts if isinstance(p, JobPost)]
                        if not job_posts:
                            print("No job postings yet.")
                        else:
                            jobs_list = job_posts[:]
                            random.shuffle(jobs_list)
                            for job in jobs_list:
                                print(f"ID: {job.post_id} | {job.job_title} at {job.company} | Poster: {job.author.name}")

                        keyword = input("Search jobs (leave blank to skip): ").strip()
                        if keyword:
                            matches = [job for job in job_posts if keyword.lower() in job.job_title.lower()]
                            if not matches:
                                print("No jobs matched your search.")
                            else:
                                random.shuffle(matches)
                                for job in matches:
                                    print(f"ID: {job.post_id} | {job.job_title} at {job.company} | Poster: {job.author.name}")

                        while True:
                            apply_job = input("Apply to a job? (y/n): ").strip().lower()
                            if apply_job in ["y", "n"]:
                                break
                            print("Please enter 'y' for yes or 'n' for no.")
                        if apply_job == "y":
                            pid = int(input("Enter Job Post ID to apply: "))
                            job = next((j for j in job_posts if j.post_id == pid), None)
                            if job:
                                print("Application sent! (Feature can be expanded)")
                            else:
                                print("Invalid Job Post ID.")

                    elif choice == "4":
                        uname = input("Follow who: ")
                        current_user.follow(uname, users)
                        save_all(users, posts, messages, marketplace)
                    elif choice == "5":
                        uname = input("Unfollow who: ")
                        current_user.unfollow(uname, users)
                        save_all(users, posts, messages, marketplace)
                    elif choice == "6":
                        uname = input("Enter username of post author: ")
                        user = find_user(users, uname)
                        if user:
                            user_posts = [p for p in posts if p.author == user]
                            if not user_posts:
                                print("This user has no posts.")
                            else:
                                user_posts_list = user_posts[:]
                                random.shuffle(user_posts_list)
                                print("Posts by", uname)
                                for p in user_posts_list:
                                    print(f"ID: {p.post_id} | {p.caption}")
                                pid = int(input("Enter Post ID to like: "))
                                post = find_post(user_posts, pid)
                                if post:
                                    current_user.like_post(post)
                                    save_all(users, posts, messages, marketplace)
                                else:
                                    print("Invalid Post ID.")
                        else:
                            print("User not found.")
                    elif choice == "7":
                        uname = input("Enter username of post author: ")
                        user = find_user(users, uname)
                        if user:
                            user_posts = [p for p in posts if p.author == user]
                            if not user_posts:
                                print("This user has no posts.")
                            else:
                                user_posts_list = user_posts[:]
                                random.shuffle(user_posts_list)
                                print("Posts by", uname)
                                for p in user_posts_list:
                                    print(f"ID: {p.post_id} | {p.caption}")
                                pid = int(input("Enter Post ID to comment on: "))
                                post = find_post(user_posts, pid)
                                if post:
                                    content = input("Your comment: ")
                                    current_user.comment_on_post(post, content)
                                    save_all(users, posts, messages, marketplace)
                                else:
                                    print("Invalid Post ID.")
                        else:
                            print("User not found.")
                    elif choice == "8":
                        show_posts_menu(current_user, users, posts, messages, marketplace)
                    elif choice == "9":
                        receiver_name = input("Send to username: ")
                        receiver = find_user(users, receiver_name)
                        if receiver:
                            content = input("Message: ")
                            msg = Message(current_user, receiver, content)
                            messages.append(msg)
                            save_all(users, posts, messages, marketplace)
                            print("Message sent.")
                        else:
                            print("User not found.")
                    elif choice == "10":
                        inbox = [m for m in messages if m.receiver == current_user]
                        if not inbox:
                            print("No messages.")
                        else:
                            print("Your inbox:")
                            for m in inbox:
                                print(f"From {m.sender.name} ({m.sender.account.username}) at {m.timestamp.strftime('%Y-%m-%d %H:%M')}:\n  {m.content}\n")
                    elif choice == "11":
                        current_user.account.logout()
                        save_all(users, posts, messages, marketplace)
                        current_user = None
                        print("Logged out.")
            except Exception as e:
                print("Error:", e)

if __name__ == "__main__":
    main()
