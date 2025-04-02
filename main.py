from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
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
import mimetypes
from supabase import create_client, Client, create_async_client, AsyncClient
from typing import List

async def startup_event():
    global supabase
    url: str = os.environ.get("supabase_url")
    key: str = os.environ.get("supabase_key")
    supabase = await create_async_client(url, key)

app=FastAPI()
app.add_event_handler("startup", startup_event) # register the startup event handler
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

        # Calculate total pages and page range
        start_page = max(1, page - 1)
        end_page = min(total_pages, page + 1)
        page_numbers = list(range(start_page, end_page + 1))

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

        return templates.TemplateResponse("base.html", {
            "request": request, 
            "bribes": bribe_data,
            "page": page,
            "total_pages": total_pages,
            "page_numbers": page_numbers
        })

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
                        evidence_files: List[UploadFile] = Form([])
                        ):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            return templates.TemplateResponse("incorrect_username.html", {"request": request})

        if official is None:
            official = "*UNKNOWN"

        parsed_date = None
        if date:
            try:
                parsed_date = datetime.datetime.strptime(date, '%Y-%m-%d').date() # Parse date string to datetime.date
            except ValueError:
                return JSONResponse({"error": "Invalid date format"}, status_code=422) # Return error if date format is invalid

        # Create Bribe object WITHOUT evidence URLs initially
        bribe = Bribe(
            user=user,
            ofcl_name=official,
            dept=department,
            bribe_amt=amount,
            pin_code=pincode,
            state_ut=state,
            district=district,
            descr=description,
            doi=parsed_date,
            # evidence_urls will be added after upload
            user_id = user.id
        )

        # Add bribe to session to get its ID without commiting
        session.add(bribe)
        session.flush() # Make the bribe object available in the session to get ID
        session.refresh(bribe) # Load the generated bribe.id (UUID)

        # --- Process and Upload Evidence Files to Supabase ---
        evidence_public_urls = []
        upload_successful = True # Flag to track upload status

        # 3. Use a try...except block for the entire upload process
        try:
            if evidence_files:
                print("Files received, starting upload process...")
                for evidence_file in evidence_files:
                    if evidence_file and evidence_file.filename and evidence_file.size > 0:
                        # Read file content
                        contents = await evidence_file.read()
                        await evidence_file.seek(0)

                        original_filename = evidence_file.filename
                        content_type = evidence_file.content_type

                        # Determine Supabase bucket
                        if content_type and content_type.startswith("image/"):
                            bucket_name = "images"
                        elif content_type == "application/pdf":
                            bucket_name = "documents"
                        else:
                            print(f"Skipping unsupported file type: {content_type} for file {original_filename}")
                            continue

                        # Construct Supabase storage path using the generated bribe.id
                        storage_path = f"{username}/{bribe.id}/{original_filename}"
                        print(f"Uploading to bucket: {bucket_name}, path: {storage_path}")

                        # Upload to Supabase Storage
                        response = await supabase.storage.from_(bucket_name).upload(
                            path=storage_path,
                            file=contents,
                            file_options={"content-type": evidence_file.content_type, "cache-control": "3600", "upsert": "false"}
                        )
                        print(f"Supabase Upload Response Status: {response}")

                        # Get public URL
                        url_response =await supabase.storage.from_(bucket_name).get_public_url(storage_path)
                        print(f"Supabase Public URL Response: {url_response}")

                        if isinstance(url_response, str):
                            evidence_public_urls.append(url_response)
                        else:
                            print(f"Warning: Could not get public URL for {storage_path}")
                            upload_successful = False
                            break # Stop processing further files

        except Exception as e:
            # Catch any unexpected errors during file processing/upload
            print(f"An unexpected error occurred during file upload: {e}")
            upload_successful = False

        # --- Finalize based on upload success ---
        if upload_successful:
            #  If ALL uploads succeeded, generate bribe_id and COMMIT
            print("All uploads successful. Generating bribe_id and committing.")
            # Generate User-Facing Bribe ID (using existing logic)
            uuid_str = str(bribe.id)
            numeric_uuid_chars = ''.join(filter(str.isdigit, uuid_str))
            import random
            if len(numeric_uuid_chars) >= 6:
                first_six_digits = ''.join(random.sample(numeric_uuid_chars, 6))
            else:
                first_six_digits = numeric_uuid_chars.zfill(6)

            bribe_id = f"{username[:2]}{username[-2:]}{first_six_digits}"
            print(f"Generated BRIBE ID: {bribe_id}")

            # Collision check (using existing logic)
            while True:
                existing_bribe = session.exec(select(Bribe).where(Bribe.bribe_id == bribe_id, Bribe.user_id == user.id)).first()
                if not existing_bribe or existing_bribe.id == bribe.id:
                    break
                else:
                    first_six_digits = ''.join(random.sample(numeric_uuid_chars, 6))
                    bribe_id = f"{username[:2]}{username[-2:]}{first_six_digits}"
                    print(f"Regenerated BRIBE ID: {bribe_id}")

            # Update the bribe object with the generated bribe_id and evidence URLs
            bribe.bribe_id = bribe_id
            bribe.evidence_urls = evidence_public_urls
            print(f"FINAL BRIBE before commit: {bribe}")

            # Commit the transaction ONLY IF uploads were successful
            session.commit()
            print("Bribe report committed successfully.")

            return templates.TemplateResponse("bribe_reported.html", {"request": request, "bribe_id": bribe_id})
        else:
            # If any upload failed, ROLLBACK the transaction
            print("Upload failed. Rolling back database changes.")
            session.rollback() # Discard the bribe added earlier

            return templates.TemplateResponse("report.html", {
                "request": request,
                "error": "Failed to upload evidence files. Please try submitting the report again."
            }, status_code=500) 

@app.post('/track_bribe')
async def track_bribe(request: Request, username: str = Form(None), reportingId: str = Form(None)):
    with Session(engine) as session:
        
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
            # Return JSON error or render a template indicating no reports found
            return templates.TemplateResponse("track_report.html", {"request": request, "bribes": [], "error": "No reports found for the provided information."})

        
        bribe_data = []
        
        for bribe in bribes:
            
            bribe_data.append({
                "id": str(bribe.id),
                "username": bribe.user.username,
                "official_name": bribe.ofcl_name,
                "department": bribe.dept, 
                "amount": bribe.bribe_amt,
                "state": bribe.state_ut,
                "district": bribe.district,
                "description": bribe.descr,
                "date": str(bribe.doi) if bribe.doi else None,
                "has_evidence": bool(bribe.evidence_urls), # Check if the list is not empty
                "evidence_urls": bribe.evidence_urls, # Pass the list of URLs
                "bribe_id": bribe.bribe_id,
            })
            
         # Store bribe data in session 
        request.session['bribe_data'] = bribe_data
        
        # Redirect to the track report page
        return RedirectResponse(url="/track_report", status_code=303)

@app.get('/track_report')
async def track_report(request: Request):
    print("CHECK 5")
    bribe_data = request.session.get('bribe_data', [])
    error_message = request.session.pop('error', None) # Get potential error from session
    context = {"request": request, "bribes": bribe_data}
    if error_message:
        context["error"] = error_message
    return templates.TemplateResponse("track_report.html", context)


