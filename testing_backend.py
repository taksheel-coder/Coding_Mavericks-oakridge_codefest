import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
cred = credentials.Certificate('/Users/taksheelsubudhi/Downloads/Dementia Assistant Firebase Service Account.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://dementia-assistant-90aef-default-rtdb.asia-southeast1.firebasedatabase.app/'
})
database = db.reference('data')
print("add this data")
name = input("name ")
age = input("age ")
information = input("information ")
database.push({
    'name': name,
    'age': age,
    'information': information
})
print("data has been successfully added")
