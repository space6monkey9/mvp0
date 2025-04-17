from fastapi import FastAPI, Request, Form, UploadFile, Depends,HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from db import engine
from models import User, Bribe
from sqlmodel import Session, select, func, SQLModel
import datetime
from starlette.middleware.sessions import SessionMiddleware
import os
from supabase import create_async_client
from typing import List
from supabase import SupabaseAuthClient
from pydantic import BaseModel, constr
import logging


# configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# get logger instance
logger = logging.getLogger(__name__)

logger.info("--- main.py loaded, imports successful ---")

# --- Dependency to get Supabase Client (Handles Lazy Init) ---
async def get_supabase_client() -> create_async_client:
    """
    Dependency that creates and provides a NEW Supabase async client
    instance FOR EACH request.
    """
    supabase_url: str | None = os.environ.get("supabase_url")
    supabase_key: str | None = os.environ.get("supabase_key")

    try:
        # Create a new client instance every time the dependency is resolved
        client = await create_async_client(supabase_url, supabase_key)
        logger.debug("New Supabase async client created successfully for this request.")
        return client
    except Exception as e:
        logger.error(
            f"CRITICAL: Failed to create Supabase async client for request: {e}", exc_info=True
        )
        # Raise 503 if client creation fails for any reason
        raise HTTPException(status_code=503, detail="Failed to initialize service dependency.")
    
logger.info("--- About to initialize FastAPI app ---")
app = FastAPI()
logger.info("--- FastAPI app initialized ---")

secret_key_value = os.environ.get("secret_key")
if not secret_key_value:
    logger.error("CRITICAL: secret_key environment variable is missing or empty!")
else:
    logger.info("Found secret_key environment variable.")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("secret_key"))

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

SQLModel.metadata.create_all(engine)

# Dependency to get current user from Supabase session
async def get_current_user(
        request: Request,
   # Use the new dependency to get the initialized client
    current_supabase_client: create_async_client = Depends(get_supabase_client)
    ) -> SupabaseAuthClient | None:
    """Gets the current user using the injected request-scoped Supabase client."""

    supabase_session_data = request.session.get("supabase_session")
    if not supabase_session_data:
        
        return None

    # trying to get user with existing access token
    access_token = supabase_session_data.get("access_token")
    refresh_token = supabase_session_data.get("refresh_token")  # Get refresh token

    if not access_token:
        logger.warning("Access token missing in Supabase session data.")
        return None

    try:
        # Set the session for the supabase client instance for this request
        await current_supabase_client.auth.set_session(
            access_token=access_token, refresh_token=refresh_token
        )
        response = await current_supabase_client.auth.get_user()
        # user is retrieved directly from the response object
        user = response.user
        if user:
            logger.info(f"User verified via access token: {user.id}")
            return user  # Return the Supabase user object
        else:
            # If get_user returns no user despite token, try refreshing
            logger.warning("No user found with current token, attempting refresh")
            if refresh_token:
                try:
                    refresh_response = await current_supabase_client.auth.refresh_session(
                        refresh_token
                    )
                    if refresh_response and refresh_response.session:
                        logger.info(
                            f"Session refreshed successfully for user: {refresh_response.user.id}"
                        )
                        # Update session in Starlette middleware
                        request.session["supabase_session"] = (
                            refresh_response.session.dict()
                        )
                        # Return the newly verified user
                        return refresh_response.user
                    else:
                        logger.warning("Refresh token failed or returned no session.")
                        request.session.pop(
                            "supabase_session", None
                        )  # Clear invalid session
                        await (
                    await current_supabase_client.auth.sign_out()
                        )  # Clear supabase client session state
                        return None
                except Exception as refresh_e:
                    logger.error(
                        f"Error refreshing session: {refresh_e}", exc_info=True
                    )
                    request.session.pop("supabase_session", None)
                    await current_supabase_client.auth.sign_out()
                    return None
            else:
                logger.warning("No refresh token available to refresh session.")
                request.session.pop("supabase_session", None)
                await current_supabase_client.auth.sign_out()
                return None

    except Exception as e:
        logger.error(f"Error validating session with access token: {e}", exc_info=True)

        if refresh_token:
            try:
                logger.warning(
                    "Attempting refresh due to session validation exception..."
                )
                refresh_response = await current_supabase_client.auth.refresh_session(refresh_token)
                if refresh_response and refresh_response.session:
                    logger.info(
                        f"Session refreshed successfully after exception for user: {refresh_response.user.id}"
                    )
                    request.session["supabase_session"] = (
                        refresh_response.session.dict()
                    )
                    return refresh_response.user
                else:
                    logger.warning(
                        "Refresh token failed or returned no session after exception."
                    )
                    request.session.pop("supabase_session", None)
                    await current_supabase_client.auth.sign_out()
                    return None
            except Exception as refresh_e:
                logger.error(
                    f"Error refreshing session after exception: {refresh_e}",
                    exc_info=True,
                )
                request.session.pop("supabase_session", None)
                await current_supabase_client.auth.sign_out()
                return None
        else:
            logger.warning(
                "No refresh token available after session validation exception, clearing session."
            )
            request.session.pop("supabase_session", None)
            await current_supabase_client.auth.sign_out()
            return None

@app.get("/")
async def index(
    request: Request,
    page: int = 1,
    current_user: SupabaseAuthClient | None = Depends(get_current_user),
):
    logger.info(f"Index page requested: page={page}")
    with Session(engine) as session:
        # Calculate the offset based on the page number.
        offset = (page - 1) * 50
        # Query the database, ordering by bribe_amt in descending order,
        # limiting to 50 results per page, and applying the offset.
        bribes = session.exec(
            select(Bribe).order_by(Bribe.bribe_amt.desc()).offset(offset).limit(50)
        ).all()

        # Get total number of bribes for pagination
        total_bribes = session.exec(select(func.count(Bribe.id))).one()
        total_pages = (total_bribes + 49) // 50

        # Calculate total pages and page range
        start_page = max(1, page - 1)
        end_page = min(total_pages, page + 1)
        page_numbers = list(range(start_page, end_page + 1))

        bribe_data = []
        for bribe in bribes:
            bribe_data.append(
                {
                    "ofcl_name": bribe.ofcl_name,
                    "dept": bribe.dept,
                    "state_ut": bribe.state_ut,
                    "district": bribe.district,
                    "bribe_amt": bribe.bribe_amt,
                    "doi": str(bribe.doi) if bribe.doi else "No Date",
                    "bribe_id": bribe.bribe_id,
                }
            )

        return templates.TemplateResponse(
            "base.html",
            {
                "request": request,
                "bribes": bribe_data,
                "page": page,
                "total_pages": total_pages,
                "page_numbers": page_numbers,
                "current_user": current_user,
            },
        )

@app.get("/report")
async def report(
    request: Request,
    current_user: SupabaseAuthClient | None = Depends(get_current_user),
):
    logger.info("Report check 1: ")
    current_date = datetime.date.today()
    formatted_date = current_date.strftime("%Y-%m-%d")
    logger.info("Report check 2: ")

    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "current_date": formatted_date,
            "current_user": current_user,
        },
    )

@app.post("/report_bribe")
async def report_bribe(
    request: Request,
    official: str = Form(None),
    department: str = Form(...),
    amount: int = Form(...),
    pincode: str = Form(None),
    state: str = Form(...),
    district: str = Form(...),
    description: str = Form(...),
    date: str = Form(None),
    evidence_files: List[UploadFile] = Form([]),
    current_user: SupabaseAuthClient | None = Depends(get_current_user),
    current_supabase_client: create_async_client = Depends(get_supabase_client)
):
    if not current_user:
        logger.warning("Unauthorized attempt to report bribe.")
        return RedirectResponse(url="/", status_code=303)

    username = current_user.user_metadata.get("username")
    logger.info(f"User '{username}' attempting to report a bribe.")

    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()

        if official == '':
            official = "*UNKNOWN"

        parsed_date = None
        if date:
            try:
                parsed_date = datetime.datetime.strptime(
                    date, "%Y-%m-%d"
                ).date()  # Parse date string to datetime.date
            except ValueError:
                return JSONResponse(
                    {"error": "Invalid date format"}, status_code=422
                )  # Return error if date format is invalid

        # generate bribe_id
        import uuid

        uuid_str = str(uuid.uuid4())
        numeric_uuid_chars = "".join(filter(str.isdigit, uuid_str))
        import random

        if len(numeric_uuid_chars) >= 6:
            first_six_digits = "".join(random.sample(numeric_uuid_chars, 6))
        else:
            first_six_digits = numeric_uuid_chars.zfill(6)

        bribe_id_candidate = f"{username[:2]}{username[-2:]}{first_six_digits}"
        logger.info(f"Generated Candidate BRIBE ID: {bribe_id_candidate}")

        # Collision check for the user-facing bribe_id
        while True:
            existing_bribe = session.exec(
                select(Bribe).where(Bribe.bribe_id == bribe_id_candidate)
            ).first()
            if not existing_bribe:
                break
            else:
                logger.warning(
                    f"Collision detected for BRIBE ID: {bribe_id_candidate}. Regenerating..."
                )
                # Regenerate using a different sample
                if len(numeric_uuid_chars) >= 6:
                    first_six_digits = "".join(random.sample(numeric_uuid_chars, 6))
                else:
                    first_six_digits = numeric_uuid_chars.zfill(6)
                bribe_id_candidate = f"{username[:2]}{username[-2:]}{first_six_digits}"
                logger.info(f"Regenerated Candidate BRIBE ID: {bribe_id_candidate}")

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
            id=user.id,
        )

        # Add bribe to the session
        session.add(bribe)

        evidence_public_urls = []
        upload_successful = True  # Flag to track upload status

        try:
            if evidence_files:
                logger.info(
                    f"Processing {len(evidence_files)} evidence files for bribe report {bribe_id_candidate}."
                )
                for evidence_file in evidence_files:
                    if (
                        evidence_file
                        and evidence_file.filename
                        and await evidence_file.read()
                    ):  # Check if file has content
                        await evidence_file.seek(0)  # Reset pointer after read check
                        contents = await evidence_file.read()
                        await evidence_file.seek(0)  # Reset again for upload

                        original_filename = evidence_file.filename
                        content_type = evidence_file.content_type

                        if content_type and content_type.startswith("image/"):
                            bucket_name = "images"
                        elif content_type == "application/pdf":
                            bucket_name = "documents"
                        else:
                            logger.warning(
                                f"Skipping unsupported file type: {content_type} for file {original_filename} in bribe report {bribe_id_candidate}"
                            )
                            continue

                        # Use authenticated username from session and bribe_id
                        username = current_user.user_metadata.get("username")
                        storage_path = (
                            f"{username}/{bribe_id_candidate}/{original_filename}"
                        )
                        logger.info(
                            f"Uploading to bucket: {bucket_name}, path: {storage_path}"
                        )

                        # Set session for storage interaction
                        await current_supabase_client.auth.set_session(
                            access_token=request.session.get(
                                "supabase_session", {}
                            ).get("access_token"),
                            refresh_token=request.session.get(
                                "supabase_session", {}
                            ).get("refresh_token"),
                        )

                        response = await current_supabase_client.storage.from_(bucket_name).upload(
                            path=storage_path,
                            file=contents,
                            file_options={
                                "content-type": evidence_file.content_type,
                                "cache-control": "3600",
                                "upsert": "false",
                            },
                        )
                        logger.info(
                            f"Supabase Upload Response Status for {storage_path}: {response}"
                        )  

                        try:
                            # Attempt to get public URL if upload successful
                            if response:
                                url_response = await current_supabase_client.storage.from_(
                                    bucket_name
                                ).get_public_url(storage_path)
                                logger.info(
                                    f"Supabase Public URL for {storage_path}: {url_response}"
                                )
                                evidence_public_urls.append(url_response)
                            else:
                                # This else block might not be reached if upload raises exception on failure
                                logger.error(
                                    f"Error uploading file {original_filename} for bribe {bribe_id_candidate}. Status: {response}"
                                )  # Log detailed error if possible
                                upload_successful = False
                                # Attempt cleanup
                                try:
                                    await current_supabase_client.storage.from_(bucket_name).remove(
                                        [storage_path]
                                    )
                                    logger.info(
                                        f"Attempted cleanup of failed upload: {storage_path}"
                                    )
                                except Exception as delete_e:
                                    logger.error(
                                        f"Error during cleanup of failed upload {storage_path}: {delete_e}",
                                        exc_info=True,
                                    )
                                break  # Stop processing further files
                        except Exception as upload_detail_err:
                            # Catch potential errors during upload or getting URL
                            logger.error(
                                f"Error processing upload for file {original_filename} for bribe {bribe_id_candidate}: {upload_detail_err}",
                                exc_info=True,
                            )
                            upload_successful = False
                            # Attempt cleanup if storage_path was defined
                            if "storage_path" in locals():
                                try:
                                    await current_supabase_client.storage.from_(bucket_name).remove(
                                        [storage_path]
                                    )
                                    logger.info(
                                        f"Attempted cleanup after error processing upload: {storage_path}"
                                    )
                                except Exception as delete_e:
                                    logger.error(
                                        f"Error during cleanup after error processing upload {storage_path}: {delete_e}",
                                        exc_info=True,
                                    )
                            break

        except Exception as e:
            logger.error(
                f"An unexpected error occurred during file upload process for bribe {bribe_id_candidate}: {e}",
                exc_info=True,
            )
            err_msg= e
            upload_successful = False

        if upload_successful:
            logger.info(
                f"All uploads successful or no files to upload for bribe {bribe_id_candidate}."
            )

            # Update the bribe object with the generated bribe_id and evidence URLs
            bribe.bribe_id = bribe_id_candidate
            bribe.evidence_urls = evidence_public_urls
            logger.info(f"FINAL BRIBE before commit: {bribe}")

            session.commit()
            logger.info(
                f"Bribe report {bribe.bribe_id} committed successfully by user '{username}'."
            )

            return JSONResponse({"bribe_id": bribe.bribe_id}, status_code=200)
        else:
            # If any upload failed, ROLLBACK the transaction
            logger.error(
                f"Upload failed for bribe report by '{username}'. Rolling back database changes."
            )
            session.rollback()

            # Re-render report form with error, also needs current_user
            current_date = datetime.date.today()
            formatted_date = current_date.strftime("%Y-%m-%d")
            return templates.TemplateResponse(
                "report.html",
                {
                    "request": request,
                    "error": str(err_msg),
                    "current_date": formatted_date,
                    "current_user": current_user,
                },
                status_code=500,
            )

@app.post("/track_bribe")
async def track_bribe(
    request: Request,
    username: str = Form(None),
    reportingId: str = Form(None),
    current_user: SupabaseAuthClient | None = Depends(get_current_user),
):
    with Session(engine) as session:
        clean_username = username.strip() if username else None
        clean_reporting_id = reportingId.strip() if reportingId else None
        logger.info(
            f"Tracking bribe request received. Username: '{clean_username}', Reporting ID: '{clean_reporting_id}'"
        )
        bribes = []
        query_description = ""
        if (
            clean_username and clean_reporting_id
        ):  # Both username and reportingId are provided
            query_description = f"specific bribe ID '{clean_reporting_id}' for user '{clean_username}' and other bribes by user"
            logger.info(f"Tracking: {query_description}")
            # Get the specific bribe by ID for this user
            bribe_by_id = session.exec(
                select(Bribe).where(
                    Bribe.bribe_id == clean_reporting_id,
                    Bribe.user.has(username=clean_username),
                )
            ).first()
            logger.debug(f"Result for specific bribe ID: {bribe_by_id}")

            if bribe_by_id:
                # Get all other bribes for this user, excluding the one we already found, ordered by date descending
                other_bribes = session.exec(
                    select(Bribe)
                    .where(
                        Bribe.user.has(username=clean_username),
                        Bribe.bribe_id != clean_reporting_id,
                    )
                    .order_by(Bribe.bribe_amt.desc())
                ).all()

                # Add the specific bribe first, then the rest
                bribes.append(bribe_by_id)
                bribes.extend(other_bribes)

        elif clean_username:
            query_description = f"all bribes for user '{clean_username}'"
            logger.info(f"Tracking: {query_description}")
            user_bribes = session.exec(
                select(Bribe).where(Bribe.user.has(username=username))
            ).all()
            logger.debug(f"Found {len(user_bribes)} bribes for user '{clean_username}'")
            if user_bribes:
                bribes.extend(user_bribes)

        elif clean_reporting_id:
            query_description = f"bribe with ID '{clean_reporting_id}'"
            logger.info(f"Tracking: {query_description}")
            bribe_by_id = session.exec(
                select(Bribe).where(Bribe.bribe_id == clean_reporting_id)
            ).first()
            logger.debug(f"Result for specific bribe ID: {bribe_by_id}")
            if bribe_by_id:
                bribes.append(bribe_by_id)

        if not bribes:
            logger.warning(f"No bribe reports found for query: {query_description}")
            # Check if request is AJAX 
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JSONResponse({"error": "No reports found for the provided information."}, status_code=404)
            else:
                # Render the template with error message for normal form POST
                context = {"request": request, "bribes": [], "error": "No bribe reports found for the provided information.", "current_user": current_user}
                return templates.TemplateResponse("track_report.html", context)

        bribe_data = []

        for bribe in bribes:
            bribe_data.append(
                {
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
                }
            )

        logger.info(
            f"Returning {len(bribe_data)} bribe reports for query: {query_description}"
        )
        # logger.debug(f"Bribe data returned: {bribe_data}"
        context = {
            "request": request,
            "bribes": bribe_data,
            "current_user": current_user,
        }

        return templates.TemplateResponse("track_report.html", context)


# Pydantic model for request body validation
class UsernameCheckRequest(BaseModel):
    username: constr(min_length=3, max_length=20, regex=r"^[a-zA-Z0-9]+$")  # type: ignore


@app.post("/check_username")
async def check_username_availability(
    request: Request, username_data: UsernameCheckRequest,
    current_supabase_client: create_async_client = Depends(get_supabase_client)
):
    username_to_check = username_data.username.lower()
    logger.info(f"Checking username availability for: '{username_to_check}'")

    try:
        username_check = await current_supabase_client.rpc(
            "check_username_exist", {"username_text": username_to_check}
        ).execute()
        logger.debug(
            f"Supabase RPC check_username_exist response data: {username_check.data}"
        )

        # The RPC returns true if username exists, so availability is the opposite
        is_available = not username_check.data
        logger.info(f"Username '{username_to_check}' availability: {is_available}")

        return JSONResponse({"available": is_available}, status_code=200)

    except Exception as e:
        logger.error(
            f"Error checking username availability for '{username_to_check}': {e}",
            exc_info=True,
        )

        return JSONResponse(
            {"error": "Failed to check username availability", "details": str(e)},
            status_code=500,
        )


@app.post("/signup")
async def signup(request: Request, username_data: dict, current_supabase_client: create_async_client = Depends(get_supabase_client)):
    username = username_data.get("username")
    if not username:
        logger.error("Signup attempt failed: Username missing from request data.")
        return JSONResponse({"error": "Username is required"}, status_code=400)
    username = username.lower()

    password = username_data.get("password")
    if not password:
        logger.error(f"Signup attempt failed for user '{username}': Password missing.")
        return JSONResponse({"error": "Password is required"}, status_code=400)

    logger.info(f"Signup attempt for username: '{username}'")

    # Check if username already exists via RPC
    try:
        username_check = await current_supabase_client.rpc(
            "check_username_exist", {"username_text": username}
        ).execute()
        logger.debug(
            f"Username check RPC response for '{username}': {username_check.data}"
        )

        if username_check.data:
            logger.warning(
                f"Signup attempt failed for '{username}': Username already exists."
            )
            return JSONResponse(
                {"error": "Username already exists"}, status_code=409
            )  # Return 409 conflict status code

    except Exception as rpc_e:
        logger.error(
            f"Error checking username existence via RPC during signup for '{username}': {rpc_e}",
            exc_info=True,
        )
        return JSONResponse(
            {"error": "Failed to verify username availability. Please try again."},
            status_code=500,
        )

    # Proceed with signup if username is available
    logger.info(f"Username '{username}' is available, proceeding with signup.")
    email = f"{username}@{username}.com"  # Using derived email

    try:
        logger.info(f"Attempting Supabase Auth signup for email '{email}'.")
        response1 = await current_supabase_client.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {"data": {"username": username}},
            }
        )
        logger.info(
            f"Supabase Auth signup successful for user '{username}', User ID: {response1.user.id}"
        )
        # logger.debug(f"Supabase Auth signup response: {response1}")

        logger.info(
            f"Inserting user record into public table for user '{username}', ID: {response1.user.id}"
        )
        response2 = (
            await current_supabase_client.table("user")
            .insert({"username": username, "id": response1.user.id})
            .execute()
        )
        logger.info(f"Public user table insert successful for user '{username}'.")
        # logger.debug(f"Public table insert response: {response2}")

        return JSONResponse(
            {"message": "Account created successfully"}, status_code=200
        )

    except Exception as e:
        logger.error(
            f"Error during signup process for username '{username}': {e}", exc_info=True
        )

        return JSONResponse(
            {"error": f"An error occurred during signup: {e}"}, status_code=500
        )


@app.post("/signin")
async def signin(request: Request, username_data: dict, current_supabase_client: create_async_client = Depends(get_supabase_client)):
    username = username_data.get("username").lower()
    password = username_data.get("password").lower()

    logger.info(f"Signin attempt for username: '{username}'")
    email = f"{username}@{username}.com"

    try:
        response = await current_supabase_client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        # logger.debug(f"Supabase signin response user: {response.user}")
        # logger.debug(f"Supabase signin response session: {response.session}")

        if response.user and response.session:
            # Store session in Starlette session
            request.session["supabase_session"] = {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "username": response.user.user_metadata.get("username", username),
            }
            logger.info(
                f"User '{username}' signed in successfully. Supabase session stored in Starlette session."
            )

            return JSONResponse({"message": "Login successful", "redirect_url": "/"})
        else:
            logger.warning(
                f"Signin failed for '{username}': Supabase response indicates no user or session, but no exception raised."
            )
            return JSONResponse(
                {"error": "Invalid credentials or user not found."}, status_code=401
            )

    except Exception as e:
        logger.error(
            f"Signin failed for username '{username}': {e}", exc_info=True
        )  # Log stack trace for debug

        # Clear any potentially partially set session data on failure
        request.session.pop("supabase_session", None)
        try:
            await current_supabase_client.auth.sign_out()  # Ensure Supabase client state is cleared
            logger.info("Cleared Supabase client state after signin failure.")
        except Exception as signout_e:
            logger.error(
                f"Error during Supabase signout cleanup after failed signin: {signout_e}",
                exc_info=True,
            )

        return JSONResponse({"error": str(e)}, status_code=401)


@app.post("/signout")
async def signout(request: Request, current_supabase_client: create_async_client = Depends(get_supabase_client)):
    # Get username from session before popping it for logging
    session_data = request.session.get("supabase_session")
    username_for_log = session_data.get("username") if session_data else "Unknown user"

    # Clear the Starlette session
    supabase_session_cleared = request.session.pop("supabase_session", None) is not None
    logger.info(
        f"Signing out user: '{username_for_log}'. Starlette session cleared: {supabase_session_cleared}"
    )

    try:
        #  invalidate the supabase tokens
        response = await current_supabase_client.auth.sign_out()
        # logger.debug(f"Supabase signout response: {response}"), Should be None on success
        logger.info(f"Supabase signout successful for user '{username_for_log}'.")

        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        logger.error(
            f"Error during Supabase sign-out for user '{username_for_log}': {e}",
            exc_info=True,
        )
        # Still redirect even if Supabase signout fails, as local session is cleared
        return RedirectResponse(url="/", status_code=303)
