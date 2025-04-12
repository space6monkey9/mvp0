from faker import Faker
import psycopg2
import uuid
import random
import os
import time
from datetime import datetime, timedelta
from supabase import create_client, Client


url: str = os.environ.get("supabase_url")
key: str = os.environ.get("supabase_key")
supabase: Client = create_client(url, key)

# Initialize Faker with Indian locale for relevant data
fake = Faker('en_IN')

# Connect to PostgreSQL
conn = psycopg2.connect(os.environ.get("db_url"))
cursor = conn.cursor()

print("CHECK 1")

# Generate mock dept
departments = [
    "Police", "Municipal Corporation", "Transport", 
    "Electricity Board", "Tax Department", "Education"
]

indian_states_ut = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", 
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", 
    "Himachal Pradesh", "Jharkhand", "Karnataka", 
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", 
    "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", 
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", 
    "West Bengal", "Andaman and Nicobar Islands", 
    "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Lakshadweep", "Delhi", "Puducherry"
]

'''
# Create 50 mock users
users = {}
for i in range(50):
    if i==9 or i== 19 or i==29 or i==39:
        time.sleep(3)
    username = fake.user_name() + str(random.randint(100, 999))  # Ensure unique username
    email= fake.email()
    password = fake.password(lower_case=True, digits=True)
    users[i]= {"email": email,"password": password,}
    response1=supabase.auth.sign_up(
              {
                "email": email,
                "password": password
              }
            ) 
    response2=supabase.table("user").insert({"username": username, "id": response1.user.id}).execute()
    #user_ids.append((response1.user.id,))

print("CHECK 2")  '''

# Insert users and get their IDs
#cursor.executemany("INSERT INTO \"user\" (username) VALUES (%s)", users)
#conn.commit()


# Get all user IDs
user_ids=[]
cursor.execute("SELECT id FROM \"user\"")
user_ids = [row[0] for row in cursor.fetchall()]

print("CHECK 3")

# Generate 200 mock bribes
bribes = []
for _ in range(200):

    ''' key=random.choice(list(users.keys()))
    email=users[key]["email"]
    password=users[key]["password"]

    response1=supabase.auth.sign_in_with_password(
            {
                "email": email,
                "password": password
            }
        ) '''
    user_id = random.choice(user_ids)
    department = random.choice(departments)
    state = random.choice(indian_states_ut)
    
    bribe = (
        #str(uuid.uuid4()),  # Generate UUID
        fake.name(),        # Official name
        department,
        random.randint(500, 50000),  # Bribe amount
        random.randint(100000, 999999),  # Pincode - generates a 6-digit random number
        state,
        fake.city(),        # District
        fake.text(max_nb_chars=300),  # Description
        (datetime.now() - timedelta(days=random.randint(0, 365))).date(),  # Date of incident
        None,               # Evidence (bytes) - can be null
        str(uuid.uuid4())[:6], # bribe_id - first 8 chars of UUID
        user_id
    )
    bribes.append(bribe)
    #response2 = supabase.auth.sign_out()

print("CHECK 4")

# Insert bribes
cursor.executemany("""
    INSERT INTO bribe (
        ofcl_name, dept, bribe_amt, pin_code, 
        state_ut, district, descr, doi, evidence_urls, bribe_id, id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s)
""", bribes)

print("CHECK 5")

conn.commit()
cursor.close()
conn.close()

print("DONE!")