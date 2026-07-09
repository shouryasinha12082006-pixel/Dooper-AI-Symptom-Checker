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

def initialize_database_and_migrations(conn):
    cursor = conn.cursor()
    # 1. Create medical_knowledge table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medical_knowledge (
        id INT AUTO_INCREMENT PRIMARY KEY,
        condition_name VARCHAR(255) UNIQUE NOT NULL,
        description TEXT,
        symptoms TEXT,
        severity VARCHAR(50) NOT NULL,
        recommended_department VARCHAR(255) NOT NULL,
        home_care_advice TEXT,
        medical_references TEXT,
        red_flags TEXT
    )
    """)
    conn.commit()
    
    # 2. Seed/Sync medical_knowledge table from JSON
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "medical_knowledge.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                knowledge_data = json.load(f)
            for item in knowledge_data:
                cursor.execute(
                    """
                    INSERT INTO medical_knowledge (condition_name, description, symptoms, severity, recommended_department, home_care_advice, medical_references, red_flags)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        description = VALUES(description),
                        symptoms = VALUES(symptoms),
                        severity = VALUES(severity),
                        recommended_department = VALUES(recommended_department),
                        home_care_advice = VALUES(home_care_advice),
                        medical_references = VALUES(medical_references),
                        red_flags = VALUES(red_flags)
                    """,
                    (
                        item["condition_name"],
                        item["description"],
                        ",".join(item["symptoms"]),
                        item["severity"],
                        item["recommended_department"],
                        item["home_care_advice"],
                        json.dumps(item["medical_references"]),
                        json.dumps(item["red_flags"])
                    )
                )
            conn.commit()
            print("Seeded and updated medical knowledge table successfully.")
        except Exception as e:
            print(f"Error seeding medical knowledge: {e}")

    # 3. Add migrations to assessments table
    migrations = [
        ("weight", "VARCHAR(50) DEFAULT NULL"),
        ("height", "VARCHAR(50) DEFAULT NULL"),
        ("pain_level", "INT DEFAULT NULL"),
        ("allergies", "TEXT DEFAULT NULL"),
        ("current_medications", "TEXT DEFAULT NULL"),
        ("pregnancy_status", "VARCHAR(255) DEFAULT NULL"),
        ("confidence_scores", "TEXT DEFAULT NULL"),
        ("medical_references", "TEXT DEFAULT NULL"),
        ("red_flag_detected", "TINYINT DEFAULT 0"),
        ("temperature", "VARCHAR(50) DEFAULT NULL"),
        ("temperature_unit", "VARCHAR(10) DEFAULT NULL")
    ]
    
    for col_name, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE assessments ADD COLUMN {col_name} {col_type}")
            conn.commit()
            print(f"Migration: Added column {col_name} successfully.")
        except mysql.connector.Error as err:
            # Error 1060 means column already exists, which is fine
            if err.errno != 1060:
                print(f"Migration error for column {col_name}: {err}")
                
    cursor.close()

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
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        initialize_database_and_migrations(conn)
        return conn

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

            new_conn = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            initialize_database_and_migrations(new_conn)
            return new_conn

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
def create_assessment(user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice, weight=None, height=None, pain_level=None, allergies=None, current_medications=None, pregnancy_status=None, confidence_scores=None, medical_references=None, red_flag_detected=0, temperature=None, temperature_unit=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO assessments (user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice, weight, height, pain_level, allergies, current_medications, pregnancy_status, confidence_scores, medical_references, red_flag_detected, temperature, temperature_unit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice, weight, height, pain_level, allergies, current_medications, pregnancy_status, confidence_scores, medical_references, red_flag_detected, temperature, temperature_unit)
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
    
    sql = "SELECT id, user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice, weight, height, pain_level, allergies, current_medications, pregnancy_status, confidence_scores, medical_references, red_flag_detected, temperature, temperature_unit, CAST(created_at AS CHAR) as created_at FROM assessments WHERE user_id = %s"
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
        "SELECT id, user_id, symptoms, age, gender, duration, existing_conditions, condition_name, explanation, severity, recommended_specialty, health_advice, weight, height, pain_level, allergies, current_medications, pregnancy_status, confidence_scores, medical_references, red_flag_detected, temperature, temperature_unit, CAST(created_at AS CHAR) as created_at FROM assessments WHERE id = %s AND user_id = %s",
        (assessment_id, user_id)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def get_all_medical_knowledge():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medical_knowledge")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def get_relevant_knowledge(symptoms_text):
    if not symptoms_text:
        return []
    
    words = [w.lower().strip() for w in symptoms_text.split() if len(w.strip()) > 3]
    if not words:
        return get_all_medical_knowledge()[:5]  # Fallback to some items
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # We will search the database by checking if any of the keywords match condition_name, description or symptoms list.
    query = "SELECT * FROM medical_knowledge WHERE "
    conditions = []
    params = []
    
    for word in words:
        # Match word in condition_name, description, or symptoms CSV
        conditions.append("(condition_name LIKE %s OR description LIKE %s OR symptoms LIKE %s)")
        like_term = f"%{word}%"
        params.extend([like_term, like_term, like_term])
        
    query += " OR ".join(conditions)
    cursor.execute(query, tuple(params))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # If nothing matched, get default list
    if not results:
        return get_all_medical_knowledge()[:5]
        
    return results

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
