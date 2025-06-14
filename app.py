# app.py
import os, random
from datetime import datetime
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from werkzeug.utils import secure_filename

from finalcode import (
    load_all, save_all, username_exists, find_user,
    Account, RegisteredUser, ProfessionalUser,
    Message, NormalPost, ProductPost,
    JobPost, Media, Like, Comment
)

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'

# Load data once
users, posts, messages, marketplace = load_all()
for p in posts:
    if isinstance(p.author, str):
        real = find_user(users, p.author)
        if real: p.author = real

# Context processors for templates
@app.context_processor
def inject_helpers():
    return {
        'current_year': datetime.now().year,
        'find_user': find_user,
        'users': users
    }

def current_user():
    return find_user(users, session.get('username',''))


# — Registration, Login, Logout —

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        name,u,p,r = (
            request.form['name'],
            request.form['username'],
            request.form['password'],
            request.form['role']
        )
        if username_exists(u):
            flash('Username taken.', 'danger')
        else:
            acc = Account(u,p,r)
            cls = ProfessionalUser if r=='professional' else RegisteredUser
            user = cls(len(users)+1, name, '', '', acc)
            users.append(user)
            save_all(users, posts, messages, marketplace)
            flash('Registered – please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u,p = request.form['username'], request.form['password']
        user = find_user(users, u)
        if user and user.account.login(p):
            session['username'] = u
            flash('Logged in.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

# — Dashboard — 

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = current_user()
    regular = [p for p in posts if isinstance(p, NormalPost)]
    for p in regular:
        p.likes = sum(isinstance(i, Like) for i in p.interactions)
        p.comments = [
            {'author': i.user.name, 'text': i.content}
            for i in p.interactions if isinstance(i, Comment)
        ]
    return render_template('dashboard.html', user=user, posts=regular)

# — Create Post — 

@app.route('/create-post', methods=['GET','POST'])
def create_post():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method=='POST':
        cap = request.form['caption']
        f   = request.files.get('media')
        if f and f.filename:
            up = os.path.join(app.static_folder,'uploads')
            os.makedirs(up, exist_ok=True)
            fn = secure_filename(f.filename)
            f.save(os.path.join(up,fn))
            murl = url_for('static', filename=f'uploads/{fn}')
            mtype = 'image' if f.mimetype.startswith('image') else 'video'
            media = Media(None, mtype, murl)
        else:
            media = Media(None,'','')
        author = current_user()
        nid = max([p.post_id for p in posts]+[0]) + 1
        new = NormalPost(cap, media, author, post_id=nid)
        posts.append(new)
        save_all(users, posts, messages, marketplace)
        flash('Post created.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_post.html', user=current_user())

# — Like & Comment Routes — 

@app.route('/post/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    post = next((p for p in posts if p.post_id==post_id), None)
    if post:
        user = current_user()
        user.like_post(post)          # uses User.like_post(...) :contentReference[oaicite:2]{index=2}
        save_all(users, posts, messages, marketplace)
    return redirect(url_for('dashboard'))

@app.route('/post/<int:post_id>/comment', methods=['POST'])
def comment_post(post_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    post = next((p for p in posts if p.post_id==post_id), None)
    if post:
        text = request.form['comment']
        user = current_user()
        user.comment_on_post(post, text)  # uses User.comment_on_post(...) :contentReference[oaicite:3]{index=3}
        save_all(users, posts, messages, marketplace)
    return redirect(url_for('dashboard'))

@app.route('/marketplace')
def marketplace_list():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = current_user()
    q    = request.args.get('q','').lower()
    items = marketplace.products[:]
    if q:
        items = [i for i in items if q in i.product_name.lower() or q in i.description.lower()]
    random.shuffle(items)
    return render_template('marketplace.html', user=user, items=items, search_query=q)

@app.route('/create-market-item', methods=['GET','POST'])
def create_market_item():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method=='POST':
        name, desc, price = (
            request.form['name'],
            request.form['description'],
            float(request.form['price'])
        )
        f = request.files.get('image')
        if f and f.filename:
            up = os.path.join(app.static_folder, 'uploads/marketplace')
            os.makedirs(up, exist_ok=True)
            fn = secure_filename(f.filename)
            f.save(os.path.join(up, fn))
            url = url_for('static', filename=f'uploads/marketplace/{fn}')
            media = Media(None, 'image', url)
        else:
            media = Media(None, '', '')
        author = current_user()
        nid = max([p.post_id for p in posts]+[0]) + 1
        item = ProductPost(name, price, desc, media, author, post_id=nid)
        posts.append(item)
        marketplace.add_product(item)
        save_all(users, posts, messages, marketplace)
        flash('Listing added.', 'success')
        return redirect(url_for('marketplace_list'))
    return render_template('create_marketplace.html', user=current_user())

@app.route('/jobs')
def jobs_list():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = current_user()
    q = request.args.get('q','').lower()
    job_posts = [p for p in posts if isinstance(p, JobPost)]
    if q:
        job_posts = [j for j in job_posts if q in j.job_title.lower() or q in j.company.lower()]
    random.shuffle(job_posts)
    return render_template('jobs.html', user=user, jobs=job_posts, search_query=q)

@app.route('/create-job', methods=['GET','POST'])
def create_job():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = current_user()
    if user.account.role!='professional':
        flash('Only professionals may post jobs.', 'danger')
        return redirect(url_for('jobs_list'))
    if request.method=='POST':
        title, comp, reqs = (
            request.form['title'],
            request.form['company'],
            request.form['requirements']
        )
        f = request.files.get('media')
        if f and f.filename:
            up = os.path.join(app.static_folder, 'uploads/jobs')
            os.makedirs(up, exist_ok=True)
            fn = secure_filename(f.filename)
            f.save(os.path.join(up, fn))
            url = url_for('static', filename=f'uploads/jobs/{fn}')
            media = Media(None, 'image', url)
        else:
            media = Media(None, '', '')
        nid = max([p.post_id for p in posts]+[0]) + 1
        job = JobPost(title, comp, reqs, media, user, post_id=nid)
        posts.append(job)
        save_all(users, posts, messages, marketplace)
        flash('Job posted.', 'success')
        return redirect(url_for('jobs_list'))
    return render_template('create_job.html', user=user)

@app.route('/inbox')
def inbox():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = current_user()
    inbox_msgs = [m for m in messages if m.receiver==user]
    return render_template('inbox.html', user=user, messages=inbox_msgs)

@app.route('/messages/send', methods=['GET','POST'])
def send_message():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = current_user()
    others = [u.account.username for u in users if u.account.username!=user.account.username]
    if request.method=='POST':
        to = request.form['to_username']
        txt = request.form['content']
        rec = find_user(users, to)
        if rec:
            msg = Message(user, rec, txt)
            messages.append(msg)
            save_all(users, posts, messages, marketplace)
            flash('Message sent.', 'success')
            return redirect(url_for('inbox'))
        flash('Recipient not found.', 'danger')
    return render_template('send_message.html', user=user, users=others)

@app.route('/user/<username>')
def profile(username):
    if 'username' not in session:
        return redirect(url_for('login'))
    current = current_user()
    prof = find_user(users, username)
    if not prof:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))
    is_following = username in current.following
    return render_template('profile.html', current=current, profile=prof, is_following=is_following)

@app.route('/user/<username>/follow', methods=['POST'])
def follow(username):
    if 'username' not in session:
        return redirect(url_for('login'))
    user = current_user()
    user.follow(username, users)
    save_all(users, posts, messages, marketplace)
    return redirect(url_for('profile', username=username))

@app.route('/user/<username>/unfollow', methods=['POST'])
def unfollow(username):
    if 'username' not in session:
        return redirect(url_for('login'))
    user = current_user()
    user.unfollow(username, users)
    save_all(users, posts, messages, marketplace)
    return redirect(url_for('profile', username=username))

@app.route('/search-users')
def search_users():
    if 'username' not in session:
        return redirect(url_for('login'))
    current = current_user()
    q = request.args.get('q','').strip()
    if q:
        matched = [u for u in users if q.lower() in u.name.lower()]
    else:
        matched = users
    # exclude self
    matched = [u for u in matched if u.account.username != current.account.username]
    return render_template(
        'search_users.html',
        user=current,
        matched=matched,
        query=q
    )


if __name__ == '__main__':
    app.run(debug=True)
