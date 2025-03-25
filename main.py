from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .db import SQLModel, engine
from .models import User, Bribe
from sqlmodel import Session, select, func
import base64
import uuid
import datetime
from starlette.middleware.sessions import SessionMiddleware
import os

app=FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("secret_key"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
SQLModel.metadata.create_all(engine)


@app.get('/')
async def index(request:Request, page: int = 1):
    with Session(engine) as session:
        # Calculate the offset based on the page number.
        offset = (page - 1) * 50
        # Query the database, ordering by bribe_amt in descending order,
        # limiting to 50 results per page, and applying the offset.
        bribes = session.exec(select(Bribe).order_by(Bribe.bribe_amt.desc()).offset(offset).limit(50)).all()

        # Get total number of bribes for pagination
        total_bribes = session.exec(select(func.count(Bribe.id))).one()  
        total_pages = (total_bribes + 49) // 50  # Calculate total page

        bribe_data = []
        for bribe in bribes:
            bribe_data.append({
                "ofcl_name": bribe.ofcl_name,
                "dept": bribe.dept,
                "state_ut": bribe.state_ut,
                "district": bribe.district,
                "bribe_amt": bribe.bribe_amt,
                "doi": str(bribe.doi) if bribe.doi else "No Date", # Handle potential None
            })

        return templates.TemplateResponse("base.html", {"request": request, "bribes": bribe_data, "page": page, "total_pages": total_pages})

@app.get('/report')
async def report(request:Request):

    return templates.TemplateResponse("report.html",{"request": request})

@app.post('/create_username')
async def create_username(username_data: dict):
    with Session(engine) as session:
        # Check if username already exists
        existing_user = session.exec(
            select(User).where(User.username == username_data['username'])
        ).first()

        print(f"Existing user: {existing_user}")
        
        if existing_user:
            print("WTF!!!")
            return JSONResponse({"error": "Username already exists"}, status_code=409) # Return 409(conflict) status code
            
        user = User(username=username_data['username'])
        session.add(user)
        session.commit()
        return JSONResponse({"message": "Username created successfully"}, status_code=200)

@app.post('/report_bribe')
async def report_bribe(request: Request,
                        username: str = Form(...),
                        official: str = Form(None),
                        department: str = Form(...),
                        amount: int = Form(...),
                        pincode: str = Form(None),
                        state: str = Form(...),
                        district: str = Form(...),
                        description: str = Form(...),
                        date: str = Form(None),
                        evidence: UploadFile = Form(None)
                        ):
    with Session(engine) as session:
        # Get the user
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            return templates.TemplateResponse("incorrect_username.html", {"request": request})

         # Initialize official name if None
        if official is None:
            official = "*UNKNOWN"

         # Handle date parsing
        parsed_date = None
        if date: # Check if date string is not empty
            try:
                parsed_date = datetime.datetime.strptime(date, '%Y-%m-%d').date() # Parse date string to datetime.date
            except ValueError:
                return JSONResponse({"error": "Invalid date format"}, status_code=422) # Return error if date format is invalid

        evidence_bytes = None # Initialize evidence_bytes to None
        if evidence: # Check if evidence file was uploaded
            evidence_bytes = await evidence.read() # Read the file content as bytes

        # Create Bribe object without bribe_id initially
        bribe = Bribe(
            user=user,  # Associate the user object
            ofcl_name=official,
            dept=department,
            bribe_amt=amount,
            pin_code=pincode,
            state_ut=state,
            district=district,
            descr=description,
            doi=parsed_date,
            evidence=evidence_bytes,
            user_id = user.id
        )

        # Add bribe to the session
        session.add(bribe)
        # Commit the session to get the automatically generated UUID for bribe.id
        session.commit()
        # Refresh the session to load the generated id into the bribe object
        session.refresh(bribe)

        # Generate bribe_id using the database-generated UUID
        uuid_str = str(bribe.id) # Get the UUID generated by the database
        print(f"UUID_str: {uuid_str}")
        numeric_uuid_chars = ''.join(filter(str.isdigit, uuid_str)) # Extract numeric chars from UUID
        print(f"NUMERIC_UUID_CHARS: {numeric_uuid_chars}")

        import random
        if len(numeric_uuid_chars) >= 6:
            first_six_digits = ''.join(random.sample(numeric_uuid_chars, 6)) # Randomly select 6 digits
        else:
            first_six_digits = numeric_uuid_chars.zfill(6) # Pad with zeros if less than 6 digits
        print(f"FIRST_SIX_DIGITS: {first_six_digits}")

        bribe_id = f"{username[:2]}{username[-2:]}{first_six_digits}"
        print(f"BRIBE ID: {bribe_id}")

        # Check if bribe_id already exists for the user
        while True:
            existing_bribe = session.exec(select(Bribe).where(Bribe.user_id == user.id, Bribe.bribe_id == bribe_id)).first()
            if not existing_bribe:
                break # bribe_id is unique for this user
            else:
                first_six_digits = ''.join(random.sample(numeric_uuid_chars, 6)) # Regenerate if bribe_id exists
                bribe_id = f"{username[:2]}{username[-2:]}{first_six_digits}"
                print(f"Regenerated BRIBE ID: {bribe_id}")

        # Update the bribe object with the generated bribe_id
        bribe.bribe_id = bribe_id
        print(f" BRIBE: {bribe}")
        # Commit the session again to save the bribe_id to the database
        session.commit()
        return templates.TemplateResponse("bribe_reported.html", {"request": request, "bribe_id": bribe_id}) 

@app.post('/track_bribe')
async def track_bribe(request: Request, username: str = Form(None), reportingId: str = Form(None)):
    with Session(engine) as session:
        print("YES0")
        print(f"Username is: {username}")
        print(f"reorting id is: {reportingId}")
        bribes = []
        if username and reportingId: # Both username and reportingId are provided
            print("YES3: Both username and reportingId")
            bribe_by_id = session.exec(select(Bribe).where(Bribe.bribe_id == reportingId)).first()
            if bribe_by_id:
                bribes.append(bribe_by_id) # Add the specific bribe first
            user = session.exec(select(User).where(User.username == username)).first()
            if user:
                user_bribes = session.exec(select(Bribe).where(Bribe.user_id == user.id)).all()
                if user_bribes:
                    for bribe in user_bribes:
                        if bribe not in bribes: # Avoid duplicates if bribe_by_id is also in user_bribes
                            bribes.append(bribe)

        elif username: # Only username is provided
            print("YES1: Only username")
            user = session.exec(select(User).where(User.username == username)).first()
            if user:
                user_bribes = session.exec(select(Bribe).where(Bribe.user_id == user.id)).all()
                if user_bribes:
                    bribes.extend(user_bribes)

        elif reportingId: # Only reportingId is provided
            print("YES2: Only reportingId")
            bribe_by_id = session.exec(select(Bribe).where(Bribe.bribe_id == reportingId)).first()
            if bribe_by_id:
                bribes.append(bribe_by_id)

        if not bribes:
            print("Nothing")
            bribe_data = [] 
            return JSONResponse({"error":"No reports found."})

        print("GOT IT")
        # Convert Bribe objects to dictionaries for JSON response
        bribe_data = []
        print("CHECK 1")
        for bribe in bribes:
            print("CHECK 2")
            evidence_content = None # Initialize evidence_content
            if bribe.evidence: # Check if there's an evidence path
                try:
                   with open(bribe.evidence, 'rb') as evidence_file: # Open in binary read mode ('rb')
                       evidence_content = base64.b64encode(evidence_file.read()).decode('utf-8') # Read as binary, encode to base64, then to string
                except FileNotFoundError:
                    evidence_content = "File not found" # Handle case where file is missing
                except Exception as e:
                    evidence_content = f"Error reading file: {e}" # Handle other potential errors
            bribe_data.append({
                "username": bribe.user.username,
                "official_name": bribe.ofcl_name,
                "department": bribe.dept, 
                "amount": bribe.bribe_amt,
                "state": bribe.state_ut,
                "district": bribe.district,
                "description": bribe.descr,
                "date": str(bribe.doi) if bribe.doi else None, # Convert date to string for JSON
                "evidence": evidence_content,
                "bribe_id": bribe.bribe_id,
            })
            print("CHECK 3")
         # Store bribe data in session or some temporary storage
        request.session['bribe_data'] = bribe_data
        print("CHECK 4")
        # Redirect to the track report page
        return RedirectResponse(url="/track_report", status_code=303)

@app.get('/track_report')
async def track_report(request: Request):
    print("CHECK 5")
    bribe_data = request.session.get('bribe_data', [])
    return templates.TemplateResponse("track_report.html", {"request": request, "bribes": bribe_data})


