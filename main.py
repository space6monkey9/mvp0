from fastapi import FastAPI, Request, Form, UploadFile, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .db import SQLModel, engine
from .models import User, Bribe
from sqlmodel import Session, select, func
import datetime
from starlette.middleware.sessions import SessionMiddleware
import os
from supabase import create_async_client
from typing import List
import datetime
from supabase import SupabaseAuthClient
from pydantic import BaseModel, constr

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

#Dependency to get current user from Supabase session
async def get_current_user(request: Request) -> SupabaseAuthClient | None:
    supabase_session_data = request.session.get("supabase_session")
    if not supabase_session_data:
        return None

    #trying to get user with existing access token
    access_token = supabase_session_data.get("access_token")
    refresh_token = supabase_session_data.get("refresh_token") # Get refresh token

    if not access_token:
        return None

    try:
        # Set the session for the supabase client instance for this request
        await supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
        response = await supabase.auth.get_user()
        # user is retrieved directly from the response object
        user = response.user
        if user:
            print(f"User verified: {user.id}")

            return user # Return the Supabase user object
        else:
            # If get_user returns no user despite token, try refreshing
            print("No user found with current token, attempting refresh...")
            if refresh_token:
                 try:
                     refresh_response = await supabase.auth.refresh_session(refresh_token)
                     if refresh_response and refresh_response.session:
                         print("Session refreshed successfully.")
                         # Update session in Starlette middleware
                         request.session["supabase_session"] = refresh_response.session.dict()
                         # Return the newly verified user
                         return refresh_response.user
                     else:
                         print("Refresh token failed or returned no session.")
                         request.session.pop("supabase_session", None) # Clear invalid session
                         await supabase.auth.sign_out() # Clear supabase client session state
                         return None
                 except Exception as refresh_e:
                     print(f"Error refreshing session: {refresh_e}")
                     request.session.pop("supabase_session", None) 
                     await supabase.auth.sign_out() 
                     return None
            else:
                print("No refresh token available to refresh session.")
                request.session.pop("supabase_session", None) 
                await supabase.auth.sign_out() 
                return None

    except Exception as e:
        print(f"Error validating session: {e}")
        
        if refresh_token:
             try:
                 print("Attempting refresh due to exception...")
                 refresh_response = await supabase.auth.refresh_session(refresh_token)
                 if refresh_response and refresh_response.session:
                     print("Session refreshed successfully after exception.")
                     request.session["supabase_session"] = refresh_response.session.dict()
                     return refresh_response.user
                 else:
                     print("Refresh token failed or returned no session after exception.")
                     request.session.pop("supabase_session", None)
                     await supabase.auth.sign_out()
                     return None
             except Exception as refresh_e:
                 print(f"Error refreshing session after exception: {refresh_e}")
                 request.session.pop("supabase_session", None)
                 await supabase.auth.sign_out()
                 return None
        else:
            print("No refresh token available, clearing session.")
            request.session.pop("supabase_session", None)
            await supabase.auth.sign_out()
            return None

@app.get('/')
async def index(request:Request, page: int = 1, current_user: SupabaseAuthClient | None = Depends(get_current_user)):
    with Session(engine) as session:
        # Calculate the offset based on the page number.
        offset = (page - 1) * 50
        # Query the database, ordering by bribe_amt in descending order,
        # limiting to 50 results per page, and applying the offset.
        bribes = session.exec(select(Bribe).order_by(Bribe.bribe_amt.desc()).offset(offset).limit(50)).all()

        # Get total number of bribes for pagination
        total_bribes = session.exec(select(func.count(Bribe.id))).one()  
        total_pages = (total_bribes + 49) // 50 

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
                "doi": str(bribe.doi) if bribe.doi else "No Date", 
                "bribe_id": bribe.bribe_id,
            })

        return templates.TemplateResponse("base.html", {
            "request": request, 
            "bribes": bribe_data,
            "page": page,
            "total_pages": total_pages,
            "page_numbers": page_numbers,
            "current_user": current_user
        })

@app.get('/report')
async def report(request:Request, current_user: SupabaseAuthClient | None = Depends(get_current_user)):

    if not current_user:
        
        return RedirectResponse(url="/", status_code=303)

    current_date = datetime.date.today()
    formatted_date = current_date.strftime('%Y-%m-%d') 

    return templates.TemplateResponse("report.html", {
        "request": request,
        "current_date": formatted_date,
        "current_user": current_user
    })

@app.post('/report_bribe')
async def report_bribe(request: Request,
                        official: str = Form(None),
                        department: str = Form(...),
                        amount: int = Form(...),
                        pincode: str = Form(None),
                        state: str = Form(...),
                        district: str = Form(...),
                        description: str = Form(...),
                        date: str = Form(None),
                        evidence_files: List[UploadFile] = Form([]),
                        current_user: SupabaseAuthClient | None = Depends(get_current_user)
                        ):
    if not current_user:
        
        return RedirectResponse(url="/", status_code=303)

    username = current_user.user_metadata.get("username")
    
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()

        if official is None:
            official = "*UNKNOWN"

        parsed_date = None
        if date:
            try:
                parsed_date = datetime.datetime.strptime(date, '%Y-%m-%d').date() # Parse date string to datetime.date
            except ValueError:
                return JSONResponse({"error": "Invalid date format"}, status_code=422) # Return error if date format is invalid
            
        # generate bribe_id
        import uuid
        uuid_str = str(uuid.uuid4())
        numeric_uuid_chars = ''.join(filter(str.isdigit, uuid_str))
        import random
        if len(numeric_uuid_chars) >= 6:
            first_six_digits = ''.join(random.sample(numeric_uuid_chars, 6))
        else:
            first_six_digits = numeric_uuid_chars.zfill(6)

        bribe_id_candidate = f"{username[:2]}{username[-2:]}{first_six_digits}"
        print(f"Generated Candidate BRIBE ID: {bribe_id_candidate}")

        # Collision check for the user-facing bribe_id
        while True:
            existing_bribe = session.exec(select(Bribe).where(Bribe.bribe_id == bribe_id_candidate)).first()
            if not existing_bribe:
                break
            else:
                    # regenerate
                print(f"Collision detected for BRIBE ID: {bribe_id_candidate}. Regenerating...")
                    # Regenerate using a different sample
                if len(numeric_uuid_chars) >= 6:
                    first_six_digits = ''.join(random.sample(numeric_uuid_chars, 6))
                else:
                    first_six_digits = numeric_uuid_chars.zfill(6)
                bribe_id_candidate = f"{username[:2]}{username[-2:]}{first_six_digits}"
                print(f"Regenerated Candidate BRIBE ID: {bribe_id_candidate}")

        bribe = Bribe(
            ofcl_name=official,
            dept=department,
            bribe_amt=amount,
            pin_code=pincode,
            state_ut=state,
            district=district,
            descr=description,
            doi=parsed_date,
            # evidence_urls will be added after upload
            bribe_id=bribe_id_candidate, 
            id=user.id 
        )

        # Add bribe to the session 
        session.add(bribe)

        evidence_public_urls = []
        upload_successful = True # Flag to track upload status

        try:
            if evidence_files:
                print("Files received, starting upload process...")
                for evidence_file in evidence_files:
                     if evidence_file and evidence_file.filename and await evidence_file.read(): # Check if file has content
                        await evidence_file.seek(0) # Reset pointer after read check
                        contents = await evidence_file.read()
                        await evidence_file.seek(0) # Reset again for upload

                        original_filename = evidence_file.filename
                        content_type = evidence_file.content_type

                        if content_type and content_type.startswith("image/"):
                            bucket_name = "images"
                        elif content_type == "application/pdf":
                            bucket_name = "documents"
                        else:
                            print(f"Skipping unsupported file type: {content_type} for file {original_filename}")
                            continue

                        # Use authenticated username from session and bribe_id
                        username=current_user.user_metadata.get("username")
                        storage_path = f"{username}/{bribe_id_candidate}/{original_filename}"
                        print(f"Uploading to bucket: {bucket_name}, path: {storage_path}")

                        # Set session for storage interaction 
                        await supabase.auth.set_session(access_token=request.session.get("supabase_session", {}).get("access_token"),
                                                         refresh_token=request.session.get("supabase_session", {}).get("refresh_token"))

                        response = await supabase.storage.from_(bucket_name).upload(
                            path=storage_path,
                            file=contents,
                            file_options={"content-type": evidence_file.content_type, "cache-control": "3600", "upsert": "false"}
                        )
                        print(f"Supabase Upload Response Status: {response}") 

                        if response:
                            # Get public URL
                            url_response = await supabase.storage.from_(bucket_name).get_public_url(storage_path) 
                            print(f"Supabase Public URL: {url_response}")
                            evidence_public_urls.append(url_response)
                        else:
                             print(f"Error uploading file {original_filename}. Status: {response}, Message: {await response.json()}") 
                             upload_successful = False
                             # Attempt cleanup 
                             try:
                                 await supabase.storage.from_(bucket_name).remove([storage_path])
                                 print(f"Attempted cleanup of failed upload: {storage_path}")
                             except Exception as delete_e:
                                 print(f"Error during cleanup of failed upload {storage_path}: {delete_e}")
                             break # Stop processing further files

        except Exception as e:
            print(f"An unexpected error occurred during file upload: {e}")
            upload_successful = False

        if upload_successful:
            print("All uploads successful or no files to upload.")
            
            # Update the bribe object with the generated bribe_id and evidence URLs
            bribe.bribe_id = bribe_id_candidate
            bribe.evidence_urls = evidence_public_urls
            print(f"FINAL BRIBE before commit: {bribe}")

            session.commit()
            print("Bribe report committed successfully.")

            # Pass current_user to the template context
            return templates.TemplateResponse("bribe_reported.html", {
                "request": request,
                "bribe_id": bribe.bribe_id,
                "current_user": current_user
            })
        else:
            # If any upload failed, ROLLBACK the transaction
            print("Upload failed. Rolling back database changes.")
            session.rollback()

            # Re-render report form with error, also needs current_user
            current_date = datetime.date.today()
            formatted_date = current_date.strftime('%Y-%m-%d')
            return templates.TemplateResponse("report.html", {
                "request": request,
                "error": "Failed to upload evidence files. Please try submitting the report again.",
                "current_date": formatted_date,
                "current_user": current_user,
            }, status_code=500)

@app.post('/track_bribe')
async def track_bribe(request: Request, username: str = Form(None), reportingId: str = Form(None), current_user: SupabaseAuthClient | None = Depends(get_current_user)):
    with Session(engine) as session:
        
        clean_username = username.strip() if username else None
        clean_reporting_id = reportingId.strip() if reportingId else None
        print(f"Username is: {username}")
        print(f"reorting id is: {reportingId}")
        bribes = []
        if clean_username and clean_reporting_id: # Both username and reportingId are provided
            print("YES3: Both username and reportingId")
            # Get the specific bribe by ID for this user
            bribe_by_id = session.exec(select(Bribe).where(Bribe.bribe_id == clean_reporting_id, Bribe.user.has(username=clean_username))).first()
            print(f"bribe_by_id: {bribe_by_id}")
            
            if bribe_by_id:
                # Get all other bribes for this user, excluding the one we already found, ordered by date descending
                other_bribes = session.exec(
                    select(Bribe)
                    .where(Bribe.user.has(username=clean_username), Bribe.bribe_id != clean_reporting_id)
                    .order_by(Bribe.bribe_amt.desc())
                ).all()
                
                # Add the specific bribe first, then the rest
                bribes.append(bribe_by_id)
                bribes.extend(other_bribes)

        elif clean_username:
            print("YES1: Only username")
            user_bribes = session.exec(select(Bribe).where(Bribe.user.has(username=username))).all()
            print(f"user_bribes: {user_bribes}")
            if user_bribes:
                bribes.extend(user_bribes)

        elif clean_reporting_id:
            print("YES2: Only reportingId")
            bribe_by_id = session.exec(select(Bribe).where(Bribe.bribe_id == clean_reporting_id)).first()
            print(f"bribe_by_id: {bribe_by_id}")
            if bribe_by_id:
                bribes.append(bribe_by_id)

        if not bribes:
            print("Nothing found")
            
            return JSONResponse({"error": "No reports found for the provided information."}, status_code=404)
        
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
                "evidence_urls": bribe.evidence_urls, 
                "bribe_id": bribe.bribe_id,
            })

        print(f"bribe_data: {bribe_data}")
        context = {"request": request, "bribes": bribe_data, "current_user": current_user} 

        return templates.TemplateResponse("track_report.html", context)

# Pydantic model for request body validation
class UsernameCheckRequest(BaseModel):
    username: constr(min_length=3,max_length=20, regex=r'^[a-zA-Z0-9]+$') # type: ignore

@app.post('/check_username')
async def check_username_availability(request: Request, username_data: UsernameCheckRequest):
   
    username_to_check = username_data.username.lower()
    print(f"Checking availability for username: {username_to_check}")

    try:
        username_check = await supabase.rpc("check_username_exist", {"username_text": username_to_check}).execute()

        print(f"Supabase RPC check_username_exist response: {username_check.data}")

        # The RPC returns true if username exists, so availability is the opposite
        is_available = not username_check.data

        return JSONResponse({"available": is_available}, status_code=200)

    except Exception as e:
        print(f"Error checking username availability: {e}")
       
        return JSONResponse({"error": "Failed to check username availability", "details": str(e)}, status_code=500)

@app.post('/signup')
async def signup(request: Request, username_data:dict):

    # Check if username already exists
    username=username_data['username'].lower()
    username_check = await supabase.rpc("check_username_exist",{"username_text":username}).execute()
    print(username_check.data)
        
    if username_check.data:
        print(f"existing user")
        return JSONResponse({"error": "Username already exists"}, status_code=409) # Return 409 conflict status code
        
    if not username_check.data:
        print(f"new user")

        password = username_data['password']
        email=f"{username}@{username}.com"

        print(f"email: {email} passowrd: {password}")

        try:
            response1= await supabase.auth.sign_up(
              {
                "email": email,
                "password": password,
                "options": {"data":{"username": username}}
              }
            ) 
            print(f"response1: {response1}")
            response2= await supabase.table("user").insert({"username": username, "id": response1.user.id}).execute()
            print(f"response1: {response2}")
            return JSONResponse({"message": "Account created successfully"}, status_code=200)

        except Exception as e:
            print(f"error while sign-up: {e}")
            return JSONResponse({"error": e})
        
@app.post('/signin')
async def signin(request: Request, username_data:dict):
    
    try:
        response= await supabase.auth.sign_in_with_password(
            {
                "email": f"{username_data['username']}@{username_data['username']}.com",
                "password": username_data['password']
            }
        )
        print(f"Supabase signin response user: {response.user}")
        print(f"Supabase signin response session: {response.session}")

        if response.user and response.session:
            # Store session in Starlette session
            request.session["supabase_session"] = {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "username": response.user.user_metadata["username"]
            }
            print("Supabase session stored in Starlette session.")
        
            return JSONResponse({"message": "Login successful", "redirect_url": "/"}) # Send redirect URL in JSON
        else:
             # Handle cases like incorrect password, user not found
             print("Signin failed: No user / invalid credentials")
             # Supabase might raise an exception for specific errors, handled below
             return JSONResponse({"error": "Invalid credentials or user not found."}, status_code=401)

    except Exception as e:

        # Clear any potentially partially set session data on failure
        request.session.pop("supabase_session", None)
        try:
            await supabase.auth.sign_out() # Ensure Supabase client state is cleared
        except:
            pass # Ignore errors during cleanup signout

        return JSONResponse({"error": str(e)}, status_code=401)


@app.post('/signout')
async def signout(request: Request):
    # Clear the Starlette session
    supabase_session = request.session.pop("supabase_session", None)
    print(f"Cleared Starlette session: {supabase_session is None}")

    try:
        #  invalidate the supabase tokens
        response = await supabase.auth.sign_out()
        print(f"Supabase signout response: {response}") # Should be None on success
        
        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        print(f"Error during Supabase sign-out: {e}")

        return RedirectResponse(url="/", status_code=303)






