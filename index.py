from flask import Flask, request, render_template, redirect, url_for, jsonify
import psycopg2
import logging
import jwt
import hashlib
from flask import make_response
import datetime 

app = Flask(__name__)

SECRET_KEY = "lgedv2024"

DB_CONFIG = {
    "dbname": "user_db",
    "user": "postgres",
    "password": "lgedv2024",
    "host": "localhost",
    "port": 5432
}



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")

    username = request.form['username']
    password = request.form['password']
    
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user:
        stored_password = user[2]  # giả sử password ở cột thứ 3
        if stored_password == hashlib.md5(password.encode()).hexdigest():
            token = jwt.encode({
                "username": username,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=18)
            }, SECRET_KEY, algorithm="HS256")

            response = jsonify({"success": True, "redirect": "/"})
            response.set_cookie("jwt", token)
            return response
        else:
            return jsonify({"success": False, "message": "Invalid password"}), 401
    else:
        return jsonify({"success": False, "message": "User not found"}), 404


@app.route('/register', methods=['GET', 'POST'])
def register(): 
    if request.method == 'GET':
        return render_template("register.html")

    username = request.form['username']
    password = request.form['password']
    name     = request.form['name']

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user:
        return jsonify({"success": False, "message": "User already exists"}), 409
    else:
        hash_password = hashlib.md5(password.encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, password, name) VALUES (%s, %s, %s)", (username, hash_password, name))
        conn.commit()
        return jsonify({"success": True, "redirect": "/login"})


@app.route('/user', methods=['GET'])
def get_user():
    token = request.cookies.get("jwt")
    if not token:
        return jsonify({"success": False, "message": "Token is missing"}), 401

    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = decoded.get("username") 

        if not username:
            return render_template("user.html", message="Invalid token"), 401

        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()

        try:
            cur.execute("SELECT id, username, name FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if user:
                user_info = {
                    "id": user[0],
                    "username": user[1],
                    "name": user[2]
                }
                return render_template("user.html", user=user_info)
            else:
                return render_template("user.html", message="User not found")
        except Exception as e:
            logging.error(f"Error querying user: {e}")
            return render_template("user.html", message="Error occurred")
        finally:
            cur.close()
            conn.close()
    except jwt.ExpiredSignatureError:
        return render_template("login.html", message="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        return render_template("login.html", message="Invalid token. Please login again.")
    except Exception as e:
        logging.error(f"Error decoding token or connecting to database: {e}")
        return render_template("user.html", message="Unexpected error occurred")

@app.route('/create_docs', methods=['GET', 'POST'])
def handle_docs():
    token = request.cookies.get("jwt") 
    if not token:
        return jsonify({"success": False, "message": "Token is missing"}), 401
    
    try:
        user = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = user.get("username")
        
        if request.method == 'GET':
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            cursor.execute("SELECT id, title, content, created_at FROM docs WHERE username = %s ORDER BY created_at DESC", (username,))
            docs = cursor.fetchall()

            result = [
                {"id": row[0], "title": row[1], "content": row[2], "created_at": row[3].isoformat()}
                for row in docs
            ]
            return render_template("list_docs.html", docs=result)

        elif request.method == 'POST':
            title = request.form['title']
            content = request.form['content']
            
            if not title or not content:
                return jsonify({"success": False, "message": "Title and content are required"}), 400
            
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            cursor.execute("INSERT INTO docs (title, content, username) VALUES (%s, %s, %s)", (title, content, username))
            conn.commit()

            # Fetch and display the updated list of documents
            cursor.execute("SELECT id, title, content, created_at FROM docs WHERE username = %s ORDER BY created_at DESC", (username,))
            docs = cursor.fetchall()

            result = [
                {"id": row[0], "title": row[1], "content": row[2], "created_at": row[3].isoformat()}
                for row in docs
            ]

            return render_template("list_docs.html", docs=result, message="Document added successfully")

    except jwt.ExpiredSignatureError:
        return render_template("login.html", message="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        return render_template("login.html", message="Invalid token. Please login again.")
    except Exception as e:
        logging.error(f"Error in /list_docs: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route('/update_doc/<int:doc_id>', methods=['GET', 'POST'])
def update_doc(doc_id):
    token = request.cookies.get("jwt") 
    if not token:
        return jsonify({"success": False, "message": "Token is missing"}), 401
    
    try:
        user = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = user.get("username")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        if request.method == 'POST':
            new_title = request.form['title']
            new_content = request.form['content']

            cursor.execute("SELECT title, content, username FROM docs WHERE id = %s", (doc_id,))
            doc = cursor.fetchone()

            if doc:
                # Verify if the document belongs to the user
                if doc[2] == username:
                    # Update the document
                    cursor.execute("""
                        UPDATE docs 
                        SET title = %s, content = %s
                        WHERE id = %s
                    """, (new_title, new_content, doc_id))
                    conn.commit()
                    return redirect(url_for('view_docs'))
                else:
                    return jsonify({"success": False, "message": "You are not authorized to update this document"}), 403
            else:
                return jsonify({"success": False, "message": "Document not found"}), 404
        
        else:
            cursor.execute("SELECT title, content,username FROM docs WHERE id = %s", (doc_id,))
            doc = cursor.fetchone()
            
            if doc and doc[2] == username:
                return render_template('update_doc.html', doc=doc)
            else:
                return jsonify({"success": False, "message": "Authentication valid"}), 401


    except Exception as e:
        logging.error(f"Error in /update_doc: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
@app.route('/view_docs', methods=['GET', 'POST'])
def view_docs():
    token = request.cookies.get("jwt")  # Get JWT token from cookies
    if not token:
        return jsonify({"success": False, "message": "Token is missing"}), 401
    
    try:
        user = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = user.get("username")
        
        if request.method == 'GET':
            return render_template("view_docs.html", docs=None)

        elif request.method == 'POST':
            title = request.form['title']
            if not title:
                return render_template("view_docs.html", docs=None, message="Title is required")
            
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, title, content, created_at,username FROM docs WHERE username = %s AND title = '{title}' ORDER BY created_at DESC", (username,))
            docs = cursor.fetchall()
            
            result = [
                {"id": row[0], "title": row[1], "content": row[2], "created_at": row[3].isoformat(),"username": row[4]}
                for row in docs
            ]
            
            if not result:
                return render_template("view_docs.html", docs=None, message="No documents found")
            
            return render_template("view_docs.html", docs=result)

    except jwt.ExpiredSignatureError:
        return render_template("login.html", message="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        return render_template("login.html", message="Invalid token. Please login again.")
    except Exception as e:
        logging.error(f"Error in /view_docs: {e}")
        return render_template("view_docs.html", docs=None, message="Internal server error")

@app.route('/view_docs/<int:doc_id>', methods=['GET'])
def view_doc(doc_id):
    token = request.cookies.get("jwt") 
    if not token:
        return jsonify({"success": False, "message": "Token is missing"}), 401

    try:
        user = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = user.get("username")

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SELECT title, content, username, created_at FROM docs WHERE id = %s", (doc_id,))
        doc = cursor.fetchone()

        if not doc:
            return jsonify({"success": False, "message": "Document not found"}), 404

        if doc[2] != username:
            return jsonify({"success": False, "message": "You are not authorized to view this document"}), 403

        doc_info = {
            "id": doc_id,
            "title": doc[0],
            "content": doc[1],
            "created_at": doc[3].isoformat()
        }

        return render_template('doc.html', doc=doc_info)

    except jwt.ExpiredSignatureError:
        return jsonify({"success": False, "message": "The signature expired"}), 403    
    except jwt.InvalidTokenError:
        return jsonify({"success": False, "message": "Invalid token"}), 403    
    except Exception as e:
        logging.error(f"Error in /view_docs: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@app.route('/', methods=['GET'])
def index():
    token = request.cookies.get("jwt")  # Get JWT token from cookies
    if not token:
        return redirect(url_for('login'))
    try:
        user = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = user.get("username")
        return render_template("index.html")
    except jwt.ExpiredSignatureError:
        return redirect(url_for('login'))
    except jwt.InvalidTokenError:
        return redirect(url_for('loginn'))
    except Exception as e:
        return redirect(url_for('login'))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
