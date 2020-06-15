import os,json
import requests
from flask import Flask,render_template,request,session,logging,url_for,redirect,flash,jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session,sessionmaker
from passlib.hash import sha256_crypt

from dotenv import load_dotenv
load_dotenv()

myapi= "qJy8eMVXru55W5wKSvsNw"
 
engine = create_engine(os.getenv("DATABASE_URL"))
db= scoped_session(sessionmaker(bind=engine))
 

if not os.getenv("DATABASE_URL"):
	raise RuntimeError("DATABASE_URL is not set")


app=Flask(__name__)

@app.route("/")
def home():
	return render_template("home.html")

#register form
@app.route("/register",methods=["GET","POST"])
def register():
	if request.method == "POST":
		
		username = request.form.get("username")
		# Ensure username was submitted
		if not request.form.get("username"):
			return render_template("error.html", message="You must provide your username")

		# Query database for username
		check_user = db.execute("SELECT * FROM useraccount WHERE username = :username",
						  {"username":request.form.get("username")}).fetchone()

		# Check if username already exist
		if check_user:
			return render_template("error.html", message=" The username you provided already exist")

		password = request.form.get("password")
		confirm = request.form.get("confirm")
		secure_password= sha256_crypt.encrypt(str(password))

		if password == confirm:
			db.execute("INSERT INTO useraccount(username,password) VALUES (:username,:password)",
											{"username": username,"password":secure_password})
			db.commit()
			flash("You are now registered and can login")
			return redirect(url_for("login"))
		else:
			flash("Password does not match !","danger")
			return render_template("register.html")

	return render_template("register.html")

#login
@app.route("/login",methods =["GET","POST"])
def login():
	if request.method =="POST":
		username= request.form.get("username")
		#password= sha256_crypt.encrypt( request.form.get("password") )
		password= request.form.get("password")

		# Ensure username was submitted
		if not request.form.get("username"):
			return render_template("error.html", message=" You must provide username")

		# Ensure password was submitted
		elif not request.form.get("password"):
			return render_template("error.html", message="You must provide password")

		# print(username)
		# print(password)
		data = db.execute("SELECT * FROM useraccount WHERE username=:username",{"username":username}).fetchone()
		# print(session)
 
		if data is None:
			flash("You are not registered,Please register and try again.","danger")
			return render_template("login.html")

		else:
			# print("Name and hash password")
			# print(data[1])
			# print(data[2])
			if sha256_crypt.verify(password,data[2]):

				session["loggedin_userid"]=data[0]
				session["username"]=data[1]
				session['logged_in'] = True
				# print(session)
				flash("You are now login","success")
				return redirect(url_for('bookLists'))

			else:
				flash("Incorrect password!")

	return render_template("login.html")
 
#display list of book
@app.route("/bookLists")
def bookLists():
	#Listing  all available books
	books = db.execute("SELECT * FROM books").fetchall()
	return render_template("bookLists.html", books=books)

#information about the book
@app.route("/bookDetails/<id>", methods=['GET','POST'])
def bookDetails(id):
	book = db.execute("SELECT * FROM books WHERE id = '"+id+"'").fetchone()
	#by accessing api key from goodreads website
	query = requests.get("https://www.goodreads.com/book/review_counts.json",
				params={"key":myapi, "isbns":book.isbn})

	response = query.json()
	# print(response[0])
	sBook=response["books"][0]
	ratings_count = sBook["ratings_count"]
	average_rating = sBook["average_rating"]
	# reviews = db.execute("SELECT * FROM reviews WHERE book_id = :book_id", {"book_id": book.id}).fetchall()
	# users = []

	return render_template("bookDetails.html",book=book,ratings_count=ratings_count,average_rating=average_rating)

# search
@app.route("/search", methods=["POST"])
def search():
	searchText = request.form.get("searchText").lower();
	searchBy = request.form.get("searchby")
	results = []
	
	if searchBy == 'isbn':
		results = db.execute("SELECT * FROM books WHERE lower(isbn) LIKE '%"+searchText+"%'").fetchall()
	elif searchBy == 'title':
		results = db.execute("SELECT * FROM books WHERE lower(title) LIKE '%"+searchText+"%'").fetchall()
	elif searchBy == 'author':
		results = db.execute("SELECT * FROM books WHERE lower(author) LIKE '%"+searchText+"%'").fetchall()

	return render_template("bookLists.html", books=results,searchBy=searchBy,searchText=searchText)

#logout
@app.route("/logout")
def logout():
	session.clear()
	flash("You are now logged out","success")
	return redirect(url_for('login'))

#submitting bookreview
@app.route("/submit_bookreview/<book_id>", methods=["POST"])
def submit_bookreview(book_id):
	current_user=session["loggedin_userid"]
	 
	# book_id=request.form.get('book_id')
	comment=request.form.get('comment')
	rating=request.form.get('rating')

	row = db.execute("SELECT * FROM user_reviews WHERE user_id = :user_id AND book_id = :book_id",
					{"user_id": current_user,
					 "book_id": book_id})
	 #making sure no multiple reviews for one user_id
	if row.rowcount == 1:
			flash('You already submitted a review for this book', 'warning')
			return redirect("/bookDetails/" + book_id)

	db.execute("INSERT INTO user_reviews(user_id,book_id,comment,rating) VALUES(:user_id,:book_id,:comment,:rating)",
		{"user_id":current_user, "book_id":book_id, "comment":comment, "rating":rating})
		 
	db.commit()
	flash("Your review has been submitted","info")
	
	return redirect("/bookDetails/"+book_id)

#making our own API	
@app.route("/api/<isbn>", methods=['GET'])
def api_call(isbn):
	book =  db.execute("SELECT * FROM books WHERE isbn = :isbn",{"isbn":isbn}).fetchone()
	print(book)
	print(isbn)
	if book is None:
		return jsonify(
			{
				"error_code": 404,
				"error_message": "Not Found"
			}
		), 404
	reviews = db.execute("SELECT * FROM user_reviews WHERE book_id = :book_id", {"book_id": book.id}).fetchall()
	count = len(reviews)
	rating=0
	for review in reviews:
		rating += review.rating
	if count:
		average_rating = rating / count
	else:
		average_rating = 0
	result = {
		"title": book.title,
		"author":book.author,
		"year": book.year,
		"isbn": book.isbn,
		"review_count":count,
		"average_score":average_rating
		 
		}
	return jsonify(result)

	 
if __name__=="__main__":
	app.secret_key="thisismysecretkey"
	app.run(debug=True)

