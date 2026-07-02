import mysql.connector
import json
import os
import datetime
import jwt

DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "123Shorya@"
DB_NAME = "dooper_symptom_checker"
JWT_SECRET = "dooper_symptom_checker_secret_key_jwt_token_auth"

def get_db_connection():

    base_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(
        os.path.join(base_dir, "static", "uploads"),
        exist_ok=True
    )

    os.makedirs(
        os.path.join(base_dir, "static", "uploads", "profile_pics"),
        exist_ok=True
    )

    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

    except mysql.connector.Error as err:

        if err.errno == 1049:

            print("Database not found. Initializing database and tables...")

            conn = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD
            )

            cursor = conn.cursor()

            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
            cursor.execute(f"USE {DB_NAME}")

            schema_path = os.path.join(base_dir, "symptom_checker.sql")

            if os.path.exists(schema_path):

                with open(schema_path, "r") as f:
                    schema_sql = f.read()

                for command in schema_sql.split(";"):

                    if command.strip():
                        cursor.execute(command)

            conn.commit()

            cursor.close()
            conn.close()

            return mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )

        else:
            raise err

# JWT Helpers
def encode_jwt_token(user_id):
    try:
        payload = {
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1),
            "iat": datetime.datetime.utcnow(),
            "sub": str(user_id)   # <-- Convert to string
        }

        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        if isinstance(token, bytes):
            token = token.decode("utf-8")

        return token

    except Exception as e:
        print("JWT Encode Error:", e)
        return None

def decode_jwt_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"])      # <-- Convert back to integer

    except jwt.ExpiredSignatureError:
        return "Expired"

    except jwt.InvalidTokenError as e:
        print("JWT Decode Error:", e)
        return "Invalid"

    except Exception as e:
        print("JWT Error:", e)
        return "Error"

# User Queries
def create_user(name, email, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, password_hash)
        )
        user_id = cursor.lastrowid
        
        # Initialize default settings
        cursor.execute(
            "INSERT IGNORE INTO settings (user_id, theme, language) VALUES (%s, %s, %s)",
            (user_id, "light", "en")
        )
        conn.commit()
        return user_id
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, password, profile_pic FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, password, profile_pic FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def update_user_profile_pic(user_id, filename):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET profile_pic = %s WHERE id = %s", (filename, user_id))
    conn.commit()
    cursor.close()
    conn.close()

def update_user_password(user_id, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = %s WHERE id = %s", (password_hash, user_id))
    conn.commit()
    cursor.close()
    conn.close()

# Settings Queries
def get_user_settings(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM settings WHERE user_id = %s", (user_id,))
    settings = cursor.fetchone()
    if not settings:
        cursor.execute("INSERT IGNORE INTO settings (user_id, theme, language) VALUES (%s, 'light', 'en')", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM settings WHERE user_id = %s", (user_id,))
        settings = cursor.fetchone()
    cursor.close()
    conn.close()
    return settings

def update_user_settings(user_id, theme, language):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO settings (user_id, theme, language) VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE theme = %s, language = %s
        """,
        (user_id, theme, language, theme, language)
    )
    conn.commit()
    cursor.close()
    conn.close()

# Assessment Queries
def create_assessment(user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO assessments (user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice)
        )
        assessment_id = cursor.lastrowid
        conn.commit()
        return assessment_id
    except mysql.connector.Error as err:
        print(f"Error creating assessment: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_assessments_by_user(user_id, query_str=None, severity=None, date_val=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT id, user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice, CAST(created_at AS CHAR) as created_at FROM assessments WHERE user_id = %s"
    params = [user_id]
    
    if query_str:
        sql += " AND (symptoms LIKE %s OR condition_name LIKE %s OR recommended_specialty LIKE %s)"
        like_str = f"%{query_str}%"
        params.extend([like_str, like_str, like_str])
        
    if severity:
        sql += " AND severity = %s"
        params.append(severity)
        
    if date_val:
        sql += " AND DATE(created_at) = %s"
        params.append(date_val)
        
    sql += " ORDER BY created_at DESC"
    
    cursor.execute(sql, tuple(params))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def get_assessment_by_id(assessment_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice, CAST(created_at AS CHAR) as created_at FROM assessments WHERE id = %s AND user_id = %s",
        (assessment_id, user_id)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def delete_assessment(assessment_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM assessments WHERE id = %s AND user_id = %s", (assessment_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

# Chat Messages
def add_chat_message(assessment_id, sender, message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_messages (assessment_id, sender, message) VALUES (%s, %s, %s)",
        (assessment_id, sender, message)
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_chat_messages(assessment_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT sender, message, CAST(created_at AS CHAR) as created_at FROM chat_messages WHERE assessment_id = %s ORDER BY id ASC",
        (assessment_id,)
    )
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return messages

# Dashboard Stats
def get_dashboard_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total assessments
    cursor.execute("SELECT COUNT(*) FROM assessments WHERE user_id = %s", (user_id,))
    total = cursor.fetchone()[0]
    
    # Severity distribution
    cursor.execute("SELECT COUNT(*) FROM assessments WHERE user_id = %s AND severity = 'Mild'", (user_id,))
    mild = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assessments WHERE user_id = %s AND severity = 'Moderate'", (user_id,))
    moderate = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assessments WHERE user_id = %s AND severity = 'Severe'", (user_id,))
    severe = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    return {
        "total": total,
        "mild": mild,
        "moderate": moderate,
        "severe": severe
    }
