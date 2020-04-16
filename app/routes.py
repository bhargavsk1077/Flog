from app import app,db 
from flask import render_template,flash,redirect,url_for,request
from werkzeug.urls import url_parse
from app.forms import LoginForm,RegistrationForm,PostForm,EditProfileForm
from flask_login import current_user,login_user,logout_user,login_required
from app.models import User,Post,Message
from datetime import datetime
from app.forms import ResetPasswordRequestForm,ResetPasswordForm,DeleteAccountForm,MessageForm
from app.email import send_password_reset_email

@app.route('/')
@app.route('/index')
@login_required
def index():
    page = request.args.get('page',1,type=int)
    posts = current_user.followed_posts().paginate(
            page,app.config['POSTS_PER_PAGE'],False)
    next_url = url_for('index',page=posts.next_num)\
            if posts.has_next else None
    prev_url = url_for('index',page=posts.prev_num)\
            if posts.has_prev else None
    return render_template('index.html',title="home", posts=posts.items,next_url=next_url,prev_url=prev_url)

@app.route('/login',methods=["GET","POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc !='':
            next_page = url_for('index') 
        return redirect(next_page)
    return render_template('login.html',title='Login', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=["GET","POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username = form.username.data, email = form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Signup succesful')
        return redirect(url_for('login'))
    return render_template('register.html',form=form,title='Register')

@app.route('/new_post',methods=["GET","POST"])
@login_required 
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=current_user.username).first()
        if user is not None:
             user_id = user.id
             post = Post(body=form.content.data,user_id=user_id)
             db.session.add(post)
             db.session.commit()
             flash('Posted succesfully')
             return redirect(url_for('index'))
        flash("some error fetching user details")
        return render_template('new_post.html',form=form,title="New Post")
    return render_template('new_post.html',form=form,title="New Post")


        
@app.route('/user/<username>')
@login_required 
def user(username):
    page = request.args.get('page',1,type=int)
    user = User.query.filter_by(username = username).first_or_404()
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
            page,app.config['POSTS_PER_PAGE'],False)
    next_url = url_for('user',username=user.username,page=posts.next_num)\
            if posts.has_next else None
    prev_url = url_for('user',username=user.username,page=posts.prev_num)\
            if posts.has_prev else None
    return render_template('user.html',user = user , posts = posts.items, title=user.username,prev_url=prev_url,next_url=next_url)

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@app.route('/edit_profile',methods=["GET","POST"])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash("Profile updated succesfully")

    elif request.method=="GET":
        form.username.data=current_user.username
        form.about_me.data=current_user.about_me
    return render_template('edit_profile.html',title ="Edit Profile",form = form)

@app.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        flash("user not found")
        return redirect(url_for('index'))
    if user == current_user:
        flash("you cannot follow yourself")
        return redirect(url_for('user',username=username))
    current_user.follow(user)
    db.session.commit()
    flash("you are now following {}!".format(username))
    return redirect(url_for('user',username=username))


@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash("user not found")
        return redirect(url_for('index'))
    if user == current_user:
        flash("you cannot unfollow yourself")
        return redirect(url_for('user',username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash("you have unfollowed {}".format(username))
    return redirect(url_for('user',username=username))

@app.route('/discover')
@login_required
def explore():
    page = request.args.get('page',1,type=int)
    posts = current_user.unfollowed_posts().paginate(
            page,app.config['POSTS_PER_PAGE'],False)
    next_url = url_for('explore',page=posts.next_num)\
            if posts.has_next else None
    prev_url = url_for('explore',page=posts.prev_num)\
            if posts.has_prev else None
    return render_template('index.html',title = "Discover",posts=posts.items,prev_url=prev_url,next_url=next_url)


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

@app.route('/delete_account',methods=['GET','POST'])
@login_required
def delete_account():
    form = DeleteAccountForm()
    if form.validate_on_submit():
        if current_user.check_password(form.password.data):
            user = current_user
            #logout_user()
            user.delete_info()
            db.session.delete(user)
            db.session.commit()
            logout_user()
            flash("your account has been deleted succesfully")
            return redirect(url_for('index'))
        flash("enter correct password")
        return redirect(url_for('delete_account'))
    return render_template('delete_account.html',form=form,title="Delete Account")

@app.route('/delete_post/<post_id>')
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted succesfully")
    return redirect(url_for('user',username=current_user.username))

@app.route('/send_message/<recipient>', methods=['GET', 'POST'])
@login_required
def send_message(recipient):
    user = User.query.filter_by(username=recipient).first_or_404()
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(author=current_user, recipient=user,
                      body=form.message.data)
        db.session.add(msg)
        db.session.commit()
        flash('Your message has been sent.')
        return redirect(url_for('user', username=recipient))
    return render_template('send_message.html', title='Send Message',
                           form=form, recipient=recipient)

@app.route('/messages')
@login_required
def messages():
    current_user.last_message_read_time = datetime.utcnow()
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    messages = current_user.messages_received.order_by(
        Message.timestamp.desc()).paginate(
            page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('main.messages', page=messages.next_num) \
        if messages.has_next else None
    prev_url = url_for('main.messages', page=messages.prev_num) \
        if messages.has_prev else None
    return render_template('messages.html', messages=messages.items,
                           next_url=next_url, prev_url=prev_url)
