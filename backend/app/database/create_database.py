from backend.app.database import db


db.connect_db()

try:
    db.reset_db()
    db.init_db()
    db.seed_locations()
finally:
    db.close_db()
