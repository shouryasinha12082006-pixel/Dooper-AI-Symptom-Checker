from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import database as db
from rag_engine import rag_engine
import os
import re
import json
import urllib.request
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = "dooper_ai_symptom_checker_secret_key"


# Configure uploads directory for profile pictures
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "profile_pics")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB max upload limit

# JWT Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        token = request.cookies.get("auth_token")

        print("Cookie Token:", token)

        if not token:
            print("No auth cookie found.")
            return redirect(url_for("login"))

        user_id = db.decode_jwt_token(token)

        print("Decoded User ID:", user_id)

        if user_id in ["Expired", "Invalid", "Error"]:
            flash("Session expired. Please log in again.", "danger")

            resp = make_response(redirect(url_for("login")))
            resp.delete_cookie("auth_token")
            return resp

        request.user_id = user_id

        return f(*args, **kwargs)

    return decorated_function

# Context processor to inject user information, settings, and avatars globally
@app.context_processor
def inject_global_vars():
    token = request.cookies.get("auth_token")
    if token:
        user_id = db.decode_jwt_token(token)
        if user_id not in ["Expired", "Invalid", "Error"]:
            user_info = db.get_user_by_id(user_id)
            settings = db.get_user_settings(user_id)
            if user_info:
                return {
                    "user_name": user_info["name"],
                    "user_info": user_info,
                    "theme": settings["theme"] if settings else "light",
                    "language": settings["language"] if settings else "en"
                }
    return {"user_name": None, "user_info": None, "theme": "light", "language": "en"}

# Helper to determine user initials avatar background color
@app.context_processor
def utility_processor():
    def get_avatar_color(username):
        colors_list = ["#E30613", "#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#06B6D4", "#14B8A6", "#F97316"]
        if not username:
            return colors_list[0]
        char_sum = sum(ord(c) for c in username)
        return colors_list[char_sum % len(colors_list)]
    return dict(get_avatar_color=get_avatar_color)

# Root route redirector
@app.route("/")
def index():
    token = request.cookies.get("auth_token")
    if token:
        user_id = db.decode_jwt_token(token)
        if user_id not in ["Expired", "Invalid", "Error"]:
            return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# Register route
@app.route("/register", methods=["GET", "POST"])
def register():
    token = request.cookies.get("auth_token")
    if token:
        user_id = db.decode_jwt_token(token)
        if user_id not in ["Expired", "Invalid", "Error"]:
            return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email address.", "danger")
            return render_template("register.html")

        hashed_pass = generate_password_hash(password)
        user_id = db.create_user(name, email, hashed_pass)

        if user_id:
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Email already registered.", "danger")

    return render_template("register.html")

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    token = request.cookies.get("auth_token")
    if token:
        user_id = db.decode_jwt_token(token)
        if user_id not in ["Expired", "Invalid", "Error"]:
            return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("login.html")

        user = db.get_user_by_email(email)
        if user and check_password_hash(user["password"], password):
            token = db.encode_jwt_token(user["id"])
            if token:
                resp = make_response(redirect(url_for("dashboard")))
                # Set HTTP-only secure cookie
                resp.set_cookie("auth_token", token, httponly=True, max_age=86400)
                flash(f"Welcome back, {user['name']}!", "success")
                return resp
            else:
                flash("Token generation failed. Please try again.", "danger")
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")

# Logout route
@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie("auth_token")
    flash("You have successfully logged out.", "success")
    return resp

# Theme Toggle AJAX
@app.route("/toggle-theme", methods=["POST"])
@login_required
def toggle_theme():
    settings = db.get_user_settings(request.user_id)
    new_theme = "dark" if settings["theme"] == "light" else "light"
    db.update_user_settings(request.user_id, new_theme, settings["language"])
    return jsonify({"status": "success", "theme": new_theme})

# Dashboard / Symptom Checker Page
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        symptoms = request.form.get("symptoms", "").strip()
        age = request.form.get("age", "").strip()
        gender = request.form.get("gender", "")
        duration = request.form.get("duration", "").strip()
        existing_conditions = request.form.get("existing_conditions", "").strip()
        weight = request.form.get("weight", "").strip()
        height = request.form.get("height", "").strip()
        pain_level = request.form.get("pain_level", "").strip()
        allergies = request.form.get("allergies", "").strip()
        current_medications = request.form.get("current_medications", "").strip()
        pregnancy_status = request.form.get("pregnancy_status", "").strip()
        temperature = request.form.get("temperature", "").strip()
        temperature_unit = request.form.get("temperature_unit", "").strip()

        if not symptoms or not age or not gender or not duration:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("dashboard"))

        # Emergency keywords check
        is_emergency = detect_emergency_keywords(symptoms, pain_level, pregnancy_status)

        # Create interactive assessment record
        assessment_id = db.create_assessment(
            user_id=request.user_id,
            symptoms=symptoms,
            age=int(age),
            gender=gender,
            duration=duration,
            existing_conditions=existing_conditions or None,
            condition_name="Consultation in Progress",
            explanation="interactive triage questionnaire...",
            severity="Moderate",
            recommended_specialty="General Physician",
            health_advice="Interactive guidance",
            weight=weight or None,
            height=height or None,
            pain_level=int(pain_level) if pain_level else None,
            allergies=allergies or None,
            current_medications=current_medications or None,
            pregnancy_status=pregnancy_status or None,
            confidence_scores="[]",
            medical_references="[]",
            red_flag_detected=1 if is_emergency else 0,
            temperature=temperature or None,
            temperature_unit=temperature_unit or None
        )

        if is_emergency:
            db.update_assessment_status(assessment_id, "emergency")
            db.add_chat_message(assessment_id, "ai", "⚠️ EMERGENCY ALERT DETECTED: You may be experiencing a critical medical emergency. Please read the directions below immediately.")
            return redirect(url_for("assessment_detail", assessment_id=assessment_id))

        # Initialize chatbot consultation greeting
        db.update_assessment_status(assessment_id, "active", current_step=0)
        db.add_chat_message(assessment_id, "ai", f"Hello! I am your Dooper AI Clinical Assistant. I've received your symptom report: '{symptoms}'. To build a structured clinical assessment, I will ask you a few follow-up questions. Let's begin: When did this symptom start, and has it been getting progressively worse?")

        if assessment_id:
            return redirect(url_for("assessment_detail", assessment_id=assessment_id))
        else:
            flash("Failed to save assessment. Please try again.", "danger")
            return redirect(url_for("dashboard"))

    recent = db.get_assessments_by_user(request.user_id)
    stats = db.get_dashboard_stats(request.user_id)
    bookings = db.get_bookings_by_user(request.user_id)
    
    return render_template("dashboard.html", recent_assessments=recent, stats=stats, bookings=bookings)

# Assessment detail view / interactive chat controller
@app.route("/assessment/<int:assessment_id>")
@login_required
def assessment_detail(assessment_id):
    assessment = db.get_assessment_by_id(assessment_id, request.user_id)
    if not assessment:
        flash("Record not found or unauthorized.", "danger")
        return redirect(url_for("dashboard"))
        
    chat_messages = db.get_chat_messages(assessment_id)
    
    # Check consultation state
    status = assessment.get("status", "completed")
    
    if status == "completed":
        # Deserialize JSON fields
        if assessment.get("confidence_scores"):
            try:
                assessment["confidence_scores_list"] = json.loads(assessment["confidence_scores"])
            except Exception:
                assessment["confidence_scores_list"] = []
        else:
            assessment["confidence_scores_list"] = []
            
        if assessment.get("medical_references"):
            try:
                assessment["medical_references_list"] = json.loads(assessment["medical_references"])
            except Exception:
                assessment["medical_references_list"] = []
        else:
            assessment["medical_references_list"] = []
            
        # Parse final report JSON if present
        report = {}
        if assessment.get("final_report"):
            try:
                report = json.loads(assessment["final_report"])
            except Exception:
                pass
                
        return render_template("assessment_detail.html", assessment=assessment, chat_messages=chat_messages, report=report)
    
    # Active or emergency consultation view
    return render_template("consultation.html", consultation=assessment, messages=chat_messages)

# Interactive Triage Message Endpoint
@app.route("/assessment/<int:assessment_id>/message", methods=["POST"])
@login_required
def send_consultation_message(assessment_id):
    c = db.get_assessment_by_id(assessment_id, request.user_id)
    if not c:
        return jsonify({"status": "error", "message": "Record not found"}), 404
        
    status = c.get("status", "active")
    if status != "active":
        return jsonify({"status": "error", "message": "Consultation is no longer active"}), 400

    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"status": "error", "message": "Empty message"}), 400

    # Save user response
    db.add_chat_message(assessment_id, "user", user_message)

    # Check for emergency keywords in new response
    if detect_emergency_keywords(user_message):
        db.update_assessment_status(assessment_id, "emergency")
        alert_msg = "⚠️ EMERGENCY ALERT: You have mentioned critical symptoms. Please stop this chat and seek immediate emergency care."
        db.add_chat_message(assessment_id, "ai", alert_msg)
        return jsonify({"status": "emergency", "reply": alert_msg})

    next_step = c.get("current_step", 0) + 1
    db.update_assessment_status(assessment_id, status=None, current_step=next_step)

    # RAG search context
    rag_context = rag_engine.query(c["symptoms"] + " " + user_message)

    if next_step >= 4:
        # Finalize and compile diagnostics
        chat_messages = db.get_chat_messages(assessment_id)
        report = generate_structured_report_ai(c, chat_messages, rag_context)
        
        # Save structured values to assessments
        db.update_assessment_status(assessment_id, "completed", final_report=json.dumps(report))
        db.add_chat_message(assessment_id, "ai", "Thank you. I have gathered enough information and generated your structured clinical assessment report. You can now open it.")
        
        # Update main columns for backwards compatibility
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE assessments SET condition_name = %s, explanation = %s, severity = %s, recommended_specialty = %s, health_advice = %s, confidence_scores = %s, medical_references = %s, red_flag_detected = %s WHERE id = %s",
            (
                report["primary_condition"]["name"],
                report["primary_condition"]["reasoning"],
                report["severity"],
                report["recommended_specialist"]["name"],
                report["home_care_advice"],
                json.dumps(report["differential_diagnosis"]),
                json.dumps(report["medical_references"]),
                1 if report["severity"] == "Severe" else 0,
                assessment_id
            )
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "completed"})

    # Next follow-up questions
    follow_up_questions = [
        "How would you rate the pain or discomfort on a scale of 1 to 10? Also, are you experiencing any fever, chills, or sweats?",
        "Are you experiencing any other symptoms, such as nausea, vomiting, dizziness, or vision changes?",
        "Have you taken any medications to relieve these symptoms, and do you have any pre-existing health conditions or allergies?"
    ]
    
    ai_question = follow_up_questions[next_step - 1]
    db.add_chat_message(assessment_id, "ai", ai_question)
    return jsonify({"status": "active", "reply": ai_question})

# Force Consultation Finish Early
@app.route("/assessment/<int:assessment_id>/complete", methods=["POST"])
@login_required
def complete_consultation_early(assessment_id):
    c = db.get_assessment_by_id(assessment_id, request.user_id)
    if not c:
        return jsonify({"status": "error", "message": "Record not found"}), 404

    rag_context = rag_engine.query(c["symptoms"])
    chat_messages = db.get_chat_messages(assessment_id)
    report = generate_structured_report_ai(c, chat_messages, rag_context)

    db.update_assessment_status(assessment_id, "completed", final_report=json.dumps(report))
    db.add_chat_message(assessment_id, "ai", "Consultation finalized early at patient's request. Structured clinical assessment generated.")
    
    # Update main columns for backwards compatibility
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE assessments SET condition_name = %s, explanation = %s, severity = %s, recommended_specialty = %s, health_advice = %s, confidence_scores = %s, medical_references = %s, red_flag_detected = %s WHERE id = %s",
        (
            report["primary_condition"]["name"],
            report["primary_condition"]["reasoning"],
            report["severity"],
            report["recommended_specialist"]["name"],
            report["home_care_advice"],
            json.dumps(report["differential_diagnosis"]),
            json.dumps(report["medical_references"]),
            1 if report["severity"] == "Severe" else 0,
            assessment_id
        )
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success"})

# Book Specialist Appointment
@app.route("/book-appointment", methods=["POST"])
@login_required
def book_appointment():
    data = request.get_json()
    assessment_id = data.get("assessment_id")
    specialist_type = data.get("specialist_type")
    doctor_name = data.get("doctor_name")
    app_date = data.get("appointment_date")

    if not specialist_type or not doctor_name or not app_date:
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    dt = datetime.strptime(app_date, "%Y-%m-%d %H:%M")
    booking_id = db.create_booking(request.user_id, assessment_id, specialist_type, doctor_name, dt)
    if booking_id:
        return jsonify({"status": "success", "message": f"Appointment successfully scheduled with {doctor_name}."})
    return jsonify({"status": "error", "message": "Failed to schedule appointment."}), 500

# Health History Timeline
@app.route("/timeline")
@login_required
def timeline_page():
    history = db.get_assessments_by_user(request.user_id)
    timeline_events = []
    for c in history:
        status = c.get("status", "completed")
        if status == "completed":
            timeline_events.append({
                "id": c["id"],
                "date": c["created_at"],
                "symptoms": c["symptoms"],
                "primary_condition": c["condition_name"],
                "severity": c["severity"],
                "specialist": c["recommended_specialty"]
            })
    return render_template("timeline.html", events=timeline_events)


# Delete assessment record
@app.route("/assessment/<int:assessment_id>/delete", methods=["POST"])
@login_required
def delete_assessment(assessment_id):
    assessment = db.get_assessment_by_id(assessment_id, request.user_id)
    if not assessment:
        flash("Record not found or unauthorized.", "danger")
        return redirect(url_for("dashboard"))
        
    db.delete_assessment(assessment_id, request.user_id)
    flash("Record successfully deleted.", "success")
    return redirect(url_for("history"))

# History filter view
@app.route("/history")
@login_required
def history():
    search = request.args.get("search", "").strip()
    severity = request.args.get("severity", "").strip()
    date = request.args.get("date", "").strip()
    
    # Fetch filtered history records
    assessments = db.get_assessments_by_user(request.user_id, query_str=search, severity=severity, date_val=date)
    return render_template("history.html", assessments=assessments)

# Profile configuration page
@app.route("/profile")
@login_required
def profile():
    user_info = db.get_user_by_id(request.user_id)
    settings = db.get_user_settings(request.user_id)
    return render_template("profile.html", user_info=user_info, settings=settings)

# Profile Pic Upload
@app.route("/profile/pic", methods=["POST"])
@login_required
def upload_profile_pic():
    if "profile_pic" not in request.files:
        flash("No file selected.", "danger")
        return redirect(url_for("profile"))
        
    file = request.files["profile_pic"]
    if file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("profile"))
        
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ["png", "jpg", "jpeg"]:
        flash("Invalid image format. PNG, JPG, and JPEG only.", "danger")
        return redirect(url_for("profile"))
        
    filename = f"user_{request.user_id}.{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    
    db.update_user_profile_pic(request.user_id, filename)
    flash("Profile picture updated successfully!", "success")
    return redirect(url_for("profile"))

# Change Password
@app.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    new_pass = request.form.get("new_password", "")
    confirm_pass = request.form.get("confirm_password", "")
    
    if len(new_pass) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("profile"))
        
    if new_pass != confirm_pass:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("profile"))
        
    hashed = generate_password_hash(new_pass)
    db.update_user_password(request.user_id, hashed)
    flash("Password updated successfully!", "success")
    return redirect(url_for("profile"))

# Save theme & language preferences
@app.route("/profile/preferences", methods=["POST"])
@login_required
def update_preferences():
    theme = request.form.get("theme", "light")
    language = request.form.get("language", "en")
    
    db.update_user_settings(request.user_id, theme, language)
    flash("Preferences saved successfully!", "success")
    return redirect(url_for("profile"))


# ----------------------------------------------------
# AI Symptom Analyzer & Chat Engine
# ----------------------------------------------------

def query_gemini_api(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text_response = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_response)
    except Exception as e:
        print(f"Gemini API Query Failed: {e}")
        return None

def local_fallback_symptom_analysis(symptoms, age, gender, duration, existing_conditions, weight=None, height=None, pain_level=None, allergies=None, current_medications=None, pregnancy_status=None, temperature=None, temperature_unit=None):
    # Fetch all knowledge entries
    all_knowledge = db.get_relevant_knowledge(symptoms)
    
    scored_conditions = []
    symptoms_lower = symptoms.lower()
    
    # Determine if patient has high fever
    is_high_fever = False
    if temperature:
        try:
            temp_val = float(temperature)
            unit = (temperature_unit or "F").upper()
            if unit == "C":
                if temp_val >= 38.4:
                    is_high_fever = True
            else: # Fahrenheit
                if temp_val >= 101.0:
                    is_high_fever = True
        except ValueError:
            pass

    for item in all_knowledge:
        score = 0
        matching_words = []
        cond_name_lower = item["condition_name"].lower()
        
        # Check condition name matches
        if cond_name_lower in symptoms_lower:
            score += 4
        
        # Split symptom keywords and check overlap
        keywords = [kw.strip().lower() for kw in item["symptoms"].split(",") if kw.strip()]
        for kw in keywords:
            if kw in symptoms_lower:
                score += 3
                matching_words.append(kw)
        
        # Check description matches
        desc_words = [dw.strip().lower() for dw in item["description"].split() if len(dw) > 4]
        for dw in desc_words:
            if dw in symptoms_lower:
                score += 1
        
        # Clinical adjustments based on exact temperature & symptoms
        if is_high_fever:
            if cond_name_lower == "malaria":
                score += 4 # Boost for high fever
                # Check for chills/sweats/shaking
                if any(w in symptoms_lower for w in ["chills", "shak", "sweat", "cycl"]):
                    score += 5
                    matching_words.append("high fever with chills/sweating")
            elif cond_name_lower == "dengue":
                score += 4 # Boost for high fever
                # Check for joint pain / retro-orbital pain / rash
                if any(w in symptoms_lower for w in ["joint", "bone", "retro", "eye", "rash"]):
                    score += 5
                    matching_words.append("high fever with joint pain/rash")
            elif cond_name_lower == "typhoid":
                score += 4 # Boost for high fever
                # Check for abdominal pain / rose spots / weakness
                if any(w in symptoms_lower for w in ["stomach", "abdom", "rose", "weak"]):
                    score += 5
                    matching_words.append("high fever with abdominal symptoms")
            elif cond_name_lower == "common cold":
                score -= 6 # Reduce score: cold rarely has high fever
            elif cond_name_lower == "tension headache":
                score -= 5 # Reduce score: tension headache doesn't cause high fever
        else:
            # If no high fever is reported but it's a malaria/dengue/typhoid check, reduce score slightly
            if cond_name_lower in ["malaria", "dengue", "typhoid"]:
                score -= 3
                
        # Set confidence based on score
        confidence = 50 + min(score * 8, 45)
        
        scored_conditions.append({
            "name": item["condition_name"],
            "score": confidence,
            "supporting_symptoms": f"Matches symptoms: {', '.join(matching_words) if matching_words else 'General description overlap'}.",
            "item": item
        })
        
    # Sort by score descending
    scored_conditions.sort(key=lambda x: x["score"], reverse=True)
    top_3 = scored_conditions[:3]
    
    # Pad if less than 3
    if len(top_3) < 3:
        all_items = db.get_all_medical_knowledge()
        for item in all_items:
            if len(top_3) >= 3:
                break
            if not any(x["name"] == item["condition_name"] for x in top_3):
                top_3.append({
                    "name": item["condition_name"],
                    "score": 40,
                    "supporting_symptoms": "Secondary differential possibility.",
                    "item": item
                })
                
    primary = top_3[0]["item"]
    
    # Red Flag Detection
    red_flag_detected = 0
    emergency_keywords = ["chest pain", "sweating", "difficulty breathing", "breathlessness", "loss of consciousness", "drooping", "slurred speech", "numbness", "hives", "anaphylaxis", "severe allergic"]
    if any(ek in symptoms_lower for ek in emergency_keywords) or primary["severity"] == "Severe" or (pain_level and pain_level >= 8):
        red_flag_detected = 1
        
    return {
        "condition_name": primary["condition_name"],
        "explanation": primary["description"],
        "severity": primary["severity"],
        "recommended_specialty": primary["recommended_department"],
        "health_advice": primary["home_care_advice"],
        "red_flag_detected": red_flag_detected,
        "confidence_scores": [{ "name": x["name"], "score": x["score"], "supporting_symptoms": x["supporting_symptoms"] } for x in top_3],
        "medical_references": json.loads(primary["medical_references"]) if primary["medical_references"] else []
    }

def analyze_symptoms(symptoms, age, gender, duration, existing_conditions, weight=None, height=None, pain_level=None, allergies=None, current_medications=None, pregnancy_status=None, lang="en", temperature=None, temperature_unit=None):
    # 1. Retrieve relevant records from local Knowledge Base
    relevant_knowledge = db.get_relevant_knowledge(symptoms)
    knowledge_context = []
    for item in relevant_knowledge:
        knowledge_context.append({
            "condition_name": item["condition_name"],
            "description": item["description"],
            "symptoms": item["symptoms"].split(","),
            "severity": item["severity"],
            "recommended_department": item["recommended_department"],
            "home_care_advice": item["home_care_advice"],
            "medical_references": json.loads(item["medical_references"]) if item["medical_references"] else [],
            "red_flags": json.loads(item["red_flags"]) if item["red_flags"] else []
        })

    # 2. Build Gemini prompt
    prompt = f"""
    You are a professional clinical decision-support AI assistant.
    Analyze the following patient case and match it against the retrieved medical knowledge base.
    
    PATIENT CASE:
    - Age: {age}
    - Gender: {gender}
    - Weight: {weight or 'Not Provided'} kg
    - Height: {height or 'Not Provided'} cm
    - Body Temperature: {f"{temperature}°{temperature_unit}" if temperature else 'Not Provided'}
    - Pain Level: {pain_level or 'Not Provided'}/10
    - Duration of Symptoms: {duration}
    - Reported Symptoms/Description: {symptoms}
    - Existing Diseases: {existing_conditions or 'None'}
    - Current Medications: {current_medications or 'None'}
    - Allergies: {allergies or 'None'}
    - Pregnancy Status: {pregnancy_status or 'Not Applicable'}
    
    RETRIEVED MEDICAL KNOWLEDGE CONTEXT:
    {json.dumps(knowledge_context, indent=2)}
    
    CLINICAL RULES:
    1. Pay extremely close attention to the Body Temperature:
       - High fever (>= 101°F / 38.4°C) should strongly point to Malaria, Dengue, or Typhoid if other symptoms line up.
       - Dengue is highly characterized by sudden high fever, retro-orbital pain (pain behind eyes), severe joint/muscle aches ("breakbone fever"), and skin rash.
       - Malaria is highly characterized by cyclic high fever spikes with shaking chills, sweating, and severe headache.
       - Typhoid is characterized by sustained step-ladder high fever, abdominal/stomach pain, extreme weakness, and rose spots rash on the trunk.
       - Do NOT diagnose these cases as simple Influenza or Common Cold if they have characteristic symptoms of Dengue (like retro-orbital pain, joint/bone pain), Malaria (like cyclic shaking chills), or Typhoid (like abdominal pain with persistent high fever).
    
    TASK:
    1. Perform clinical reasoning and determine the top 3 possible conditions based on the symptoms and retrieved medical facts.
    2. Assess severity (Mild, Moderate, Severe).
    3. Detect if any emergency situation (Red Flag) is present (e.g., chest pain + sweating, severe difficulty breathing, loss of consciousness, stroke signs, severe allergic swelling, or severe dengue warnings).
    4. Provide home-care advice (safe general advice ONLY for mild conditions; NEVER recommend prescription medicines).
    5. Formulate supporting symptoms explanations for each condition showing why it matches the patient symptoms.
    6. Include trusted medical references from the knowledge base (e.g. WHO, CDC, NHS, MedlinePlus) that support this analysis.
    
    You MUST respond in JSON format ONLY. Do not wrap in markdown blocks, do not output any surrounding text. Use exactly this JSON structure:
    {{
      "condition_name": "Primary possible condition",
      "explanation": "Brief explanation of the primary condition and why it fits.",
      "severity": "Mild/Moderate/Severe",
      "recommended_specialty": "Department name",
      "health_advice": "Detailed self-care and home advice.",
      "red_flag_detected": 0 or 1,
      "confidence_scores": [
        {{ "name": "Condition 1", "score": 85, "supporting_symptoms": "Why it matches" }},
        {{ "name": "Condition 2", "score": 60, "supporting_symptoms": "Why it matches" }},
        {{ "name": "Condition 3", "score": 45, "supporting_symptoms": "Why it matches" }}
      ],
      "medical_references": ["WHO Guidelines...", "CDC reference..."]
    }}
    """
    
    # 3. Call Gemini
    assessment = query_gemini_api(prompt)
    if not assessment:
        print("Gemini API not available. Using local rule-based clinical scoring engine fallback.")
        assessment = local_fallback_symptom_analysis(symptoms, age, gender, duration, existing_conditions, weight, height, pain_level, allergies, current_medications, pregnancy_status, temperature, temperature_unit)

    # 4. Multi-language translation maps
    translations = {
        "es": {
            "Mild": "Leve",
            "Moderate": "Moderado",
            "Severe": "Severo"
        },
        "fr": {
            "Mild": "Léger",
            "Moderate": "Modéré",
            "Severe": "Grave"
        },
        "de": {
            "Mild": "Leicht",
            "Moderate": "Mittelschwer",
            "Severe": "Schwer"
        },
        "hi": {
            "Mild": "हल्का (माइल्ड)",
            "Moderate": "मध्यम (मॉडरेट)",
            "Severe": "गंभीर (सिवियर)"
        }
    }

    if lang in translations:
        lang_map = translations[lang]
        assessment["severity"] = lang_map.get(assessment["severity"], assessment["severity"])

    return assessment


def generate_chat_reply(message, assessment, chat_messages, lang="en"):
    msg = message.lower()
    
    # Check if this message indicates a new symptom
    symptom_keywords = ["vomit", "fever", "cough", "throat", "headache", "dizzy", "pain", "rash", "itch", "breathing", "nausea", "chill"]
    is_new_symptom = any(sk in msg for sk in symptom_keywords) and not any(sk in assessment["symptoms"].lower() for sk in symptom_keywords)
    
    if is_new_symptom:
        # Re-run symptom checker combining old symptoms and new message
        combined_symptoms = f"{assessment['symptoms']} (Additional symptom noted: {message})"
        print(f"Chat Memory: Re-analyzing with combined symptoms: {combined_symptoms}")
        
        # Analyze
        updated = analyze_symptoms(
            symptoms=combined_symptoms,
            age=assessment["age"],
            gender=assessment["gender"],
            duration=assessment["duration"],
            existing_conditions=assessment["existing_conditions"],
            weight=assessment.get("weight"),
            height=assessment.get("height"),
            pain_level=assessment.get("pain_level"),
            allergies=assessment.get("allergies"),
            current_medications=assessment.get("current_medications"),
            pregnancy_status=assessment.get("pregnancy_status"),
            lang=lang
        )
        
        # Format updated response
        alert_str = "⚠️ ALERT: A red flag condition has been detected! Please seek immediate emergency medical care." if updated.get("red_flag_detected") else ""
        
        reply = f"Thank you for sharing. Based on the new symptom details you mentioned ('{message}'), I have updated your assessment:\n\n"
        reply += f"- **Updated Condition**: {updated['condition_name']}\n"
        reply += f"- **Updated Severity**: {updated['severity']}\n"
        reply += f"- **Recommended Department**: {updated['recommended_specialty']}\n"
        reply += f"- **Home Care Advice**: {updated['health_advice']}\n\n"
        
        if updated.get("confidence_scores"):
            reply += "**Differential Conditions**:\n"
            for x in updated["confidence_scores"][:3]:
                reply += f"- {x['name']} ({x['score']}%)\n"
                
        if alert_str:
            reply += f"\n{alert_str}"
            
        return reply

    # 1. Gemini Chat Reply
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        history_formatted = []
        for c in chat_messages[-5:]:
            history_formatted.append(f"{c['sender'].upper()}: {c['message']}")
            
        chat_prompt = f"""
        You are Dooper Doctor AI, a clinical chat assistant.
        The user has previously completed a clinical symptom check:
        - Diagnosis: {assessment['condition_name']}
        - Recommended Department: {assessment['recommended_specialty']}
        - Current Symptoms: {assessment['symptoms']}
        
        Here is the chat history:
        {chr(10).join(history_formatted)}
        
        USER NEW MESSAGE:
        {message}
        
        Answer their question professionally in the context of their symptoms and diagnosis.
        Do not diagnose new conditions or recommend prescription drugs. Offer safe, general home-care advice.
        Keep the response brief (1-3 sentences).
        """
        response_json = query_gemini_api(chat_prompt)
        if response_json and isinstance(response_json, dict) and "text" in response_json:
            return response_json["text"]
        elif response_json and isinstance(response_json, str):
            return response_json
            
    # 2. Local Fallback Chat Reply
    replies = {
        "en": {
            "hello": "Hello! I am here to help you understand your symptoms. How can I assist you further?",
            "thanks": "You're very welcome! Keep monitoring your health and get plenty of rest.",
            "thank you": "You're welcome! Dooper is always here for your healthcare support.",
            "appointment": f"Since the recommended specialty is {assessment['recommended_specialty']}, I recommend calling a local clinic to consult a licensed {assessment['recommended_specialty']}.",
            "doctor": f"Consulting a licensed {assessment['recommended_specialty']} will provide a definitive diagnosis. If you wish to book, look for verified {assessment['recommended_specialty']} clinics in your area.",
            "worse": "If your symptoms get worse, please go to the nearest urgent care center or clinic immediately.",
            "medicine": "I cannot prescribe specific prescription drugs. Over-the-counter pain relief can help with fever or pain, but please consult a pharmacist or doctor first.",
            "default": f"Based on your check for '{assessment['condition_name']}', it is recommended to get rest and consult a specialized {assessment['recommended_specialty']} if symptoms don't resolve."
        }
    }
    
    lang_replies = replies.get(lang, replies["en"])
    
    if "hello" in msg or "hi" in msg or "hey" in msg:
        return lang_replies["hello"]
    elif "thank you" in msg:
        return lang_replies["thank you"]
    elif "thanks" in msg or "thank" in msg:
        return lang_replies["thanks"]
    elif "appointment" in msg or "book" in msg or "schedule" in msg or "meet" in msg or "see" in msg:
        return lang_replies["appointment"]
    elif "doctor" in msg or "specialist" in msg:
        return lang_replies["doctor"]
    elif "worse" in msg or "bad" in msg or "emergency" in msg or "painful" in msg:
        return lang_replies["worse"]
    elif "medicine" in msg or "drug" in msg or "pill" in msg or "tablet" in msg or "cure" in msg:
        return lang_replies["medicine"]
    
    return lang_replies["default"]


def detect_emergency_keywords(text, pain_level=None, pregnancy_status=None):
    text_lower = text.lower()
    emergencies = [
        "chest pain", "pressure in chest", "sweating", "difficulty breathing",
        "breathlessness", "shortness of breath", "stroke", "drooping",
        "slurred speech", "numbness", "arm weakness", "uncontrolled bleeding",
        "loss of consciousness", "passed out", "fainting", "anaphylaxis",
        "lips swelling", "tongue swelling", "throat swelling"
    ]
    if any(e in text_lower for e in emergencies):
        return True
    if pain_level and int(pain_level) >= 9:
        return True
    if pregnancy_status and pregnancy_status.strip().lower() not in ["", "no", "n/a", "none", "not pregnant"]:
        if any(w in text_lower for w in ["bleed", "cramp", "severe pain", "contraction"]):
            return True
    return False

def generate_structured_report_ai(c, chat_history, rag_context):
    api_key = os.environ.get("GEMINI_API_KEY")
    prompt = f"""
    You are a professional clinical decision-support AI.
    Analyze the patient consultation session and provide a structured clinical assessment.
    
    PATIENT CASE:
    - Age: {c["age"]}
    - Gender: {c["gender"]}
    - Weight: {c.get("weight") or "Not Provided"} kg
    - Height: {c.get("height") or "Not Provided"} cm
    - Temperature: {c.get("temperature") or "Not Provided"} {c.get("temperature_unit") or "F"}
    - Pain Level: {c.get("pain_level") or "Not Provided"}/10
    - Existing Conditions: {c.get("existing_conditions") or "None"}
    - Allergies: {c.get("allergies") or "None"}
    - Medications: {c.get("current_medications") or "None"}
    - Pregnancy Status: {c.get("pregnancy_status") or "Not Applicable"}
    - Initial Symptoms: {c["symptoms"]}
    
    CONSULTATION CHAT HISTORY:
    {json.dumps([{"sender": m["sender"], "message": m["message"]} for m in chat_history], indent=2)}
    
    TRUSTED MEDICAL KNOWLEDGE BASE:
    {json.dumps(rag_context, indent=2)}
    
    TASK:
    1. Formulate the Differential Diagnosis (Top 5 possible conditions).
       For each, provide: name, probability_score (0-100), matching_symptoms (list), missing_symptoms (list), reasoning.
    2. Determine the overall Severity Level (Mild, Moderate, or Severe).
    3. Choose the most appropriate Recommended Specialist from the following:
       [General Physician, Emergency Medicine, Cardiologist, Neurologist, Pulmonologist, Gastroenterologist, Dermatologist, ENT Specialist, Gynecologist, Orthopedic Surgeon].
       Provide the specialist name and a clear explanation of why they are recommended.
    4. Provide Home Care Advice (first aid, rest, hydration, warning signs when to seek immediate care. NEVER recommend prescription drugs).
    5. List supporting Medical References from the knowledge base (e.g. CDC, WHO, NHS guidelines).
    
    You MUST respond in JSON format ONLY. Do not wrap in markdown blocks, do not output any surrounding text. Use exactly this JSON structure:
    {{
      "severity": "Mild/Moderate/Severe",
      "primary_condition": {{
        "name": "Condition Name",
        "reasoning": "Why this is primary"
      }},
      "differential_diagnosis": [
        {{ "name": "Condition 1", "probability_score": 85, "matching_symptoms": ["symptom A", "symptom B"], "missing_symptoms": ["symptom C"], "reasoning": "Matches..." }},
        {{ "name": "Condition 2", "probability_score": 60, "matching_symptoms": ["symptom A"], "missing_symptoms": ["symptom B"], "reasoning": "..." }},
        {{ "name": "Condition 3", "probability_score": 40, "matching_symptoms": [], "missing_symptoms": ["symptom A"], "reasoning": "..." }},
        {{ "name": "Condition 4", "probability_score": 25, "matching_symptoms": [], "missing_symptoms": ["symptom B"], "reasoning": "..." }},
        {{ "name": "Condition 5", "probability_score": 15, "matching_symptoms": [], "missing_symptoms": ["symptom C"], "reasoning": "..." }}
      ],
      "recommended_specialist": {{
        "name": "Specialist Department Name",
        "explanation": "Why this specialist is selected"
      }},
      "home_care_advice": "Detailed self-care instructions...",
      "medical_references": ["WHO Guidelines...", "CDC reference..."]
    }}
    """
    
    if api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=12) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                text_response = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text_response)
        except Exception as e:
            print(f"Gemini API Call Failed: {e}")
            
    # Fallback to local calculations
    diff = []
    for item in rag_context[:5]:
        diff.append({
            "name": item["condition_name"],
            "probability_score": item["probability_score"],
            "matching_symptoms": item["matching_symptoms"],
            "missing_symptoms": item["missing_symptoms"],
            "reasoning": item["reasoning"]
        })
    
    primary = diff[0] if diff else {"name": "General Illness", "reasoning": "Symptoms match a general systemic overlap."}
    severity = rag_context[0]["severity"] if rag_context else "Moderate"
    specialist = rag_context[0]["recommended_department"] if rag_context else "General Physician"
    home_care = rag_context[0]["home_care_advice"] if rag_context else "Rest and monitor symptoms."
    refs = rag_context[0]["medical_references"] if rag_context else ["WHO Guidelines", "CDC Guidelines"]
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except Exception:
            refs = [refs]

    return {
        "severity": severity,
        "primary_condition": {
            "name": primary["name"],
            "reasoning": primary["reasoning"]
        },
        "differential_diagnosis": diff,
        "recommended_specialist": {
            "name": specialist,
            "explanation": f"Recommended department based on suspected condition {primary['name']}."
        },
        "home_care_advice": home_care,
        "medical_references": refs
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000)
