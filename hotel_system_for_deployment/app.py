from flask import Flask, render_template, request, redirect, url_for, flash, session
from connection import get_connection
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import math
from math import ceil
from flask import jsonify
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = os.urandom(24)
PAYMENT_UPLOAD_FOLDER = 'static/proof_of_payments'
app.config['PAYMENT_UPLOAD_FOLDER'] = PAYMENT_UPLOAD_FOLDER
ROOM_UPLOAD_FOLDER = 'static/rooms_images'
app.config['ROOM_UPLOAD_FOLDER'] = ROOM_UPLOAD_FOLDER

if not os.path.exists(PAYMENT_UPLOAD_FOLDER):
    os.makedirs(PAYMENT_UPLOAD_FOLDER)

if not os.path.exists(ROOM_UPLOAD_FOLDER):
    os.makedirs(ROOM_UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('is_admin') == 1:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            # Query to validate the user credentials
            validate = "SELECT * FROM `signup_hotel` WHERE hotel_email=%s AND hotel_password=%s"
            cursor.execute(validate, (email, password))
            result = cursor.fetchone()
            conn.close()

            if result is None:
                flash("Wrong Credentials.", "danger")
                return redirect(url_for('login'))
            else:
                # Set session variables
                session['user_id'] = result[0]  # user_id
                session['first_name'] = result[1]  # first_name
                session['last_name'] = result[2]  # last_name
                session['email'] = result[3]  # hotel_email
                session['is_admin'] = result[5]  # is_admin (6th column)

                # Debugging: Check session values
                print(f"Session: {session}")

                # Redirect admins to the admin dashboard
                if session.get('is_admin') == 1:
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('dashboard'))

    return render_template("login.html")



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if email already exists
        cursor.execute("SELECT * FROM signup_hotel WHERE hotel_email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already exists! Try another one.", "danger")
        else:
            query = "INSERT INTO signup_hotel (first_name, last_name, hotel_email, hotel_password) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (first_name, last_name, email, password))
            conn.commit()
            flash("Account created successfully! You can now log in.", "success")

        cursor.close()
        conn.close()

        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for('index'))
    
    # Default page number if not provided
    page = int(request.args.get('page', 1))

    # Search bar logic
    if request.method == 'POST':
        search_query = request.form.get('search', '')
    else:
        search_query = request.args.get('search', '')

    per_page = 10
    offset = (page - 1) * per_page

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if search_query:
        count_query = '''
            SELECT COUNT(*) AS total FROM bookings
            JOIN signup_hotel ON bookings.user_id = signup_hotel.user_id
            JOIN rooms ON bookings.room_id = rooms.room_id
            WHERE 
                signup_hotel.first_name LIKE %s OR 
                signup_hotel.last_name LIKE %s OR 
                rooms.type LIKE %s OR 
                bookings.status LIKE %s
        '''
        cursor.execute(count_query, (f'%{search_query}%',)*4)
        total = cursor.fetchone()['total']

        data_query = '''
            SELECT 
                b.booking_id,
                u.first_name,
                u.last_name,
                r.room_name,
                b.check_in,
                b.check_out,
                b.guests,
                b.num_rooms,
                b.status,
                b.proof_of_payment,
                b.total_amount,
                b.special_suggestion,
                b.extra_mattress,
                b.extra_pillow,
                b.extra_towel,
                GROUP_CONCAT(rn.room_number ORDER BY rn.room_number SEPARATOR ', ') AS room_numbers
            FROM bookings b
            JOIN signup_hotel u ON b.user_id = u.user_id
            JOIN rooms r ON b.room_id = r.room_id
            LEFT JOIN booked_room_numbers brn ON b.booking_id = brn.booking_id
            LEFT JOIN room_numbers rn ON brn.room_number_id = rn.room_number_id
            WHERE b.is_archived = 0 AND (
                u.first_name LIKE %s OR 
                u.last_name LIKE %s OR 
                r.type LIKE %s OR 
                b.status LIKE %s
            )
            GROUP BY b.booking_id
            ORDER BY b.booking_id Asc
            LIMIT %s OFFSET %s
        '''
        cursor.execute(data_query, (f'%{search_query}%',)*4 + (per_page, offset))
        bookings = cursor.fetchall()
    else:
        cursor.execute('SELECT COUNT(*) AS total FROM bookings')
        total = cursor.fetchone()['total']

        cursor.execute(''' 
            SELECT 
                b.booking_id,
                u.first_name,
                u.last_name,
                r.room_name,
                b.check_in,
                b.check_out,
                b.guests,
                b.num_rooms,
                b.status,
                b.proof_of_payment,
                b.total_amount,
                b.special_suggestion,
                b.extra_mattress,
                b.extra_pillow,
                b.extra_towel,
                GROUP_CONCAT(rn.room_number ORDER BY rn.room_number SEPARATOR ', ') AS room_numbers
            FROM bookings b
            JOIN signup_hotel u ON b.user_id = u.user_id
            JOIN rooms r ON b.room_id = r.room_id
            LEFT JOIN booked_room_numbers brn ON b.booking_id = brn.booking_id
            LEFT JOIN room_numbers rn ON brn.room_number_id = rn.room_number_id
            WHERE b.is_archived = 0
            GROUP BY b.booking_id
            ORDER BY b.booking_id Asc
            LIMIT %s OFFSET %s
        ''', (per_page, offset))


        bookings = cursor.fetchall()

    total_pages = (total + per_page - 1) // per_page

    cursor.close()
    conn.close()

    return render_template('admin/admin_dashboard.html',
                           bookings=bookings,
                           search_query=search_query,
                           page=page,
                           total_pages=total_pages)


@app.route('/rooms')
def rooms():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rooms")
    rooms = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('users/rooms.html', rooms=rooms)

@app.route("/rooms/<int:roomID>")
def room_details(roomID):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get room details
    cursor.execute("SELECT * FROM rooms WHERE room_id = %s", (roomID,))
    room = cursor.fetchone()

    # Get available room numbers
    cursor.execute("SELECT * FROM room_numbers WHERE room_id = %s AND is_available = 1", (roomID,))
    rooms_available_numbers = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("users/bookings.html", room=room, rooms_available_numbers=rooms_available_numbers)

# booking func
from flask import request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

@app.route('/book/<int:roomID>', methods=['POST'])
def book(roomID):
    if 'user_id' not in session:
        flash('Please log in to book a room.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    check_in = request.form.get('check_in')
    check_out = request.form.get('check_out')
    guests = request.form.get('guests')
    num_rooms = int(request.form.get('num_rooms'))
    room_number_id = request.form.get('room_number_id')
    special_suggestion = request.form.get('special_suggestion')

    extra_mattress = 1 if request.form.get('extra_mattress') == 'Yes' else 0
    extra_pillow = 1 if request.form.get('extra_pillow') == 'Yes' else 0
    extra_towel = 1 if request.form.get('extra_towel') == 'Yes' else 0

    proof_of_payment = request.files.get('proof_of_payment')
    proof_of_payment_filename = None

    if proof_of_payment and proof_of_payment.filename != '':
        filename = str(uuid.uuid4()) + '_' + secure_filename(proof_of_payment.filename)
        filepath = os.path.join('static/proof_of_payments', filename)
        proof_of_payment.save(filepath)
        proof_of_payment_filename = filename

    check_in_date = datetime.strptime(check_in, '%Y-%m-%d')

    if check_out:
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d')
        num_nights = (check_out_date - check_in_date).days
        if num_nights <= 0:
            flash("Check-out date must be after check-in date.", "danger")
            return redirect(url_for('rooms'))
    else:
        num_nights = 1  # Default to 1 night

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()

        # Get extra service prices
        cursor.execute("SELECT name, price FROM extra_services")
        service_prices = {row['name'].lower(): row['price'] for row in cursor.fetchall()}

        mattress_price = service_prices.get('extra mattress', 0)
        pillow_price = service_prices.get('extra pillow', 0)
        towel_price = service_prices.get('extra towel', 0)

        # Check selected room availability
        cursor.execute("""
            SELECT is_available FROM room_numbers WHERE room_number_id = %s FOR UPDATE
        """, (room_number_id,))
        room_status = cursor.fetchone()

        if not room_status or not room_status['is_available']:
            flash('Selected room is no longer available. Please choose another room.', 'danger')
            conn.rollback()
            return redirect(url_for('rooms'))

        # Get room price
        cursor.execute("SELECT price FROM rooms WHERE room_id = %s", (roomID,))
        room = cursor.fetchone()

        if not room:
            flash('Room not found.', 'danger')
            conn.rollback()
            return redirect(url_for('rooms'))

        room_price = room['price']
        room_total = room_price * num_nights * num_rooms
        extras_total = (
            extra_mattress * mattress_price +
            extra_pillow * pillow_price +
            extra_towel * towel_price
        ) * num_nights * num_rooms
        total_amount = room_total + extras_total

        # Insert booking
        cursor.execute("""
            INSERT INTO bookings (
                user_id, room_id, check_in, check_out, guests, num_rooms, 
                extra_mattress, extra_pillow, extra_towel, total_amount, 
                room_number_id, proof_of_payment, special_suggestion, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, 'Pending'
            )
        """, (
            user_id, roomID, check_in, check_out, guests, num_rooms,
            extra_mattress, extra_pillow, extra_towel, total_amount,
            room_number_id, proof_of_payment_filename, special_suggestion
        ))

        # Get booking ID
        booking_id = cursor.lastrowid

        # Insert main room into booked_room_numbers
        cursor.execute("""
            INSERT INTO booked_room_numbers (booking_id, room_number_id)
            VALUES (%s, %s)
        """, (booking_id, room_number_id))

        # Mark main room unavailable
        cursor.execute("""
            UPDATE room_numbers SET is_available = FALSE
            WHERE room_number_id = %s
        """, (room_number_id,))

        # If multiple rooms booked, find and block additional available rooms
        if num_rooms > 1:
            cursor.execute("""
                SELECT room_number_id FROM room_numbers
                WHERE room_id = %s AND is_available = TRUE AND room_number_id != %s
                LIMIT %s
            """, (roomID, room_number_id, num_rooms - 1))
            additional_rooms = cursor.fetchall()

            if len(additional_rooms) < (num_rooms - 1):
                flash("Not enough available rooms to complete your booking.", "danger")
                conn.rollback()
                return redirect(url_for('rooms'))

            for extra_room in additional_rooms:
                extra_room_id = extra_room['room_number_id']

                # Mark as unavailable
                cursor.execute("""
                    UPDATE room_numbers SET is_available = FALSE
                    WHERE room_number_id = %s
                """, (extra_room_id,))

                # Insert into booked_room_numbers
                cursor.execute("""
                    INSERT INTO booked_room_numbers (booking_id, room_number_id)
                    VALUES (%s, %s)
                """, (booking_id, extra_room_id))

        conn.commit()
        flash('Room booked successfully!', 'success')

    except Exception as e:
        conn.rollback()
        flash(f"An error occurred: {str(e)}", 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/service')
def service():
    return render_template('services.html')

@app.route('/location')
def location():
    return render_template('location.html')

@app.route('/manage_rooms')
def manage_rooms():
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for('index'))
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM rooms')
    rooms = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/manage_rooms.html', rooms=rooms)

def get_user_booking(user_id):
    if not user_id:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT rooms.room_name, bookings.check_in, bookings.check_out
        FROM bookings
        JOIN rooms ON bookings.room_id = rooms.room_id
        WHERE bookings.user_id = %s
        ORDER BY bookings.check_in DESC
        LIMIT 1
    """

    cursor.execute(query, (user_id,))
    booking = cursor.fetchone()

    conn.close()
    cursor.close()
    return booking

# user dashboard
@app.route('/dashboard')
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT first_name, last_name, hotel_email FROM signup_hotel WHERE user_id = %s", (session['user_id'],))
    user = cursor.fetchone()

    # Query to get all bookings of the user with associated room details from booked_room_numbers
    cursor.execute("""
    SELECT 
        b.booking_id, b.check_in, b.check_out, b.num_rooms, b.status, r.room_name,
        b.extra_mattress, b.extra_pillow, b.extra_towel, b.total_amount,
        GROUP_CONCAT(rn.room_number ORDER BY rn.room_number SEPARATOR ', ') AS room_numbers,
        b.proof_of_payment
    FROM bookings b
    JOIN rooms r ON b.room_id = r.room_id
    JOIN booked_room_numbers brn ON b.booking_id = brn.booking_id
    LEFT JOIN room_numbers rn ON brn.room_number_id = rn.room_number_id
    WHERE b.user_id = %s AND b.check_in >= CURDATE()
    GROUP BY b.booking_id
    ORDER BY b.check_in ASC
    """, (session['user_id'],))


    bookings = cursor.fetchall()

    # Past bookings (already archived ones)
    cursor.execute("SELECT * FROM archived_bookings WHERE user_id = %s AND (status = 'Confirmed' OR status = 'Declined')", (session['user_id'],))
    archived_bookings = cursor.fetchall()

    conn.close()
    cursor.close()

    if user:
        return render_template('dashboard.html', first_name=user[0], last_name=user[1], email=user[2], bookings=bookings, archived_bookings=archived_bookings)
    else:
        flash("User not found!", "danger")
        return redirect(url_for('login'))

@app.route('/admin/bookings')
def admin_bookings():
    # Check if the user is logged in and is an admin
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for('index'))  # Redirect to a non-admin page (e.g., dashboard)

    # If the user is admin, fetch bookings
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            b.booking_id, 
            u.first_name, 
            u.last_name, 
            r.room_name, 
            b.check_in, 
            b.check_out, 
            b.guests, 
            b.num_rooms, 
            b.status
        FROM bookings b
        LEFT JOIN signup_hotel u ON b.user_id = u.user_id
        LEFT JOIN rooms r ON b.room_id = r.room_id
        ORDER BY b.check_in ASC;
    """)

    bookings = cursor.fetchall()
    conn.close()
    cursor.close()

    if not bookings:
        flash("No bookings found!", "warning")

    return render_template('admin.html', bookings=bookings)


import logging

@app.route("/add-rooms", methods=["POST"])
def add_rooms():
    roomName = request.form["roomName"]
    totalRooms = int(request.form["totalRooms"])
    roomType = request.form["roomType"]
    price = request.form["price"]
    description = request.form["description"]
    roomImage = request.files["roomImage"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Sanitize and save image
        image_filename = secure_filename(f"{roomName}_{roomImage.filename}")
        image_path = os.path.join(app.config["ROOM_UPLOAD_FOLDER"], image_filename)

        # Ensure upload directory exists
        os.makedirs(app.config["ROOM_UPLOAD_FOLDER"], exist_ok=True)
        roomImage.save(image_path)

        # Insert into rooms table
        cursor.execute("""
            INSERT INTO rooms (room_name, description, price, image_url, room_type, total_rooms)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (roomName, description, price, image_filename, roomType, totalRooms))

        conn.commit()
        room_id = cursor.lastrowid

        # Get highest current room number
        cursor.execute("SELECT MAX(room_number) AS max_room_number FROM room_numbers")
        result = cursor.fetchone()
        max_room_number = result['max_room_number'] or 100  # Start from 101

        # Generate new room numbers
        for i in range(1, totalRooms + 1):
            new_room_number = max_room_number + i

            # Avoid duplicates
            cursor.execute("SELECT COUNT(*) AS count FROM room_numbers WHERE room_number = %s", (new_room_number,))
            if cursor.fetchone()['count'] > 0:
                continue

            cursor.execute("""
                INSERT INTO room_numbers (room_id, room_number, is_available)
                VALUES (%s, %s, %s)
            """, (room_id, new_room_number, 1))

        conn.commit()
        flash("Room(s) added successfully", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error adding room: {e}", "danger")
        print(f"[ERROR] {e}")  # Debug log

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("manage_rooms"))




@app.route('/delete-rooms/<int:roomID>')
def delete_rooms(roomID):
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("You must be an admin to delete rooms", "danger")
        return redirect(url_for('index'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Archive the room information before deletion
        cursor.execute("""
            INSERT INTO rooms_archive (room_id, type, room_name, description, price, image_url, room_type, total_rooms)
            SELECT room_id, type, room_name, description, price, image_url, room_type, total_rooms
            FROM rooms
            WHERE room_id = %s
        """, (roomID,))

        # Delete related room numbers first
        cursor.execute("""
            DELETE FROM room_numbers WHERE room_id = %s
        """, (roomID,))

        # Now, delete the room from the rooms table
        cursor.execute("""
            DELETE FROM rooms WHERE room_id = %s
        """, (roomID,))

        conn.commit()
        flash("Room deleted successfully", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('manage_rooms'))




@app.route("/edit-rooms/<int:roomID>", methods=["POST"])
def edit_rooms(roomID):
    roomName = request.form["roomName"]
    totalRooms = request.form["totalRooms"]
    editRoomType = request.form["editRoomTpye"]
    price = request.form["price"]
    description = request.form["description"]
    editRoomImage = request.files["editRoomImage"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT image_url FROM rooms WHERE room_id = %s", (roomID,))
    current_image = cursor.fetchone()["image_url"]

    if editRoomImage and editRoomImage.filename:
        filename = secure_filename(editRoomImage.filename)
        room_image_filename = f"{roomID}_{filename}"
        room_image_path = os.path.join(app.config["ROOM_UPLOAD_FOLDER"], room_image_filename)

        try:
            editRoomImage.save(room_image_path)
            print(f"Image saved successfully at: {room_image_path}")
        except Exception as e:
            print(f"Error saving image: {e}")
            flash("Error saving the image!", "danger")
            return redirect(url_for("manage_rooms"))
        new_image_filename = room_image_filename
    else:
        new_image_filename = current_image

    cursor.execute("""
        UPDATE rooms 
        SET type=%s, room_name=%s, description=%s, 
            price=%s, image_url=%s, room_type=%s,
            total_rooms=%s WHERE room_id=%s
    """, (editRoomType, roomName, description, price, new_image_filename, editRoomType, totalRooms, roomID))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("manage_rooms"))

@app.route('/admin/update_booking_status', methods=['POST'])
def update_booking_status():
    booking_id = request.form.get('booking_id')
    new_status = request.form.get('status')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE bookings SET status = %s WHERE booking_id = %s
    """, (new_status, booking_id))

    conn.commit()
    conn.close()
    cursor.close()

    # Passing a variable to trigger the modal
    return redirect(url_for('admin_dashboard', update_success=True))
    


@app.route('/archive_booking', methods=['POST'])
def archive_booking():
    booking_id = request.form.get('booking_id')
    if not booking_id:
        flash("Missing booking ID", "danger")
        return redirect(url_for('admin_dashboard'))

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Fetch the booking details along with user and room info, and extra services
        cursor.execute("""
            SELECT 
                b.booking_id, 
                b.user_id,
                b.room_id,
                u.first_name, 
                u.last_name, 
                r.room_name, 
                b.check_in, 
                b.check_out, 
                b.guests, 
                b.num_rooms, 
                b.status, 
                b.proof_of_payment,
                b.extra_mattress,
                b.extra_pillow,
                b.extra_towel,
                b.total_amount,
                b.room_number_id
            FROM bookings b
            LEFT JOIN signup_hotel u ON b.user_id = u.user_id
            LEFT JOIN rooms r ON b.room_id = r.room_id
            WHERE b.booking_id = %s
        """, (booking_id,))
        booking = cursor.fetchone()

        if not booking:
            flash(f"Booking with ID {booking_id} not found", "danger")
            return redirect(url_for('admin_dashboard'))

        archived_at = datetime.now()

        # Archive the booking by inserting into archived_bookings table
        cursor.execute("""
            INSERT INTO archived_bookings (
                booking_id, user_id, room_id, first_name, last_name, room_name, 
                check_in, check_out, guests, num_rooms, status, 
                proof_of_payment, archived_at, 
                extra_mattress, extra_pillow, extra_towel, 
                total_amount, room_number_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            booking[0], booking[1], booking[2], booking[3], booking[4], booking[5],
            booking[6], booking[7], booking[8], booking[9], booking[10], booking[11],
            archived_at, booking[12], booking[13], booking[14], booking[15], booking[16]
        ))
        archived_booking_id = cursor.lastrowid

        # Fetch all room_number_ids for the booking from the booked_room_numbers table
        cursor.execute("""
            SELECT room_number_id
            FROM booked_room_numbers
            WHERE booking_id = %s
        """, (booking_id,))
        room_numbers = cursor.fetchall()

        # Insert into archived_booked_room_numbers
        for room in room_numbers:
            cursor.execute("""
                INSERT INTO archived_booked_room_numbers (archived_booking_id, room_number_id)
                VALUES (%s, %s)
            """, (archived_booking_id, room[0]))

        # Mark all the room numbers as available
        for room in room_numbers:
            cursor.execute('UPDATE room_numbers SET is_available = 1 WHERE room_number_id = %s', (room[0],))

        # Delete the booking from the 'bookings' table
        cursor.execute('DELETE FROM bookings WHERE booking_id = %s', (booking_id,))

        # Commit the changes
        conn.commit()

        flash(f"Booking {booking_id} archived successfully!", "success")

    except Exception as e:
        conn.rollback()  # Rollback on any error
        flash(f"Error archiving booking: {str(e)}", "danger")
    
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_dashboard'))


from math import ceil

@app.route('/archive')
def archive():
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for('index'))
    
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    search_term = f"%{search_query}%"

    # Count total records
    cursor.execute("""
        SELECT COUNT(DISTINCT ab.booking_id) AS count
        FROM archived_bookings ab
        LEFT JOIN room_numbers rn ON ab.room_number_id = rn.room_number_id
        WHERE ab.first_name LIKE %s OR ab.last_name LIKE %s OR ab.room_name LIKE %s OR ab.status LIKE %s OR ab.room_number_id  LIKE %s
    """, (search_term, search_term, search_term, search_term, search_term))
    total_count = cursor.fetchone()['count']
    
    total_pages = ceil(total_count / per_page)
    offset = (page - 1) * per_page

    # Fetch archived bookings with grouped room numbers
    cursor.execute("""
        SELECT 
            ab.booking_id, ab.first_name, ab.last_name, ab.room_name,
            ab.check_in, ab.check_out, ab.guests, ab.num_rooms,
            ab.status, ab.extra_mattress, ab.extra_pillow, ab.extra_towel,
            ab.total_amount, ab.archived_booking_id,
            GROUP_CONCAT(rn.room_number ORDER BY rn.room_number SEPARATOR ', ') AS room_number
        FROM archived_bookings ab
        LEFT JOIN archived_booked_room_numbers abn ON ab.archived_booking_id = abn.archived_booking_id
        LEFT JOIN room_numbers rn ON abn.room_number_id = rn.room_number_id
        WHERE ab.first_name LIKE %s OR ab.last_name LIKE %s OR ab.room_name LIKE %s OR ab.status LIKE %s
        GROUP BY ab.archived_booking_id
        ORDER BY ab.check_in DESC
        LIMIT %s OFFSET %s
    """, (search_term, search_term, search_term, search_term, per_page, offset))


    
    bookings = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin/archive.html',
                           bookings=bookings,
                           search_query=search_query,
                           page=page,
                           total_pages=total_pages)




@app.route('/delete_archived_booking', methods=['POST'])
def delete_archived_booking():
    booking_id = request.form.get('booking_id')

    if not booking_id:
        flash("Missing booking ID", "danger")
        return redirect(url_for('archive'))

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # First, fetch the archived_booking_id using the booking_id
        cursor.execute("SELECT archived_booking_id FROM archived_bookings WHERE booking_id = %s", (booking_id,))
        result = cursor.fetchone()
        if not result:
            flash("Archived booking not found", "danger")
            return redirect(url_for('archive'))

        archived_booking_id = result[0]

        # Delete from child table first
        cursor.execute("DELETE FROM archived_booked_room_numbers WHERE archived_booking_id = %s", (archived_booking_id,))

        # Delete from parent table
        cursor.execute("DELETE FROM archived_bookings WHERE archived_booking_id = %s", (archived_booking_id,))

        conn.commit()
        flash("Archived booking deleted successfully!", "success")
    except Exception as e:
        print(f"Error deleting archived booking: {e}")
        flash("Failed to delete archived booking", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('archive'))



# debug mamaya, maling table, di room_availability, room_numbers dapat
# otaps na

@app.route("/delete-booking/<int:booking_id>", methods=["POST"])
def delete_booking(booking_id):
    if 'user_id' not in session:
        flash("You must be logged in to cancel a booking!", "warning")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor()

    # Verify the booking belongs to the logged-in user
    cursor.execute("""
        SELECT booking_id FROM bookings
        WHERE booking_id = %s AND user_id = %s
    """, (booking_id, session['user_id']))
    booking = cursor.fetchone()

    if not booking:
        flash("Booking not found or you are not authorized to cancel this booking.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    # Fetch all room_number_ids from booked_room_numbers
    cursor.execute("""
        SELECT room_number_id FROM booked_room_numbers
        WHERE booking_id = %s
    """, (booking_id,))
    room_number_rows = cursor.fetchall()

    # Mark each room as available
    for (room_number_id,) in room_number_rows:
        cursor.execute("""
            UPDATE room_numbers
            SET is_available = 1
            WHERE room_number_id = %s
        """, (room_number_id,))

    # Delete from booked_room_numbers
    cursor.execute("""
        DELETE FROM booked_room_numbers
        WHERE booking_id = %s
    """, (booking_id,))

    # Delete the booking itself
    cursor.execute("""
        DELETE FROM bookings
        WHERE booking_id = %s
    """, (booking_id,))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Booking cancelled and associated rooms are now available.", "success")
    return redirect(url_for('dashboard'))



from datetime import datetime

@app.route('/edit_booking/<int:booking_id>', methods=['GET', 'POST'])
def edit_booking(booking_id):
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("Unauthorized access", "danger")
        return redirect(url_for('index'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        check_in = request.form.get('check_in')
        check_out = request.form.get('check_out')
        guests = request.form.get('guests')
        num_rooms = int(request.form.get('num_rooms'))
        special_suggestion = request.form.get('special_suggestion')
        room_number_id = request.form.get('room_number_id')

        check_in_date = datetime.strptime(check_in, '%Y-%m-%d')
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d')
        num_nights = (check_out_date - check_in_date).days

        if num_nights <= 0:
            flash("Check-out must be after check-in", "danger")
            return redirect(url_for('edit_booking', booking_id=booking_id))

        # Get room_id from booking
        cursor.execute("SELECT room_id FROM bookings WHERE booking_id = %s", (booking_id,))
        room_id = cursor.fetchone()['room_id']

        # Get room price
        cursor.execute("SELECT price FROM rooms WHERE room_id = %s", (room_id,))
        room_price = cursor.fetchone()['price']

        room_total = room_price * num_nights * num_rooms

        # Handle hardcoded extras (checkboxes: present if checked)
        extra_mattress = bool(request.form.get('extra_mattress'))
        extra_pillow = bool(request.form.get('extra_pillow'))
        extra_towel = bool(request.form.get('extra_towel'))

        extras_total = 0
        if extra_mattress:
            extras_total += 300 * num_nights * num_rooms
        if extra_pillow:
            extras_total += 50 * num_nights * num_rooms
        if extra_towel:
            extras_total += 100 * num_nights * num_rooms

        extra_hour = int(request.form.get('extra_hour', 0))
        extra_hour_total = extra_hour * 200

        total_amount = room_total + extras_total + extra_hour_total

        # Update booking
        cursor.execute("""
            UPDATE bookings
            SET check_in = %s,
                check_out = %s,
                guests = %s,
                num_rooms = %s,
                special_suggestion = %s,
                room_number_id = %s,
                total_amount = %s,
                extra_mattress = %s,
                extra_pillow = %s,
                extra_towel = %s,
                extra_hour = %s
            WHERE booking_id = %s
        """, (
            check_in, check_out, guests, num_rooms, special_suggestion,
            room_number_id, total_amount,
            extra_mattress, extra_pillow, extra_towel,
            extra_hour, booking_id
        ))

        conn.commit()
        flash("Booking updated successfully", "success")
        return redirect(url_for('admin_dashboard'))

    # Pre-fill form values
    cursor.execute("SELECT * FROM bookings WHERE booking_id = %s", (booking_id,))
    booking = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('admin/edit_booking.html', booking=booking)


@app.route('/restore_booking', methods=['POST'])
def restore_booking():
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for('index'))

    archived_booking_id = request.form.get('archived_booking_id')
    if not archived_booking_id:
        flash("Missing archived booking ID", "danger")
        return redirect(url_for('archive'))

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Fetch the archived booking
        cursor.execute("""
            SELECT booking_id, user_id, room_id, check_in, check_out, guests, num_rooms, 
                status, proof_of_payment, extra_mattress, extra_pillow, extra_towel, 
                total_amount, room_number_id
            FROM archived_bookings
            WHERE archived_booking_id = %s
        """, (archived_booking_id,))
        booking = cursor.fetchone()

        if not booking:
            flash("Archived booking not found.", "danger")
            return redirect(url_for('archive'))

        # Check if room_number_id exists
        room_number_id = booking[-1]  # last item in fetch
        cursor.execute("SELECT room_number_id FROM room_numbers WHERE room_number_id = %s", (room_number_id,))
        room_number_exists = cursor.fetchone()

        if not room_number_exists:
            room_number_id = None

        # Insert into bookings table
        cursor.execute("""
            INSERT INTO bookings (
                booking_id, user_id, room_id, check_in, check_out, guests, num_rooms,
                status, proof_of_payment, is_archived,
                extra_mattress, extra_pillow, extra_towel, total_amount, room_number_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s)
        """, (
            booking[0], booking[1], booking[2], booking[3], booking[4], booking[5], booking[6],
            booking[7], booking[8], 0,  # is_archived = 0
            booking[9], booking[10], booking[11], booking[12], room_number_id
        ))

        # Insert booked room numbers from archived version (AFTER inserting into bookings)
        cursor.execute("""
            SELECT room_number_id FROM archived_booked_room_numbers
            WHERE archived_booking_id = %s
        """, (archived_booking_id,))
        archived_room_numbers = cursor.fetchall()

        for row in archived_room_numbers:
            cursor.execute("""
                INSERT INTO booked_room_numbers (booking_id, room_number_id)
                VALUES (%s, %s)
            """, (booking[0], row[0]))

        # Mark the room as unavailable (if exists)
        if room_number_id:
            cursor.execute("UPDATE room_numbers SET is_available = 0 WHERE room_number_id = %s", (room_number_id,))

        # Delete the archived booked room numbers
        cursor.execute("""
            DELETE FROM archived_booked_room_numbers
            WHERE archived_booking_id = %s
        """, (archived_booking_id,))

        # Delete the archived booking
        cursor.execute("""
            DELETE FROM archived_bookings
            WHERE archived_booking_id = %s
        """, (archived_booking_id,))

        conn.commit()
        flash("Booking restored successfully!", "success")


    except Exception as e:
        conn.rollback()
        flash(f"Error restoring booking: {str(e)}", "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('archive'))


@app.route('/admin_rooms_available', methods=['GET', 'POST'])
def admin_rooms_available():
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for('index'))

    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    # Get the search query (either available or unavailable)
    search_query = request.form.get('search', request.args.get('search', '')).strip().lower()
    per_page = app.config.get('PER_PAGE', 10)
    offset = (page - 1) * per_page

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        base_query = '''
            SELECT 
                room_numbers.room_number_id, 
                room_numbers.room_number, 
                room_numbers.room_id, 
                room_numbers.is_available,
                rooms.type AS room_type
            FROM room_numbers
            JOIN rooms ON room_numbers.room_id = rooms.room_id
        '''

        count_query = '''
            SELECT COUNT(*) AS total
            FROM room_numbers
            JOIN rooms ON room_numbers.room_id = rooms.room_id
        '''

        params = []

        # Adjust the query based on the search query input
        if search_query == 'available':
            base_query += ' WHERE room_numbers.is_available = 1'
            count_query += ' WHERE room_numbers.is_available = 1'
        elif search_query == 'unavailable':  # For unavailable (booked) rooms
            base_query += ' WHERE room_numbers.is_available = 0'
            count_query += ' WHERE room_numbers.is_available = 0'
        elif search_query:
            base_query += ' WHERE room_numbers.room_number LIKE %s OR rooms.type LIKE %s'
            count_query += ' WHERE room_numbers.room_number LIKE %s OR rooms.type LIKE %s'
            params.extend([f'%{search_query}%', f'%{search_query}%'])

        base_query += ' ORDER BY room_numbers.room_number ASC LIMIT %s OFFSET %s'
        params_for_count = params.copy()
        params.extend([per_page, offset])

        cursor.execute(count_query, params_for_count)
        total = cursor.fetchone()['total']

        cursor.execute(base_query, params)
        rooms = cursor.fetchall()

        total_pages = (total + per_page - 1) // per_page

        start_page = max(page - 4, 1)
        end_page = min(start_page + 9, total_pages)
        start_page = max(end_page - 9, 1)

    except Error as e:
        flash(f"Database error: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

    return render_template('admin/admin_rooms_available.html',
                        rooms=rooms,
                        search_query=search_query,
                        page=page,
                        total_pages=total_pages,
                        start_page=start_page,
                        end_page=end_page)



@app.route('/user_available_rooms', methods=['GET', 'POST'])
def user_available_rooms():
    if 'user_id' not in session:
        flash("You must be logged in to view available rooms", "danger")
        return redirect(url_for('login'))

    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    search_query = request.form.get('search', request.args.get('search', '')).strip().lower()
    per_page = app.config.get('PER_PAGE', 10)
    offset = (page - 1) * per_page

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        base_query = '''
            SELECT 
                rn.room_number_id,
                rn.room_number,
                rn.room_id,
                rn.is_available,
                r.type AS room_type,
                MAX(b.check_out) AS next_available_date
            FROM room_numbers rn
            LEFT JOIN rooms r ON rn.room_id = r.room_id
            LEFT JOIN booked_room_numbers brn ON rn.room_number_id = brn.room_number_id
            LEFT JOIN bookings b ON brn.booking_id = b.booking_id AND b.check_out > CURDATE()
        '''

        count_query = '''
            SELECT COUNT(DISTINCT rn.room_number_id) AS total
            FROM room_numbers rn
            LEFT JOIN rooms r ON rn.room_id = r.room_id
            LEFT JOIN booked_room_numbers brn ON rn.room_number_id = brn.room_number_id
            LEFT JOIN bookings b ON brn.booking_id = b.booking_id AND b.check_out > CURDATE()
        '''

        conditions = []
        base_params = []
        count_params = []

        if search_query == 'available':
            conditions.append('rn.is_available = 1')
        elif search_query == 'unavailable' or search_query == 'not available':
            conditions.append('rn.is_available = 0')
        elif search_query:
            conditions.append('(rn.room_number LIKE %s OR r.type LIKE %s)')
            base_params.extend([f'%{search_query}%', f'%{search_query}%'])
            count_params.extend([f'%{search_query}%', f'%{search_query}%'])

        if conditions:
            where_clause = ' WHERE ' + ' AND '.join(conditions)
            base_query += where_clause
            count_query += where_clause

        base_query += ' GROUP BY rn.room_number_id ORDER BY rn.room_number ASC LIMIT %s OFFSET %s'
        base_params.extend([per_page, offset])

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()['total']

        cursor.execute(base_query, base_params)
        rooms = cursor.fetchall()

        total_pages = (total + per_page - 1) // per_page
        start_page = max(page - 4, 1)
        end_page = min(start_page + 9, total_pages)
        start_page = max(end_page - 9, 1)

    except Error as e:
        flash(f"Database error: {str(e)}", "danger")
        return redirect(url_for('index'))
    finally:
        cursor.close()
        conn.close()

    return render_template('user_available_rooms.html',
                        rooms=rooms,
                        search_query=search_query,
                        page=page,
                        total_pages=total_pages,
                        start_page=start_page,
                        end_page=end_page)





@app.route('/update_room_availability/<int:room_number_id>', methods=['POST'])
def update_room_availability(room_number_id):
    if 'user_id' not in session or session.get('is_admin') != 1:
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for('index'))

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Toggle availability
        cursor.execute("SELECT is_available FROM room_numbers WHERE room_number_id = %s", (room_number_id,))
        current = cursor.fetchone()
        if current:
            new_status = 0 if current[0] == 1 else 1
            cursor.execute("UPDATE room_numbers SET is_available = %s WHERE room_number_id = %s", (new_status, room_number_id))
            conn.commit()
            flash("Room availability updated successfully.", "success")
        else:
            flash("Room not found.", "danger")

    except Error as e:
        flash(f"Database error: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_rooms_available'))



if __name__ == '__main__':
    app.run(debug=True)
