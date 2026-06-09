from flask import redirect
from urllib.parse import quote
import os
from werkzeug.utils import secure_filename
from flask import send_file
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from flask import Flask, render_template, request
import sqlite3
from datetime import datetime, timedelta



app = Flask(__name__)
app.secret_key = "climax_library_secret"
id="2kz6fb"
app.config["SESSION_PERMANENT"] = False
from flask import session

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "sushant" and password == "sk123":

            session.clear()
            session["admin"] = True

            return redirect("/")

        return "Invalid Username or Password"

    return render_template("admin_login.html")
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")
from datetime import datetime

@app.template_filter("indian_date")
def indian_date(date_string):

    if not date_string:
        return ""

    return datetime.strptime(
        str(date_string),
        "%Y-%m-%d"
    ).strftime("%d-%m-%Y")
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name")
        phone = request.form.get("phone")
        address = request.form.get("address")
        join_date = request.form.get("join_date")
        shift = request.form.get("shift")
        payment_mode = request.form.get("payment_mode")
        photo = request.files.get("photo")

        shift_map = {
            "Morning": ["Morning"],
            "Afternoon": ["Afternoon"],
            "Evening": ["Evening"],
            "Morning+Afternoon": ["Morning", "Afternoon"],
            "Afternoon+Evening": ["Afternoon", "Evening"],
            "Morning+Evening": ["Morning", "Evening"],
            "Full Day": ["Morning", "Afternoon", "Evening"]
        }

        fee_map = {
            "Morning": 300,
            "Afternoon": 350,
            "Evening": 300,
            "Morning+Afternoon": 650,
            "Afternoon+Evening": 650,
            "Morning+Evening": 600,
            "Full Day": 950
        }

        if shift is None:
            return "Please select a shift"

        required_shifts = shift_map[shift]
        fee = fee_map[shift]

        conn = get_db()

        seat_no = None

        for seat in range(1, 53):

            available = True

            for shift_name in required_shifts:

                record = conn.execute("""
                    SELECT status
                    FROM seats
                    WHERE seat_no=? AND shift=?
                """, (seat, shift_name)).fetchone()

                if record is None or record["status"] != "Vacant":
                    available = False
                    break

            if available:
                seat_no = seat
                break

        if seat_no is None:
            conn.close()
            return "No seat available for selected shift combination"

        last_student = conn.execute("""
    SELECT id
    FROM students
    ORDER BY id DESC
    LIMIT 1
""").fetchone()

        if last_student:
          next_id = last_student["id"] + 1
        else: 

            next_id = 1

        roll_no = f"LIB{next_id:04d}"
        filename = f"{roll_no}_{secure_filename(photo.filename)}"

        photo.save(
           os.path.join(
             "static/photos",
             filename
    )
)

        join_date_obj = datetime.strptime(
            join_date,
            "%Y-%m-%d"
        ).date()

        expiry_date = join_date_obj + timedelta(days=30)

        conn.execute("""
            INSERT INTO students
            (
                roll_no,
                name,
                phone,
                address,
                seat_no,
                shift,
                join_date,
                expiry_date,
                status,
                fee,
                payment_status,
                photo    
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            roll_no,
            name,
            phone,
            address,
            seat_no,
            shift,
            join_date,
            str(expiry_date),
            "Active",
            fee,
            "Paid",
            filename,
        ))

        for shift_name in required_shifts:

            conn.execute("""
                UPDATE seats
                SET status='Occupied'
                WHERE seat_no=? AND shift=?
            """,
            (seat_no, shift_name))

        payment_count = conn.execute("""
            SELECT COUNT(*)
            FROM payments
        """).fetchone()[0]

        receipt_no = f"RCPT{payment_count + 1:04d}"

        payment_date = datetime.now().strftime("%Y-%m-%d")

        conn.execute("""
            INSERT INTO payments
            (
                receipt_no,
                roll_no,
                amount,
                payment_date,
                payment_mode
            )
            VALUES (?,?,?,?,?)
        """,
        (
            receipt_no,
            roll_no,
            fee,
            payment_date,
            payment_mode
        ))

        conn.commit()
        conn.close()

        return render_template(
            "success.html",
            roll_no=roll_no,
            name=name,
            seat_no=seat_no,
            shift=shift,
            join_date=join_date,
            expiry_date=expiry_date,
            fee=fee,
            receipt_no=receipt_no,
            payment_mode=payment_mode,
            payment_date=payment_date,
            photo=filename
        )

    return render_template("register.html")
# Database Connection
def get_db():
    conn = sqlite3.connect("library.db")
    conn.row_factory = sqlite3.Row
    return conn
def check_expired_students():

    conn = get_db()

    today = datetime.now().date()

    students = conn.execute("""
        SELECT *
        FROM students
        WHERE status='Active'
    """).fetchall()

    for student in students:

        expiry_date = datetime.strptime(
            student["expiry_date"],
            "%Y-%m-%d"
        ).date()

        if today > expiry_date:

            # Mark student expired
            conn.execute("""
                UPDATE students
                SET status='Expired'
                WHERE id=?
            """, (student["id"],))

            # Free all occupied shifts for that seat
            seat_no = student["seat_no"]

            shift_text = student["shift"]

            shift_map = {
                "Morning": ["Morning"],
                "Afternoon": ["Afternoon"],
                "Evening": ["Evening"],
                "Morning+Afternoon": ["Morning", "Afternoon"],
                "Afternoon+Evening": ["Afternoon", "Evening"],
                "Morning+Evening": ["Morning", "Evening"],
                "Full Day": ["Morning", "Afternoon", "Evening"]
            }

            occupied_shifts = shift_map[shift_text]

            for shift_name in occupied_shifts:

                conn.execute("""
                    UPDATE seats
                    SET status='Vacant'
                    WHERE seat_no=? AND shift=?
                """,
                (seat_no, shift_name))

    conn.commit()
    conn.close()

# Dashboard
@app.route("/")
def home():

    check_expired_students()

    conn = get_db()

    seats = conn.execute("""
        SELECT *
        FROM seats
        ORDER BY shift, seat_no
    """).fetchall()

    # Student Statistics
    total_students = conn.execute("""
        SELECT COUNT(*) FROM students
    """).fetchone()[0]

    active_students = conn.execute("""
        SELECT COUNT(*) FROM students
        WHERE status='Active'
    """).fetchone()[0]

    expired_students = conn.execute("""
        SELECT COUNT(*) FROM students
        WHERE status='Expired'
    """).fetchone()[0]

    # Seat Statistics
    occupied_seats = conn.execute("""
        SELECT COUNT(*) FROM seats
        WHERE status='Occupied'
    """).fetchone()[0]

    vacant_seats = conn.execute("""
        SELECT COUNT(*) FROM seats
        WHERE status='Vacant'
    """).fetchone()[0]

    # Shift Statistics
    morning_occupied = conn.execute("""
        SELECT COUNT(*)
        FROM seats
        WHERE shift='Morning'
        AND status='Occupied'
    """).fetchone()[0]

    afternoon_occupied = conn.execute("""
        SELECT COUNT(*)
        FROM seats
        WHERE shift='Afternoon'
        AND status='Occupied'
    """).fetchone()[0]

    evening_occupied = conn.execute("""
        SELECT COUNT(*)
        FROM seats
        WHERE shift='Evening'
        AND status='Occupied'
    """).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        seats=seats,

        total_students=total_students,
        active_students=active_students,
        expired_students=expired_students,

        occupied_seats=occupied_seats,
        vacant_seats=vacant_seats,

        morning_occupied=morning_occupied,
        afternoon_occupied=afternoon_occupied,
        evening_occupied=evening_occupied
    )
@app.route("/students")
def students():
    if not session.get("admin"):
        return redirect("/admin_login")

    search = request.args.get("search", "")

    conn = get_db()

    if search:

        student_list = conn.execute("""
            SELECT *
            FROM students
            WHERE roll_no LIKE ?
            OR name LIKE ?
            OR phone LIKE ?
            ORDER BY id ASC
        """,
        (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        )).fetchall()

    else:

        student_list = conn.execute("""
            SELECT *
            FROM students
            ORDER BY id ASC
        """).fetchall()

    conn.close()

    return render_template(
        "students.html",
        students=student_list,
        search=search
    )

# Test Route
@app.route("/test")
def test():
    return "Registration Route Working"

@app.route("/expired")
def expired_students():
    if not session.get("admin"):
      return redirect("/admin_login")

    conn = get_db()

    students = conn.execute("""
        SELECT *
        FROM students
        WHERE status='Expired'
        ORDER BY expiry_date ASC
    """).fetchall()

    conn.close()

    return render_template(
        "expired.html",
        students=students
    )
@app.route("/renew/<roll_no>", methods=["GET", "POST"])
def renew_student(roll_no):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE roll_no=?
    """, (roll_no,)).fetchone()

    if student is None:
        conn.close()
        return "Student Not Found"

    if request.method == "POST":

        payment_mode = request.form.get("payment_mode")
        shift = request.form.get("shift")

        fee_map = {
            "Morning": 300,
            "Afternoon": 350,
            "Evening": 300,
            "Morning+Afternoon": 650,
            "Afternoon+Evening": 650,
            "Morning+Evening": 600,
            "Full Day": 950
        }

        fee = fee_map[shift]

        old_expiry = datetime.strptime(
            student["expiry_date"],
            "%Y-%m-%d"
        ).date()

        today = datetime.now().date()

        if old_expiry < today:
            new_expiry = today + timedelta(days=30)
        else:
            new_expiry = old_expiry + timedelta(days=30)

        conn.execute("""
            UPDATE students
            SET expiry_date=?,
                status='Active',
                shift=?,
                fee=?
            WHERE roll_no=?
        """, (
            str(new_expiry),
            shift,
            fee,
            roll_no
        ))

        payment_count = conn.execute("""
            SELECT COUNT(*)
            FROM payments
        """).fetchone()[0]

        receipt_no = f"RCPT{payment_count + 1:04d}"

        payment_date = datetime.now().strftime("%Y-%m-%d")

        conn.execute("""
            INSERT INTO payments
            (
                receipt_no,
                roll_no,
                amount,
                payment_date,
                payment_mode
            )
            VALUES (?,?,?,?,?)
        """, (
            receipt_no,
            roll_no,
            fee,
            payment_date,
            payment_mode
        ))

        conn.commit()

        student = conn.execute("""
            SELECT *
            FROM students
            WHERE roll_no=?
        """, (roll_no,)).fetchone()

        conn.close()

        return render_template(
            "renew_success.html",
            student=student,
            old_expiry=old_expiry,
            new_expiry=new_expiry,
            fee=fee,
            receipt_no=receipt_no,
            payment_mode=payment_mode,
            payment_date=payment_date
        )

    conn.close()

    return render_template(
        "renew.html",
        student=student
    )

@app.route("/student/<roll_no>")
def student_details(roll_no):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE roll_no=?
    """, (roll_no,)).fetchone()

    conn.close()

    if student is None:
        return "Student Not Found"

    return render_template(
        "student_details.html",
        student=student
    )
@app.route("/edit/<roll_no>", methods=["GET", "POST"])
def edit_student(roll_no):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE roll_no=?
    """, (roll_no,)).fetchone()

    if student is None:
        conn.close()
        return "Student Not Found"

    if request.method == "POST":

        name = request.form.get("name")
        phone = request.form.get("phone")
        address = request.form.get("address")

        conn.execute("""
            UPDATE students
            SET
                name=?,
                phone=?,
                address=?
            WHERE roll_no=?
        """,
        (
            name,
            phone,
            address,
            roll_no
        ))

        conn.commit()
        conn.close()

        return render_template(
          "update_success.html",
           roll_no=roll_no
    )

    conn.close()

    return render_template(
        "edit_student.html",
        student=student
    )
@app.route("/delete/<roll_no>")
def delete_student(roll_no):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE roll_no=?
    """, (roll_no,)).fetchone()

    if student is None:
        conn.close()
        return "Student Not Found"

    seat_no = student["seat_no"]

    shift_map = {
        "Morning": ["Morning"],
        "Afternoon": ["Afternoon"],
        "Evening": ["Evening"],
        "Morning+Afternoon": ["Morning", "Afternoon"],
        "Afternoon+Evening": ["Afternoon", "Evening"],
        "Morning+Evening": ["Morning", "Evening"],
        "Full Day": ["Morning", "Afternoon", "Evening"]
    }

    shifts = shift_map[student["shift"]]

    for shift_name in shifts:

        conn.execute("""
            UPDATE seats
            SET status='Vacant'
            WHERE seat_no=? AND shift=?
        """,
        (seat_no, shift_name))
    conn.execute("""
    DELETE FROM payments
    WHERE roll_no=?
    """,
    (roll_no,))    
    conn.execute("""
        DELETE FROM students
        WHERE roll_no=?
    """,
    (roll_no,))

    conn.commit()
    conn.close()

    return render_template("delete_success.html")
@app.route("/payment/<roll_no>", methods=["GET", "POST"])
def payment(roll_no):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE roll_no=?
    """, (roll_no,)).fetchone()
    

    if student is None:
        conn.close()
        return "Student Not Found"

    if request.method == "POST":

        payment_mode = request.form.get("payment_mode")

        count = conn.execute("""
            SELECT COUNT(*)
            FROM payments
        """).fetchone()[0]

        receipt_no = f"RCPT{count + 1:04d}"

        payment_date = datetime.now().strftime("%Y-%m-%d")

        conn.execute("""
            INSERT INTO payments
            (
                receipt_no,
                roll_no,
                amount,
                payment_date,
                payment_mode
            )
            VALUES (?,?,?,?,?)
        """,
        (
            receipt_no,
            roll_no,
            student["fee"],
            payment_date,
            payment_mode
        ))

        conn.commit()
        conn.close()
        return render_template(
           "payment_success.html",
           receipt_no=receipt_no,
           roll_no=roll_no,
           amount=student["fee"],
           payment_mode=payment_mode,
           payment_date=payment_date
        )
        
        

    conn.close()

    return render_template(
        "payment.html",
        student=student
    )
@app.route("/payments")
def payments():

    conn = get_db()

    payment_list = conn.execute("""
        SELECT *
        FROM payments
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "payments.html",
        payments=payment_list
    )
@app.route("/receipt/<receipt_no>")
def receipt(receipt_no):

    conn = get_db()

    payment = conn.execute("""
        SELECT p.*, s.name, s.seat_no, s.shift
        FROM payments p
        JOIN students s
        ON p.roll_no = s.roll_no
        WHERE p.receipt_no = ?
    """, (receipt_no,)).fetchone()

    conn.close()

    if payment is None:
        return "Receipt Not Found"

    pdfmetrics.registerFont(
        TTFont("Algerian", "ALGER.TTF")
    )

    file_name = f"Receipt_{receipt_no}.pdf"

    c = canvas.Canvas(
        file_name,
        pagesize=(595, 842)
    )

    # Outer Border
    c.rect(20, 20, 555, 800)

    # Header (No Background)
    c.setFillColorRGB(0, 0, 0)

    c.setFont("Algerian", 28)
    c.drawCentredString(
        297,
        780,
        "CLIMAX LIBRARY"
    )

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(
        297,
        755,
        "MEMBERSHIP FEE RECEIPT"
    )

    # Header Line
    c.line(
        40,
        735,
        555,
        735
    )

    # Format Date
    payment_date = datetime.strptime(
        payment["payment_date"],
        "%Y-%m-%d"
    ).strftime("%d-%m-%Y")

    # Receipt Box
    c.rect(40, 680, 515, 40)

    c.setFont("Helvetica-Bold", 12)

    c.drawString(
        50,
        695,
        f"Receipt Number : {payment['receipt_no']}"
    )

    c.drawRightString(
        540,
        695,
        f"Date : {payment_date}"
    )

    # Student Details Section
    c.setFont("Helvetica-Bold", 14)
    c.drawString(
        40,
        640,
        "Student Details"
    )

    c.rect(
        40,
        500,
        515,
        120
    )

    c.setFont("Helvetica", 12)

    c.drawString(
        60,
        590,
        f"Roll Number : {payment['roll_no']}"
    )

    c.drawString(
        60,
        560,
        f"Student Name : {payment['name']}"
    )

    c.drawString(
        60,
        530,
        f"Seat Number : {payment['seat_no']}"
    )

    c.drawString(
        320,
        590,
        f"Shift : {payment['shift']}"
    )

    # Payment Details Section
    c.setFont("Helvetica-Bold", 14)
    c.drawString(
        40,
        460,
        "Payment Details"
    )

    c.rect(
        40,
        340,
        515,
        100
    )

    c.setFont("Helvetica", 12)

    c.drawString(
        60,
        400,
        f"Amount Paid : Rs. {payment['amount']}"
    )

    c.drawString(
        60,
        370,
        f"Payment Mode : {payment['payment_mode']}"
    )

    # Signature
    c.line(
        370,
        180,
        520,
        180
    )

    c.drawString(
        390,
        160,
        "Authorized Signature"
    )

    # Footer
    c.setFont(
        "Helvetica-Oblique",
        11
    )

    c.drawCentredString(
        297,
        90,
        "Thank you for choosing Climax Library"
    )

    c.drawCentredString(
        297,
        70,
        "This is a computer generated receipt"
    )

    c.save()

    return send_file(
        file_name,
        as_attachment=True
    )
@app.route("/whatsapp/<roll_no>")
def whatsapp_student(roll_no):

    conn = get_db()

    student = conn.execute("""
        SELECT *
        FROM students
        WHERE roll_no=?
    """, (roll_no,)).fetchone()

    conn.close()

    message = f"""
🏛️ CLIMAX LIBRARY

Dear {student['name']},

This is a friendly reminder that your library membership has expired.

📌 Roll Number : {student['roll_no']}
📌 Seat Number : {student['seat_no']}
📌 Expiry Date : {student['expiry_date']}

Kindly renew your membership to continue enjoying uninterrupted library services.

For any assistance, please contact the library office.

Thank You,
CLIMAX LIBRARY
"""

    phone = str(student["phone"]).strip()

    url = (
        f"https://api.whatsapp.com/send?"
        f"phone=91{phone}"
        f"&text={quote(message)}"
    )

    return redirect(url)
@app.route("/facilities")
def facilities():

    return render_template(
        "facilities.html"
    )
@app.route("/payment_history/<roll_no>")
def payment_history(roll_no):

    conn = get_db()

    payments = conn.execute("""
        SELECT *
        FROM payments
        WHERE roll_no=?
        ORDER BY id DESC
    """, (roll_no,)).fetchall()

    conn.close()

    return render_template(
        "payments.html",
        payments=payments,
        roll_no=roll_no
    )
if __name__ == "__main__":
    app.run(debug=False)