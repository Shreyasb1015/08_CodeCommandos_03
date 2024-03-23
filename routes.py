from flask import Flask,render_template,url_for,flash,redirect,request,abort,jsonify
import os
import secrets
from PIL import Image
from forms import RegistrationForm,LoginForm,UpdateAccountForm,JobPostForm
from flask_sqlalchemy import SQLAlchemy
from models import User,JobPost,AnalyzeResume
from __init__ import app, db,bcrypt     #type:ignore
from flask_login import login_user,current_user,logout_user,login_required
import google.generativeai as genai
import io

import base64
import pdfminer
from pdfminer.high_level import extract_text



chat_history = []
os.environ['GOOGLE_API_KEY'] = " AIzaSyAKy0DBzkk0lyMtaZym9KilBjq4SjTOg_4"
genai.configure(api_key = os.environ['GOOGLE_API_KEY'])
model = genai.GenerativeModel('gemini-pro')

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')




def save_picture(form_picture):
    random_hex=secrets.token_hex(8)
    _, f_ext=os.path.splitext(form_picture.filename)
    picture_fn=random_hex+f_ext
    picture_path=os.path.join(app.root_path,'static/profile_pics',picture_fn)
    output_size=(125,125)
    i=Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn

@app.route("/account",methods=["GET","POST"])
@login_required
def account():
    form=UpdateAccountForm()
    if form.validate_on_submit():
            if form.picture.data:
                picture_file=save_picture(form.picture.data)  
                current_user.image_file=picture_file
            current_user.username=form.username.data
            current_user.email=form.email.data
            db.session.commit()
            flash('Your account has been updated!','success')
            return redirect(url_for('account'))
    elif request.method=='GET':
        form.username.data=current_user.username 
        form.email.data=current_user.email
    image_file=url_for('static',filename='profile_pics/' + current_user.image_file) 
    return render_template('account.html',image_file=image_file,form=form)




@app.route('/layout')
def layout():
    return render_template('layout.html')   

@app.route('/register',methods=['GET','POST'])
def register():
    #if current_user.is_authenticated:
     #   return redirect(url_for('home'))
    form=RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email address is already registered!', 'danger')
            return render_template('register.html',form=form)
        hashed_password=bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user=User(username=form.username.data,email=form.email.data,password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Account created for {form.username.data}!','success')
        return redirect(url_for('login'))    
    else:
        print('Form is not valid.')
        print(form.errors)
        return render_template('register.html',form=form)


@app.route('/chatbot')
def chatbot():
    return render_template('chat.html')


@app.route("/get", methods=["GET", "POST"])
def chat():
    msg = request.form["msg"]
    if model.generate_content(f"Is {msg} query related to carrier guidance or tips regarding for carrier.Please only state ans in yes or no?").text=="Yes":
        input_msg = msg
        response = get_chat_response(input_msg)
        response=response.replace("**","").split("*")
        chat_history.append({"user": input_msg, "gemini": response})
        return jsonify({"response": response})
    else:
        return jsonify({"response":'Query is not related to carrier guidance.I am Carrier guidance bot,So I can only ans queries regarding it'})


def get_chat_response(text):
    response = model.generate_content(text).text
    return response


@app.route('/login',methods=['GET','POST'] )
def login():
    #if current_user.is_authenticated:
     #   return redirect(url_for('home'))
    form=LoginForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.email.data).first()
        
        if user and bcrypt.check_password_hash(user.password,form.password.data):
            login_user(user,remember=form.remember.data)
            return redirect(url_for('home'))
        else:
             flash('Login Unsuccessful.Please check email and password','danger')
    return render_template('login.html',form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/post_job', methods=['GET', 'POST'])
@login_required
def post_job():
    form = JobPostForm()
    if form.validate_on_submit():
        job_post = JobPost(title=form.title.data, description=form.description.data, author=current_user)
        db.session.add(job_post)
        db.session.commit()
        flash('Your job post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('post_job.html', title='Post Job', form=form)

@app.route('/apply_job/<int:job_id>', methods=['GET','POST'])
@login_required
def apply_job(job_id):
    job_post = JobPost.query.get_or_404(job_id)
    if job_post.author == current_user:
        flash('You cannot apply to your own job post!', 'warning')
        return redirect(url_for('home'))
    
    return redirect(url_for('analyze', job_id=job_id))


@app.route('/analyze/<int:job_id>', methods=['GET', 'POST'])
def analyze(job_id):
    job_post = JobPost.query.get_or_404(job_id)
    print(job_post)
    
    input_text=job_post.description
    author_name = User.query.filter_by(id=job_post.author_id).first().username if User.query.filter_by(id=job_post.author_id).first() else 'Unknown'
    if request.method=='POST':
        if 'resume' not in request.files:
                flash('No file part', 'error')
                return redirect('/')
            
        file = request.files['resume']
        if file.filename == '':
                flash('No selected file', 'error')
                return redirect('/')
            
        resume_text = process_pdf(file)
        print(resume_text)
        input_prompt = """
        'As an expert resume analyzer, your role is to meticulously evaluate the provided resume in comparison to the given job description. Your analysis should focus on determining the degree of alignment between the candidate's profile and the requirements of the role.

        Please provide a comprehensive assessment highlighting the strengths and weaknesses of the applicant's profile with respect to the specified job requirements. Assign a suitability score ranging from 0 to 1, where 0 indicates a poor match and 1 indicates a perfect match.

        Your evaluation should consider key factors such as skills, experience, qualifications, and achievements mentioned in the resume, and how well they correspond to the job description's expectations.

        Scored should be printedin this manner:
        Predicted score of suitablity: {score}

        Use your expertise to accurately gauge the candidate's suitability for the position based on the information provided in the resume.'
    """
        response=model.generate_content(f' Work as per {input_prompt}.{input_text} is job description and {resume_text} is teh conetnts of resume .Please generate score.').text
        score_start_index = response.find("Predicted score of suitability:")
        score_obtained=0.2
        if score_start_index != -1:
            score_line = response[score_start_index:].split("\n")[0]
            score = score_line.split(":")[-1].strip()
            print("Predicted Score:", score)
            score=score.replace("**","")
            score_obtained=float(score)
        else:
            print("Predicted score not found in the response.")   
        
        resume_score = AnalyzeResume(
                username=current_user.username,
                email=current_user.email,
                author_name= author_name, 
                job_post_id=job_id,
                score=score_obtained
            )
        db.session.add(resume_score)
        db.session.commit()
        
        flash('Resume score saved successfully!', 'success')
    else:
        return render_template('analyze.html', job_post=job_post)
        
        
    return render_template('analyze.html', job_post=job_post)


def process_pdf(file):
    text = extract_text(file.stream)
    return text
    

@app.route('/all_jobs')
def all_jobs():
    job_posts = JobPost.query.all()
    return render_template('all_jobs.html', job_posts=job_posts)

@app.route('/my_jobs', methods=['GET'])
@login_required
def my_jobs():
    user_jobs = JobPost.query.filter_by(author=current_user).all()
    job_ids = [job.id for job in user_jobs]
    job_applicants = AnalyzeResume.query.filter(AnalyzeResume.job_post_id.in_(job_ids)).order_by(AnalyzeResume.score.desc()).all()
    if not job_applicants:
        message = "No applications"
        return render_template('my_jobs.html', job_post=user_jobs, message=message)
    return render_template('my_jobs.html', user_jobs=user_jobs, job_applicants=job_applicants)

@app.route('/learngenie',methods=['POST','GET'])
def learngenie():        
        return render_template('geniebot.html')


@app.route("/genieget", methods=["GET", "POST"])
def geniechat():
   if request.method == 'POST':
        msg = request.form["msg"]
            
        prompt=f""" f"Act as Resource Finder Bot, which takes user company  and suggests useful links, contents, docs, or courses to help the user crack their dream company. Be helpful and provide real links."
        
         
        """
        response = get_chat_response(prompt)
        response=response.replace("**","").split("*")
        chat_history.append({"user": msg, "gemini": response})
        return jsonify({"response": response})
    

