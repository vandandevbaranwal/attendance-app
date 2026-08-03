import os
import openpyxl
from database import Base, engine, SessionLocal, Student

def seed_database():
    print("Ensuring database tables exist...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        current_count = db.query(Student).count()
        excel_file = "EE'29 STUDENT LIST.xlsx"
        
        if os.path.exists(excel_file):
            print(f"Seeding students from Excel list '{excel_file}'...")
            wb = openpyxl.load_workbook(excel_file)
            sheet = wb.active
            
            # Clear old students and re-seed from Excel
            db.query(Student).delete()
            db.commit()
            
            students = []
            for r in range(2, sheet.max_row + 1):
                roll_number = sheet.cell(row=r, column=2).value
                name = sheet.cell(row=r, column=3).value
                
                if not roll_number or not name:
                    continue
                    
                roll_number = str(roll_number).strip()
                name = str(name).strip()
                email = f"{roll_number}@ietlucknow.ac.in".lower()
                
                students.append(Student(roll_number=roll_number, name=name, email=email))
                
            db.add_all(students)
            db.commit()
            print(f"Database successfully seeded with {len(students)} EE students from Excel.")
        elif current_count == 0:
            print("Excel list not found on server. Seeding default EE'29 roll numbers (2500520200001 - 2500520200077)...")
            students = []
            for i in range(1, 78):
                roll_number = f"25005202000{i:02d}"
                email = f"{roll_number}@ietlucknow.ac.in".lower()
                name = f"EE Student {i:02d}"
                students.append(Student(roll_number=roll_number, name=name, email=email))
            db.add_all(students)
            db.commit()
            print(f"Database successfully seeded with {len(students)} default EE student records.")
        else:
            print(f"Database already contains {current_count} student records. Skipping seeding.")
    except Exception as e:
        db.rollback()
        print(f"An error occurred during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
