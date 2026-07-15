from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.api.deps import get_current_active_user, get_current_admin
from app.models.user import User, UserRole
from app.models.member import Member
from app.models.project import Project, ProjectCreate, ProjectUpdate, ProjectResponse
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[ProjectResponse])
async def read_projects(limit: int = 100, offset: int = 0):
    """
    Get all project showcases. Accessible by anyone.
    """
    db = get_db()
    docs = db.collection("projects").get()
    projects = [Project(id=doc.id, **doc.to_dict()) for doc in docs]
    return projects[offset : offset + limit]


@router.get("/{id}", response_model=ProjectResponse)
async def read_project(id: str):
    """
    Get specific project details.
    """
    db = get_db()
    doc = db.collection("projects").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return Project(id=doc.id, **doc.to_dict())


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new project showcase. Accessible by any active logged-in member.
    """
    db = get_db()
    project = Project(**project_in.model_dump())
    
    doc_ref = db.collection("projects").document()
    doc_ref.set(project.model_dump(exclude={"id"}))
    project.id = doc_ref.id
    
    return project


@router.put("/{id}", response_model=ProjectResponse)
async def update_project(
    id: str,
    project_in: ProjectUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a project showcase. Only admins or project contributors can perform this.
    """
    db = get_db()
    doc = db.collection("projects").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
        
    project = Project(id=doc.id, **doc.to_dict())
    
    # Check permissions: Admin or Contributor
    is_authorized = False
    if current_user.role == UserRole.ADMIN:
        is_authorized = True
    else:
        # Get member profile of current user to see if they are a contributor
        member_docs = db.collection("members").where("user_id", "==", str(current_user.id)).limit(1).get()
        member_doc = member_docs[0] if member_docs else None
        member = Member(id=member_doc.id, **member_doc.to_dict()) if member_doc else None
        if member:
            member_id_str = str(member.id)
            if member_id_str in project.contributors or member.name in project.contributors:
                is_authorized = True
                
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a contributor or admin to modify this project"
        )
        
    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
        
    db.collection("projects").document(project.id).set(project.model_dump(exclude={"id"}))
    return project


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a project showcase. Only admins or project contributors can perform this.
    """
    db = get_db()
    doc = db.collection("projects").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
        
    project = Project(id=doc.id, **doc.to_dict())
    
    # Check permissions: Admin or Contributor
    is_authorized = False
    if current_user.role == UserRole.ADMIN:
        is_authorized = True
    else:
        member_docs = db.collection("members").where("user_id", "==", str(current_user.id)).limit(1).get()
        member_doc = member_docs[0] if member_docs else None
        member = Member(id=member_doc.id, **member_doc.to_dict()) if member_doc else None
        if member:
            member_id_str = str(member.id)
            if member_id_str in project.contributors or member.name in project.contributors:
                is_authorized = True
                
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a contributor or admin to delete this project"
        )
        
    db.collection("projects").document(id).delete()
    return None
