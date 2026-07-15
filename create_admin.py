import os
import asyncio
from app.core.database import init_db, get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.member import Member, SocialLinks

async def main():
    await init_db()
    db = get_db()
    
    email = input("Enter admin email (e.g. admin@example.com): ")
    password = input("Enter admin password (min 6 characters): ")
    name = input("Enter admin name (e.g. Vardhan): ")
    
    if len(password) < 6:
        print("Error: Password must be at least 6 characters.")
        return
        
    # Check if user already exists
    users_ref = db.collection("users")
    docs = users_ref.where("email", "==", email).get()
    if docs:
        print("Error: A user with this email already exists!")
        return
        
    hashed_pw = get_password_hash(password)
    user = User(
        email=email,
        hashed_password=hashed_pw,
        role=UserRole.ADMIN,
        is_active=True
    )
    
    # 1. Insert User document
    user_doc_ref = users_ref.document()
    user_doc_ref.set(user.model_dump(exclude={"id"}))
    user.id = user_doc_ref.id
    
    # 2. Insert corresponding Member profile document with Admin role
    member = Member(
        user_id=str(user.id),
        name=name,
        role="Admin",
        year="Admin",
        socials=SocialLinks(),
        points=100
    )
    
    member_doc_ref = db.collection("members").document()
    member_doc_ref.set(member.model_dump(exclude={"id"}))
    
    print(f"\nSuccess: Admin user created with ID: {user.id}")
    print(f"Success: Admin member profile created with ID: {member_doc_ref.id}")

if __name__ == "__main__":
    asyncio.run(main())
