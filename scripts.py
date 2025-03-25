from faker import Faker
import psycopg2
import uuid
import random
from datetime import datetime, timedelta

# Initialize Faker with Indian locale for relevant data
fake = Faker('en_IN')

# Connect to PostgreSQL
conn = psycopg2.connect("dbname=test0 user=mayank password=159753")
cursor = conn.cursor()

# Generate mock users
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

# Create 50 mock users
users = []
for _ in range(50):
    username = fake.user_name() + str(random.randint(100, 999))  # Ensure unique username
    users.append((username,))

# Insert users and get their IDs
cursor.executemany("INSERT INTO \"user\" (username) VALUES (%s)", users)
conn.commit()

# Get all user IDs
cursor.execute("SELECT id FROM \"user\"")
user_ids = [row[0] for row in cursor.fetchall()]

# Generate 200 mock bribes
bribes = []
for _ in range(200):
    user_id = random.choice(user_ids)
    department = random.choice(departments)
    state = random.choice(indian_states_ut)
    
    bribe = (
        str(uuid.uuid4()),  # Generate UUID
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

# Insert bribes
cursor.executemany("""
    INSERT INTO bribe (
        id, ofcl_name, dept, bribe_amt, pin_code, 
        state_ut, district, descr, doi, evidence, bribe_id, user_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s)
""", bribes)

conn.commit()
cursor.close()
conn.close()