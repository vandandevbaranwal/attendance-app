import openpyxl
from database import Base, engine, SessionLocal, Student

def seed_database():
    print("Dropping old database tables...")
    Base.metadata.drop_all(bind=engine)
    print("Initializing new database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("Seeding students from Excel list 'EE\'29 STUDENT LIST.xlsx'...")
        wb = openpyxl.load_workbook("EE'29 STUDENT LIST.xlsx")
        sheet = wb.active
        
        students = []
        # Row 1 is header: ['S. No.', 'Roll No', 'Name']
        for r in range(2, sheet.max_row + 1):
            roll_number = sheet.cell(row=r, column=2).value
            name = sheet.cell(row=r, column=3).value
            
            if not roll_number or not name:
                continue
                
            # Clean roll_number and name
            roll_number = str(roll_number).strip()
            name = str(name).strip()
            
            # Generate email
            email = f"{roll_number}@ietlucknow.ac.in"
            
            student = Student(roll_number=roll_number, name=name, email=email)
            students.append(student)
            
        db.add_all(students)
        db.commit()
        print(f"Database successfully seeded with {len(students)} EE students from Excel.")
    except Exception as e:
        db.rollback()
        print(f"An error occurred during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
