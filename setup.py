import os
import shutil
import mysql.connector

def setup_project():
    print("Setting up AI Symptom Checker & Doctor Recommendation project...")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Ensure required directories exist
    os.makedirs(os.path.join(base_dir, "static", "css"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "static", "js"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "static", "uploads", "profile_pics"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "templates"), exist_ok=True)
    
    # 2. Copy Dooper logo from sister project
    src_logo = os.path.abspath(os.path.join(base_dir, "..", "ai_medical_report_analyzer", "static", "logo.png"))
    dest_logo = os.path.join(base_dir, "static", "logo.png")
    
    if os.path.exists(src_logo):
        shutil.copy(src_logo, dest_logo)
        print(f"Successfully copied Dooper logo to {dest_logo}")
    else:
        # Try BI dashboard path
        src_logo_bi = os.path.abspath(os.path.join(base_dir, "..", "dooper_bi_dashboard", "static", "logo.png"))
        if os.path.exists(src_logo_bi):
            shutil.copy(src_logo_bi, dest_logo)
            print(f"Successfully copied Dooper logo from BI Dashboard to {dest_logo}")
        else:
            print(f"Warning: Logo not found in either template directory. Please place logo.png in {dest_logo} manually.")

    # 3. Initialize MySQL Database
    print("Connecting to MySQL...")
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="123Shorya@"
        )
        cursor = conn.cursor()
        
        schema_path = os.path.join(base_dir, "symptom_checker.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            
            # Execute SQL commands
            for command in schema_sql.split(";"):
                if command.strip():
                    cursor.execute(command)
            conn.commit()
            print("Successfully initialized MySQL database 'dooper_symptom_checker'")
        else:
            print(f"Error: {schema_path} not found!")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing MySQL Database: {e}")
        print("Please make sure MySQL is running and root credentials match.")
    
    print("Setup completed successfully!")

if __name__ == "__main__":
    setup_project()
