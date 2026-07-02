from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import database as db
import os
import re
from functools import wraps

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

        if not symptoms or not age or not gender or not duration:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("dashboard"))

        # Perform Symptom Analysis based on language
        settings = db.get_user_settings(request.user_id)
        lang = settings["language"] if settings else "en"

        assessment = analyze_symptoms(symptoms, age, gender, duration, existing_conditions, lang)
        
        # Save to database
        assessment_id = db.create_assessment(
            user_id=request.user_id,
            symptoms=symptoms,
            age=int(age),
            gender=gender,
            duration=duration,
            existing_conditions=existing_conditions or None,
            condition_name=assessment["condition_name"],
            explanation=assessment["explanation"],
            severity=assessment["severity"],
            recommended_specialty=assessment["recommended_specialty"],
            health_advice=assessment["health_advice"]
        )

        if assessment_id:
            flash("Symptoms analyzed successfully by Dooper AI!", "success")
            return redirect(url_for("assessment_detail", assessment_id=assessment_id))
        else:
            flash("Failed to save assessment. Please try again.", "danger")
            return redirect(url_for("dashboard"))

    recent = db.get_assessments_by_user(request.user_id)
    stats = db.get_dashboard_stats(request.user_id)
    
    return render_template("dashboard.html", recent_assessments=recent, stats=stats)

# Assessment detail view
@app.route("/assessment/<int:assessment_id>")
@login_required
def assessment_detail(assessment_id):
    assessment = db.get_assessment_by_id(assessment_id, request.user_id)
    if not assessment:
        flash("Record not found or unauthorized.", "danger")
        return redirect(url_for("dashboard"))
        
    chat_messages = db.get_chat_messages(assessment_id)
    return render_template("assessment_detail.html", assessment=assessment, chat_messages=chat_messages)

# Assessment chat webhook
@app.route("/assessment/<int:assessment_id>/chat", methods=["POST"])
@login_required
def assessment_chat(assessment_id):
    assessment = db.get_assessment_by_id(assessment_id, request.user_id)
    if not assessment:
        return jsonify({"status": "error", "message": "Record not found"}), 404
        
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"status": "error", "message": "Empty message"}), 400
        
    # Store user message
    db.add_chat_message(assessment_id, "user", user_message)
    
    # Generate contextual chat reply based on preference language
    settings = db.get_user_settings(request.user_id)
    lang = settings["language"] if settings else "en"
    
    reply = generate_chat_reply(user_message, assessment["condition_name"], assessment["recommended_specialty"], lang)
    
    # Store AI message
    db.add_chat_message(assessment_id, "ai", reply)
    
    return jsonify({"status": "success", "reply": reply})

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
def analyze_symptoms(symptoms, age, gender, duration, conditions, lang="en"):
    s_lower = symptoms.lower()
    
    # Defaults
    condition = "General Malaise"
    explanation = "You are experiencing non-specific symptoms that suggest general bodily fatigue. Rest and hydration are advised."
    severity = "Mild"
    specialty = "General Physician"
    advice = "Maintain good hydration, rest, and monitor your body temperature. If symptoms worsen, schedule a visit with a doctor."
    
    # 1. Cardiovascular / Chest Pain
    if "chest pain" in s_lower or "shortness of breath" in s_lower or "heart racing" in s_lower or "tightness" in s_lower:
        condition = "Cardiovascular Concern"
        explanation = "The description of chest pressure, racing pulse, or shortness of breath points to possible cardiovascular strain or cardiac discomfort."
        severity = "Severe"
        specialty = "Cardiologist"
        advice = "Please sit down, rest, avoid physical exertion, and prepare to seek immediate emergency care if chest pressure worsens."
        
    # 2. Flu / Virus / Fever
    elif "fever" in s_lower or "chills" in s_lower or "body ache" in s_lower or "cough" in s_lower:
        if "sore throat" in s_lower or "runny nose" in s_lower:
            condition = "Common Cold"
            explanation = "Symptoms such as runny nose and throat irritation indicate a viral upper respiratory infection, commonly referred to as the cold."
            severity = "Mild"
            specialty = "General Physician"
            advice = "Inhale steam, drink warm teas, rinse your throat with salt water, and take rest."
        else:
            condition = "Viral Fever"
            explanation = "Elevated temperature and bodily aches are typical indicator signs of a systemic viral infection."
            severity = "Moderate"
            specialty = "General Physician"
            advice = "Keep track of your temperature, consume light meals, stay well hydrated, and rest."

    # 3. Migraine / Headache
    elif "headache" in s_lower or "migraine" in s_lower or "throbbing" in s_lower:
        condition = "Migraine Episode"
        explanation = "Unilateral throbbing head pain, often accompanied by sensitivity to sound or light, is highly suggestive of a migraine headache."
        severity = "Moderate"
        specialty = "Neurologist"
        advice = "Lie down in a quiet, dark room, place a cool compress on your forehead, and drink water."
        
    # 4. Dermatological / Rash
    elif "rash" in s_lower or "itch" in s_lower or "skin" in s_lower or "redness" in s_lower:
        condition = "Contact Dermatitis / Skin Allergy"
        explanation = "A localized rash or skin redness typically represents an allergic reaction or dermal inflammation."
        severity = "Mild"
        specialty = "Dermatologist"
        advice = "Avoid scratching the area, apply a soothing calamine lotion, and avoid contact with potential skin irritants."

    # 5. Gastric / Stomach
    elif "stomach" in s_lower or "acid" in s_lower or "heartburn" in s_lower or "vomit" in s_lower or "gastric" in s_lower:
        condition = "Acute Gastritis / Acid Reflux"
        explanation = "Burning chest or abdominal sensations point towards excess stomach acid production or esophageal lining irritation."
        severity = "Mild"
        specialty = "Gastroenterologist"
        advice = "Avoid spicy or fatty foods, eat small and frequent meals, and avoid lying down immediately after eating."

    # 6. Joint / Bone / Muscular
    elif "joint" in s_lower or "bone" in s_lower or "muscle pain" in s_lower or "fracture" in s_lower or "sprain" in s_lower:
        condition = "Musculoskeletal Sprain / Inflammation"
        explanation = "Local joint tenderness or muscle strain typically stems from minor injury or inflammatory stress."
        severity = "Moderate"
        specialty = "Orthopedic"
        advice = "Apply the R.I.C.E protocol (Rest, Ice, Compression, Elevation) to the affected body part."

    # Multi-language translation maps
    translations = {
        "es": {
            "General Malaise": "Malestar General",
            "Cardiovascular Concern": "Preocupación Cardiovascular",
            "Common Cold": "Resfriado Común",
            "Viral Fever": "Fiebre Viral",
            "Migraine Episode": "Episodio de Migraña",
            "Contact Dermatitis / Skin Allergy": "Dermatitis por Contacto / Alergia en la Piel",
            "Acute Gastritis / Acid Reflux": "Gastritis Aguda / Reflujo Ácido",
            "Musculoskeletal Sprain / Inflammation": "Esguince Musculoesquelético / Inflamación",
            "General Physician": "Médico General",
            "Cardiologist": "Cardiólogo",
            "Neurologist": "Neurólogo",
            "Dermatologist": "Dermatólogo",
            "Gastroenterologist": "Gastroenterólogo",
            "Orthopedic": "Ortopedista",
            "Mild": "Leve",
            "Moderate": "Moderado",
            "Severe": "Severo",
            "You are experiencing non-specific symptoms that suggest general bodily fatigue. Rest and hydration are advised.": "Está experimentando síntomas no específicos que sugieren fatiga corporal general. Se aconseja reposo e hidratación.",
            "Maintain good hydration, rest, and monitor your body temperature. If symptoms worsen, schedule a visit with a doctor.": "Mantenga una buena hidratación, descanse y controle su temperatura corporal. Si los síntomas empeoran, programe una visita con el médico.",
            "The description of chest pressure, racing pulse, or shortness of breath points to possible cardiovascular strain or cardiac discomfort.": "La descripción de presión en el pecho, pulso acelerado o dificultad para respirar apunta a una posible tensión cardiovascular o malestar cardíaco.",
            "Please sit down, rest, avoid physical exertion, and prepare to seek immediate emergency care if chest pressure worsens.": "Por favor, siéntese, descanse, evite el esfuerzo físico y prepárese para buscar atención de emergencia inmediata si la presión en el pecho empeora.",
            "Symptoms such as runny nose and throat irritation indicate a viral upper respiratory infection, commonly referred to as the cold.": "Los síntomas como secreción nasal e irritación de la garganta indican una infección viral de las vías respiratorias superiores, comúnmente conocida como resfriado.",
            "Inhale steam, drink warm teas, rinse your throat with salt water, and take rest.": "Inhale vapor, beba tés calientes, enjuáguese la garganta con agua tibia con sal y descanse.",
            "Elevated temperature and bodily aches are typical indicator signs of a systemic viral infection.": "La temperatura elevada y los dolores corporales son signos indicadores típicos de una infección viral sistémica.",
            "Keep track of your temperature, consume light meals, stay well hydrated, and rest.": "Lleve un registro de su temperatura, consuma comidas ligeras, manténgase bien hidratado y descanse.",
            "Unilateral throbbing head pain, often accompanied by sensitivity to sound or light, is highly suggestive of a migraine headache.": "El dolor de cabeza pulsante unilateral, a menudo acompañado de sensibilidad al sonido o a la luz, es muy sugerente de una migraña.",
            "Lie down in a quiet, dark room, place a cool compress on your forehead, and drink water.": "Acuéstese en una habitación tranquila y oscura, colóquese una compresa fría en la frente y beba agua.",
            "A localized rash or skin redness typically represents an allergic reaction or dermal inflammation.": "Una erupción localizada o enrojecimiento de la piel generalmente representa una reacción alérgica o inflamación dérmica.",
            "Avoid scratching the area, apply a soothing calamine lotion, and avoid contact with potential skin irritants.": "Evite rascarse el área, aplique una loción de calamina calmante y evite el contacto con posibles irritantes de la piel.",
            "Burning chest or abdominal sensations point towards excess stomach acid production or esophageal lining irritation.": "Las sensaciones de ardor en el pecho o en el abdomen apuntan a una producción excesiva de ácido estomacal o irritación del revestimiento esofágico.",
            "Avoid spicy or fatty foods, eat small and frequent meals, and avoid lying down immediately after eating.": "Evite los alimentos picantes o grasos, coma porciones pequeñas y frecuentes, y evite acostarse inmediatamente después de comer.",
            "Local joint tenderness or muscle strain typically stems from minor injury or inflammatory stress.": "La sensibilidad articular local o la distensión muscular generalmente se deben a una lesión menor o al estrés inflamatorio.",
            "Apply the R.I.C.E protocol (Rest, Ice, Compression, Elevation) to the affected body part.": "Aplique el protocolo R.I.C.E (Reposo, Hielo, Compresión, Elevación) en la parte del cuerpo afectada."
        },
        "fr": {
            "General Malaise": "Malaise Général",
            "Cardiovascular Concern": "Problème Cardiovasculaire",
            "Common Cold": "Rhume",
            "Viral Fever": "Fièvre Virale",
            "Migraine Episode": "Crise de Migraine",
            "Contact Dermatitis / Skin Allergy": "Dermatite de Contact / Allergie Cutanée",
            "Acute Gastritis / Acid Reflux": "Gastrite Aiguë / Reflux Acide",
            "Musculoskeletal Sprain / Inflammation": "Entorse / Inflammation Musculo-squelettique",
            "General Physician": "Médecin Généraliste",
            "Cardiologist": "Cardiologue",
            "Neurologist": "Neurologue",
            "Dermatologist": "Dermatologue",
            "Gastroenterologist": "Gastro-entérologue",
            "Orthopedic": "Orthopédiste",
            "Mild": "Léger",
            "Moderate": "Modéré",
            "Severe": "Grave",
            "You are experiencing non-specific symptoms that suggest general bodily fatigue. Rest and hydration are advised.": "Vous présentez des symptômes non spécifiques suggérant une fatigue corporelle générale. Le repos et l'hydratation sont conseillés.",
            "Maintain good hydration, rest, and monitor your body temperature. If symptoms worsen, schedule a visit with a doctor.": "Maintenez une bonne hydratation, reposez-vous et surveillez votre température corporelle. Si les symptômes s'aggravent, prenez rendez-vous avec un médecin.",
            "The description of chest pressure, racing pulse, or shortness of breath points to possible cardiovascular strain or cardiac discomfort.": "La description d'une pression thoracique, d'un pouls rapide ou d'un essoufflement indique une fatigue cardiovasculaire possible.",
            "Please sit down, rest, avoid physical exertion, and prepare to seek immediate emergency care if chest pressure worsens.": "Asseyez-vous, reposez-vous, évitez tout effort physique et préparez-vous à appeler les urgences si la pression s'aggrave.",
            "Symptoms such as runny nose and throat irritation indicate a viral upper respiratory infection, commonly referred to as the cold.": "Le nez qui coule et les maux de gorge indiquent une infection virale des voies respiratoires supérieures (rhume).",
            "Inhale steam, drink warm teas, rinse your throat with salt water, and take rest.": "Inhalez de la vapeur, buvez des infusions chaudes, gargarisez-vous à l'eau salée et reposez-vous.",
            "Elevated temperature and bodily aches are typical indicator signs of a systemic viral infection.": "Une température élevée et des courbatures sont des signes typiques d'une infection virale systémique.",
            "Keep track of your temperature, consume light meals, stay well hydrated, and rest.": "Surveillez votre température, mangez léger, hydratez-vous bien et reposez-vous.",
            "Unilateral throbbing head pain, often accompanied by sensitivity to sound or light, is highly suggestive of a migraine headache.": "Un mal de tête lancinant unilatéral, souvent sensible au bruit ou à la lumière, suggère fortement une migraine.",
            "Lie down in a quiet, dark room, place a cool compress on your forehead, and drink water.": "Allongez-vous dans une pièce calme et sombre, appliquez une compresse froide sur votre front et buvez de l'eau.",
            "A localized rash or skin redness typically represents an allergic reaction or dermal inflammation.": "Une éruption cutanée localisée ou des rougeurs représentent généralement une réaction allergique ou cutanée.",
            "Avoid scratching the area, apply a soothing calamine lotion, and avoid contact with potential skin irritants.": "Évitez de vous gratter, appliquez de la calamine et évitez les produits irritants.",
            "Burning chest or abdominal sensations point towards excess stomach acid production or esophageal lining irritation.": "Les brûlures d'estomac ou sensations d'acidité suggèrent un reflux acide.",
            "Avoid spicy or fatty foods, eat small and frequent meals, and avoid lying down immediately after eating.": "Évitez les plats épicés/gras, fractionnez vos repas et ne vous allongez pas juste après manger.",
            "Local joint tenderness or muscle strain typically stems from minor injury or inflammatory stress.": "Une douleur articulaire locale ou une fatigue musculaire provient généralement d'une blessure mineure.",
            "Apply the R.I.C.E protocol (Rest, Ice, Compression, Elevation) to the affected body part.": "Appliquez le protocole R.I.C.E. (Repos, Glace, Compression, Élévation) sur la zone affectée."
        },
        "de": {
            "General Malaise": "Allgemeines Unwohlsein",
            "Cardiovascular Concern": "Kardiovaskuläre Beschwerden",
            "Common Cold": "Erkältung",
            "Viral Fever": "Virales Fieber",
            "Migraine Episode": "Migräneanfall",
            "Contact Dermatitis / Skin Allergy": "Kontaktdermatitis / Hautallergie",
            "Acute Gastritis / Acid Reflux": "Akute Gastritis / Sodbrennen",
            "Musculoskeletal Sprain / Inflammation": "Verstauchung / Entzündung",
            "General Physician": "Allgemeinarzt",
            "Cardiologist": "Kardiologe",
            "Neurologist": "Neurologe",
            "Dermatologist": "Dermatologe",
            "Gastroenterologist": "Gastroenterologe",
            "Orthopedic": "Orthopäde",
            "Mild": "Leicht",
            "Moderate": "Mittelschwer",
            "Severe": "Schwer",
            "You are experiencing non-specific symptoms that suggest general bodily fatigue. Rest and hydration are advised.": "Sie haben unspezifische Symptome, die auf allgemeine Müdigkeit hindeuten. Ruhe und Flüssigkeit werden empfohlen.",
            "Maintain good hydration, rest, and monitor your body temperature. If symptoms worsen, schedule a visit with a doctor.": "Trinken Sie ausreichend, ruhen Sie sich aus und überwachen Sie das Fieber. Bei Verschlechterung zum Arzt gehen.",
            "The description of chest pressure, racing pulse, or shortness of breath points to possible cardiovascular strain or cardiac discomfort.": "Engegefühl in der Brust, Herzrasen oder Atemnot deuten auf mögliche Herz-Kreislauf-Probleme hin.",
            "Please sit down, rest, avoid physical exertion, and prepare to seek immediate emergency care if chest pressure worsens.": "Setzen Sie sich hin, schonen Sie sich und rufen Sie bei anhaltenden Brustschmerzen den Notruf.",
            "Symptoms such as runny nose and throat irritation indicate a viral upper respiratory infection, commonly referred to as the cold.": "Fließschnupfen und Halskratzen deuten auf einen viralen Infekt hin (Erkältung).",
            "Inhale steam, drink warm teas, rinse your throat with salt water, and take rest.": "Inhalieren Sie Dampf, trinken Sie warmen Tee, gurgeln Sie mit Salzwasser und schonen Sie sich.",
            "Elevated temperature and bodily aches are typical indicator signs of a systemic viral infection.": "Erhöhte Temperatur und Gliederschmerzen sind typische Zeichen einer Virusinfektion.",
            "Keep track of your temperature, consume light meals, stay well hydrated, and rest.": "Messen Sie regelmäßig Fieber, essen Sie leichte Kost, trinken Sie viel Wasser und ruhen Sie sich aus.",
            "Unilateral throbbing head pain, often accompanied by sensitivity to sound or light, is highly suggestive of a migraine headache.": "Einseitig pochende Kopfschmerzen mit Lichtempfindlichkeit deuten stark auf Migräne hin.",
            "Lie down in a quiet, dark room, place a cool compress on your forehead, and drink water.": "Legen Sie sich in einen dunklen Raum, nutzen Sie kalte Kompressen und trinken Sie viel Wasser.",
            "A localized rash or skin redness typically represents an allergic reaction or dermal inflammation.": "Lokaler Ausschlag oder Rötungen deuten auf eine allergische Hautreaktion hin.",
            "Avoid scratching the area, apply a soothing calamine lotion, and avoid contact with potential skin irritants.": "Nicht kratzen, tragen Sie beruhigende Lotion auf und vermeiden Sie Hautreizstoffe.",
            "Burning chest or abdominal sensations point towards excess stomach acid production or esophageal lining irritation.": "Brennen in Brust oder Magen deutet auf Sodbrennen oder Gastritis hin.",
            "Avoid spicy or fatty foods, eat small and frequent meals, and avoid lying down immediately after eating.": "Vermeiden Sie scharfes/fettiges Essen, essen Sie kleinere Portionen und legen Sie sich nicht direkt hin.",
            "Local joint tenderness or muscle strain typically stems from minor injury or inflammatory stress.": "Gelenkschmerz oder Zerrungen kommen meist von einer leichten Überlastung.",
            "Apply the R.I.C.E protocol (Rest, Ice, Compression, Elevation) to the affected body part.": "Nutzen Sie die PECH-Regel (Pause, Eis, Compression, Hochlagern) für das Gelenk."
        },
        "hi": {
            "General Malaise": "सामान्य अस्वस्थता",
            "Cardiovascular Concern": "हृदय संबंधी चिंता",
            "Common Cold": "सामान्य जुकाम",
            "Viral Fever": "वायरल बुखार",
            "Migraine Episode": "माइग्रेन का दौरा",
            "Contact Dermatitis / Skin Allergy": "त्वचा की एलर्जी / डर्मेटाइटिस",
            "Acute Gastritis / Acid Reflux": "गैस्ट्राइटिस / एसिड रिफ्लक्स",
            "Musculoskeletal Sprain / Inflammation": "मांसपेशियों में खिंचाव / मोच",
            "General Physician": "सामान्य चिकित्सक (जनरल फिजिशियन)",
            "Cardiologist": "हृदय रोग विशेषज्ञ (कार्डियोलॉजिस्ट)",
            "Neurologist": "न्यूरोलॉजिस्ट",
            "Dermatologist": "त्वचा रोग विशेषज्ञ (डर्मेटोलॉजिस्ट)",
            "Gastroenterologist": "पेट रोग विशेषज्ञ (गैस्ट्रोएंट्रोलॉजिस्ट)",
            "Orthopedic": "हड्डी रोग विशेषज्ञ (ऑर्थोपेडिक)",
            "Mild": "हल्का (माइल्ड)",
            "Moderate": "मध्यम (मॉडरेट)",
            "Severe": "गंभीर (सिवियर)",
            "You are experiencing non-specific symptoms that suggest general bodily fatigue. Rest and hydration are advised.": "आप सामान्य शारीरिक थकान के लक्षणों का अनुभव कर रहे हैं। आराम और पर्याप्त पानी पीने की सलाह दी जाती है।",
            "Maintain good hydration, rest, and monitor your body temperature. If symptoms worsen, schedule a visit with a doctor.": "पर्याप्त पानी पिएं, आराम करें और शरीर के तापमान की निगरानी करें। यदि लक्षण बिगड़ते हैं, तो डॉक्टर से मिलें।",
            "The description of chest pressure, racing pulse, or shortness of breath points to possible cardiovascular strain or cardiac discomfort.": "छाती में दबाव, तेज पल्स, या सांस लेने में तकलीफ की शिकायत हृदय संबंधी समस्या की ओर इशारा करती है।",
            "Please sit down, rest, avoid physical exertion, and prepare to seek immediate emergency care if chest pressure worsens.": "कृपया बैठें, आराम करें, शारीरिक मेहनत से बचें और छाती में दबाव बढ़ने पर तुरंत आपातकालीन चिकित्सा सहायता लें।",
            "Symptoms such as runny nose and throat irritation indicate a viral upper respiratory infection, commonly referred to as the cold.": "बहती नाक और गले में खराश ऊपरी श्वसन तंत्र के वायरल संक्रमण (जुकाम) के लक्षण हैं।",
            "Inhale steam, drink warm teas, rinse your throat with salt water, and take rest.": "भाप लें, गर्म चाय पिएं, नमक के गुनगुने पानी से गरारे करें और आराम करें।",
            "Elevated temperature and bodily aches are typical indicator signs of a systemic viral infection.": "शरीर का बढ़ा हुआ तापमान और बदन दर्द वायरल बुखार का संकेत हैं।",
            "Keep track of your temperature, consume light meals, stay well hydrated, and rest.": "तापमान रिकॉर्ड करते रहें, हल्का भोजन लें, खूब पानी पिएं और आराम करें।",
            "Unilateral throbbing head pain, often accompanied by sensitivity to sound or light, is highly suggestive of a migraine headache.": "सिर के एक तरफ तेज धड़कता हुआ दर्द, जिसके साथ आवाज या रोशनी से चिड़चिड़ापन होना माइग्रेन का लक्षण हो सकता है।",
            "Lie down in a quiet, dark room, place a cool compress on your forehead, and drink water.": "एक शांत, अंधेरे कमरे में लेट जाएं, माथे पर ठंडी पट्टी रखें और पानी पिएं।",
            "A localized rash or skin redness typically represents an allergic reaction or dermal inflammation.": "त्वचा पर लाल दाने या खुजली होना त्वचा की एलर्जी या सूजन का संकेत है।",
            "Avoid scratching the area, apply a soothing calamine lotion, and avoid contact with potential skin irritants.": "खुजली करने से बचें, कैलामाइन लोशन लगाएं, और त्वचा को नुकसान पहुंचाने वाले रसायनों से दूर रहें।",
            "Burning chest or abdominal sensations point towards excess stomach acid production or esophageal lining irritation.": "पेट में जलन या छाती में एसिड की अनुभूति एसिड रिफ्लक्स या गैस्ट्रिक समस्या का संकेत है।",
            "Avoid spicy or fatty foods, eat small and frequent meals, and avoid lying down immediately after eating.": "मसालेदार और वसायुक्त भोजन से बचें, थोड़ा-थोड़ा खाना कई बार में खाएं, और खाने के तुरंत बाद लेटने से बचें।",
            "Local joint tenderness or muscle strain typically stems from minor injury or inflammatory stress.": "जोड़ों में दर्द या मांसपेशियों का खिंचाव आमतौर पर मोच या सूजन के कारण होता है।",
            "Apply the R.I.C.E protocol (Rest, Ice, Compression, Elevation) to the affected body part.": "प्रभावित हिस्से पर आर.आई.सी.ई (आराम, बर्फ लगाना, पट्टी बांधना, ऊंचाई पर रखना) नियम का पालन करें।"
        }
    }

    # Translate if language requested and mapping exists
    if lang in translations:
        lang_map = translations[lang]
        condition = lang_map.get(condition, condition)
        explanation = lang_map.get(explanation, explanation)
        severity = lang_map.get(severity, severity)
        specialty = lang_map.get(specialty, specialty)
        advice = lang_map.get(advice, advice)

    return {
        "condition_name": condition,
        "explanation": explanation,
        "severity": severity,
        "recommended_specialty": specialty,
        "health_advice": advice
    }


def generate_chat_reply(message, condition, specialty, lang="en"):
    msg = message.lower()
    
    # Context replies
    replies = {
        "en": {
            "hello": "Hello! I am here to help you understand your symptoms. How can I assist you further?",
            "thanks": "You're very welcome! Keep monitoring your health and get plenty of rest.",
            "thank you": "You're welcome! Dooper is always here for your healthcare support.",
            "appointment": f"Since the recommended specialty is {specialty}, I recommend calling a local clinic to consult a licensed {specialty}.",
            "doctor": f"Consulting a licensed {specialty} will provide a definitive diagnosis. If you wish to book, look for verified {specialty} clinics in your area.",
            "worse": "If your symptoms get worse, please go to the nearest urgent care center or clinic immediately.",
            "medicine": "I cannot prescribe specific prescription drugs. Over-the-counter pain relief can help with fever or pain, but please consult a pharmacist or doctor first.",
            "default": f"Based on your check for '{condition}', it is recommended to get rest and consult a specialized {specialty} if symptoms don't resolve."
        },
        "es": {
            "hello": "¡Hola! Estoy aquí para ayudarle a comprender sus síntomas. ¿Cómo puedo ayudarle más?",
            "thanks": "¡De nada! Continúe monitoreando su salud y descanse mucho.",
            "thank you": "¡De nada! Dooper siempre está aquí para apoyarle.",
            "appointment": f"Dado que la especialidad recomendada es {specialty}, le sugiero llamar a una clínica local para consultar a un {specialty} calificado.",
            "doctor": f"Consultar a un {specialty} proporcionará un diagnóstico definitivo. Busque clínicas de {specialty} verificadas en su área.",
            "worse": "Si sus síntomas empeoran, vaya de inmediato al centro de urgencias más cercano.",
            "medicine": "No puedo recetar medicamentos específicos. Los analgésicos de venta libre pueden ayudar con el dolor, pero consulte primero a un médico.",
            "default": f"En relación con su evaluación de '{condition}', le recomendamos descansar y consultar a un {specialty} si los síntomas persisten."
        },
        "fr": {
            "hello": "Bonjour! Je suis là pour vous aider à comprendre vos symptômes. Comment puis-je vous aider?",
            "thanks": "Je vous en prie! Continuez à surveiller votre santé et reposez-vous.",
            "thank you": "Je vous en prie! Dooper est toujours là pour vous.",
            "appointment": f"Puisque la spécialité recommandée est {specialty}, je vous conseille de contacter un cabinet pour voir un {specialty}.",
            "doctor": f"Consulter un {specialty} permettra d'obtenir un diagnostic précis. Recherchez des spécialistes agréés.",
            "worse": "Si vos symptômes s'aggravent, veuillez vous rendre immédiatement aux urgences les plus proches.",
            "medicine": "Je ne peux pas prescrire de médicaments. Les anti-douleurs légers peuvent soulager, mais demandez d'abord à un pharmacien.",
            "default": f"D'après votre bilan pour '{condition}', il est conseillé de vous reposer et de consulter un {specialty} si cela persiste."
        },
        "de": {
            "hello": "Hallo! Ich bin hier, um Ihnen bei Ihren Symptomen zu helfen. Wie kann ich Ihnen helfen?",
            "thanks": "Gern geschehen! Bitte ruhen Sie sich aus und beobachten Sie Ihren Zustand.",
            "thank you": "Gern geschehen! Dooper ist jederzeit für Sie da.",
            "appointment": f"Da die empfohlene Fachrichtung {specialty} ist, raten wir Ihnen, einen Termin bei einem {specialty} zu vereinbaren.",
            "doctor": f"Ein Besuch beim {specialty} bringt Klarheit. Suchen Sie nach qualifizierten Praxen in Ihrer Nähe.",
            "worse": "Sollten sich die Symptome verschlimmern, suchen Sie bitte sofort die Notaufnahme auf.",
            "medicine": "Ich darf keine Medikamente verschreiben. Rezeptfreie Mittel helfen gegen Fieber, fragen Sie jedoch einen Apotheker.",
            "default": f"Bezüglich Ihrer Bewertung für '{condition}' wird empfohlen, sich auszuruhen und einen {specialty} zu konsultieren, falls keine Besserung eintritt."
        },
        "hi": {
            "hello": "नमस्ते! मैं आपके लक्षणों को समझने में मदद के लिए यहाँ हूँ। मैं आपकी क्या मदद कर सकता हूँ?",
            "thanks": "आपका स्वागत है! अपने स्वास्थ्य की निगरानी रखें और भरपूर आराम करें।",
            "thank you": "आपका बहुत-बहुत धन्यवाद! डूपर आपकी सहायता के लिए हमेशा तैयार है।",
            "appointment": f"चूंकि आपके लिए {specialty} की सिफारिश की गई है, हम आपको सलाह देते हैं कि किसी स्थानीय {specialty} से संपर्क कर अपॉइंटमेंट लें।",
            "doctor": f"एक {specialty} से परामर्श करने से सटीक निदान मिल सकेगा। अपने क्षेत्र में प्रमाणित {specialty} क्लीनिक खोजें।",
            "worse": "यदि आपके लक्षण गंभीर हो जाते हैं, तो कृपया तुरंत नजदीकी अस्पताल या आपातकालीन केंद्र जाएं।",
            "medicine": "मैं विशिष्ट दवाएं नहीं लिख सकता। बुखार या दर्द के लिए सामान्य दवाएं डॉक्टर की सलाह से ही लें।",
            "default": f"आपके '{condition}' के आकलन के आधार पर, आराम करने की सलाह दी जाती है और यदि लक्षण ठीक नहीं होते हैं, तो {specialty} से परामर्श करें।"
        }
    }
    
    lang_replies = replies.get(lang, replies["en"])
    
    # Check trigger words
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
