import csv
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, session, make_response
import joblib
import mysql.connector
from datetime import datetime

# ---------------- Flask App Setup ----------------
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for session management

# Load ML model once
model = joblib.load('Crop_Recommendation_System.pkl')

# Admin email
ADMIN_EMAIL = "admin@gmail.com"

# ---------------- MySQL Database Connection ----------------
def get_db_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",            # your MySQL username
        password="Mrunali@123",  # your MySQL password
        database="crop_system"     # database name you created
    )
    return conn

# ------------------------- Routes -------------------------

@app.route('/')
def home():
    return render_template('Home_1.html')

@app.route('/iconhome')
def iconhome():
    return render_template('iconhome.html')

@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')

@app.route('/service')
def service():
    return render_template('service.html')

@app.route('/language')
def language():
    return render_template('language.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        if not name or not email or not message:
            return "Please fill all the fields."

        print(f"Received contact from {name} - {email}: {message}")
        return render_template('succes.html')

    return render_template('contact.html')

# ------------------------- Login/Register -------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([name, email, password, confirm_password]):
            return render_template('Login.html', register_error="All fields are required.")
        if password != confirm_password:
            return render_template('Login.html', register_error="Passwords do not match.")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            cursor.close()
            conn.close()
            return render_template('Login.html', register_error="Email already registered.")

        # Insert new user
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                       (name, email, password))
        conn.commit()
        cursor.close()
        conn.close()

        return render_template('Login.html', register_success="Registration successful! Please login.")
    return render_template('Login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            return render_template('Login.html', error="Invalid email or password.")

        session['user_email'] = email
        return redirect(url_for('dashboard'))
    return render_template('Login.html')


@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('home'))

# ------------------------- Dashboard & Prediction -------------------------

@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session['user_email'])


@app.route('/predict')
def predict():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('Index.html')


@app.route('/form', methods=['POST'])
def form():
    try:
        if 'user_email' not in session:
            return redirect(url_for('login'))

        Nitrogen = float(request.form['Nitrogen'])
        Phosphorus = float(request.form['Phosphorus'])
        Potassium = float(request.form['Potassium'])
        Temperature = float(request.form['Temperature'])
        Humidity = float(request.form['Humidity'])
        ph = float(request.form['ph'])
        Rainfall = float(request.form['Rainfall'])

        if not (0 < ph < 14 and 0 <= Temperature <= 100 and 0 <= Humidity <= 100):
            return "Invalid values entered. Please recheck."

        prediction = model.predict([[Nitrogen, Phosphorus, Potassium, Temperature, Humidity, ph, Rainfall]])[0]

        # Save prediction data in MySQL
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions (email, nitrogen, phosphorus, potassium, temperature, humidity, ph, rainfall, crop, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (session['user_email'], Nitrogen, Phosphorus, Potassium, Temperature, Humidity, ph, Rainfall, prediction, datetime.now()))
        conn.commit()
        cursor.close()
        conn.close()

        return render_template('prediction.html', prediction=prediction)

    except Exception as e:
        return f"An error occurred: {e}"

# ------------------------- Admin History & Controls -------------------------

@app.route('/history')
def history():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session['user_email']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Only admin can view all data
    if user_email != ADMIN_EMAIL:
        cursor.close()
        conn.close()
        return "Access Denied: Only Admin can view all data."

    cursor.execute("SELECT * FROM predictions ORDER BY timestamp DESC")
    data = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin_history.html', data=data)


@app.route('/download_csv')
def download_csv():
    if 'user_email' not in session or session['user_email'] != ADMIN_EMAIL:
        return "Access Denied"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM predictions ORDER BY timestamp DESC")
    data = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert to CSV
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["ID", "User Email", "Nitrogen", "Phosphorus", "Potassium", "Temperature",
                 "Humidity", "pH", "Rainfall", "Predicted Crop", "Timestamp"])
    cw.writerows(data)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=predictions.csv"
    output.headers["Content-type"] = "text/csv"
    return output


@app.route('/delete/<int:entry_id>')
def delete_entry(entry_id):
    if 'user_email' not in session or session['user_email'] != ADMIN_EMAIL:
        return "Access Denied"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM predictions WHERE id = %s", (entry_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('history'))


@app.route('/delete_all')
def delete_all():
    if 'user_email' not in session or session['user_email'] != ADMIN_EMAIL:
        return "Access Denied"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM predictions")
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('history'))


# ------------------------- Run App -------------------------
if __name__ == '__main__':
    app.run(debug=True)
