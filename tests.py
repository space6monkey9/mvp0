# test_main.py
from fastapi.testclient import TestClient
from .main import app
from .main import engine, SQLModel, Session
from .main import User, Bribe # Import your User and Bribe models
import pytest
import datetime

# Use TestClient for testing FastAPI application
client = TestClient(app)

# Function to create database tables before tests and drop them after
def setup_db():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

# Pytest fixture to set up and tear down the database for tests
@pytest.fixture(scope="module", autouse=True)
def database_setup_and_teardown():
    yield from setup_db()

# --- Helper function to create a test user ---
def create_test_user(username: str):
    with Session(engine) as session:
        user = User(username=username)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

# --- Helper function to create a test bribe report ---
def create_test_bribe(user_id: int, bribe_id: str):
    with Session(engine) as session:
        bribe = Bribe(
            user_id=user_id,
            bribe_id=bribe_id,
            ofcl_name="Test Official",
            dept="Test Department",
            bribe_amt=100,
            state_ut="Test State",
            district="Test District",
            descr="Test Description",
            doi=datetime.date.today()
        )
        session.add(bribe)
        session.commit()
        session.refresh(bribe)
        return bribe

# --- Tests for each route ---

# Test for the index route (GET '/')
def test_index_route():
    # Make a GET request to the index route
    response = client.get("/")
    # Assert that the response status code is 200 (OK)
    assert response.status_code == 200
    # Assert that the response is HTML (you can check for specific content if needed)
    assert response.template.name == "base.html"

# Test for the report route (GET '/report')
def test_report_route():
    # Make a GET request to the report route
    response = client.get("/report")
    # Assert that the response status code is 200 (OK)
    assert response.status_code == 200
    # Assert that the response is HTML
    assert response.template.name == "report.html"

# Test for creating a username (POST '/create_username')
def test_create_username_route():
    # Define the username data to send in the POST request
    username_data = {"username": "testuser"}
    # Make a POST request to create a username
    response = client.post("/create_username", json=username_data)
    # Assert that the response status code is 200 (OK) for successful creation
    assert response.status_code == 200
    # Assert that the response is JSON and contains a success message
    assert response.json() == {"message": "Username created successfully"}

    # Test creating the same username again to check for error
    response_duplicate = client.post("/create_username", json=username_data)
    # Assert that the status code is 409 (Conflict) for duplicate username
    assert response_duplicate.status_code == 409
    # Assert that the error message is returned
    assert response_duplicate.json() == {"error": "Username already exists"}

# Test for reporting a bribe (POST '/report_bribe')
def test_report_bribe_route():
    # First, create a test user to associate with the bribe report
    test_user = create_test_user(username="testreporter")

    # Define bribe report form data (as it's a form submission)
    report_data = {
        "username": "testreporter",
        "official": "Corrupt Official",
        "department": "Gov Department",
        "amount": 500,
        "pincode": "123456",
        "state": "Test State",
        "district": "Test District",
        "description": "Bribe for service",
        "date": "2024-01-20", # Date in YYYY-MM-DD format
    }
    # Make a POST request to report a bribe
    response = client.post("/report_bribe", data=report_data, files={"evidence": ("evidence.txt", b"Some evidence content")})
    # Assert that the response status code is 200 (OK) for successful report
    assert response.status_code == 200
    # Assert that the template rendered is 'bribe_reported.html'
    assert response.template.name == "bribe_reported.html"
    # You can add more assertions to check if bribe_id is in the response context if needed

    # Test reporting bribe with incorrect username
    incorrect_user_data = report_data.copy()
    incorrect_user_data["username"] = "nonexistentuser"
    response_incorrect_user = client.post("/report_bribe", data=incorrect_user_data)
    assert response_incorrect_user.status_code == 200 # Or could be a different status if you handle it differently
    assert response_incorrect_user.template.name == "incorrect_username.html"

    # Test reporting bribe with invalid date format
    invalid_date_data = report_data.copy()
    invalid_date_data["date"] = "20-01-2024" # DD-MM-YYYY is invalid
    response_invalid_date = client.post("/report_bribe", data=invalid_date_data)
    assert response_invalid_date.status_code == 422 # Unprocessable Entity for invalid date format
    assert response_invalid_date.json() == {"error": "Invalid date format"}

# Test for tracking a bribe (POST '/track_bribe')
def test_track_bribe_route():
    # Create a test user and a bribe report for testing track_bribe
    test_user_track = create_test_user(username="tracker")
    test_bribe_track = create_test_bribe(user_id=test_user_track.id, bribe_id="tracker123456")

    # Test tracking by username
    track_by_username_data = {"username": "tracker", "reportingId": ""} # Only username
    response_username = client.post("/track_bribe", data=track_by_username_data, follow_redirects=False)
    assert response_username.status_code == 303 # Redirect status
    assert response_username.headers['location'] == "/track_report" # Check redirect URL

    # Test tracking by reporting ID
    track_by_id_data = {"username": "", "reportingId": "tracker123456"} # Only reportingId
    response_id = client.post("/track_bribe", data=track_by_id_data, follow_redirects=False)
    assert response_id.status_code == 303
    assert response_id.headers['location'] == "/track_report"

    # Test tracking by both username and reporting ID
    track_by_both_data = {"username": "tracker", "reportingId": "tracker123456"} # Both
    response_both = client.post("/track_bribe", data=track_by_both_data, follow_redirects=False)
    assert response_both.status_code == 303
    assert response_both.headers['location'] == "/track_report"

    # Test tracking with no data - should return error
    track_no_data = {"username": "", "reportingId": ""}
    response_no_data = client.post("/track_bribe", data=track_no_data)
    assert response_no_data.status_code == 200 # Or maybe 400 if you want to indicate bad request
    assert response_no_data.json() == {"error": "No reports found."}

# Test for track report page (GET '/track_report')
def test_track_report_page_route():
    # To test this properly, you'd ideally want to set up session data before redirecting.
    # For a basic test, we'll just check if the route is accessible and returns HTML.
    response = client.get("/track_report")
    assert response.status_code == 200
    assert response.template.name == "track_report.html"