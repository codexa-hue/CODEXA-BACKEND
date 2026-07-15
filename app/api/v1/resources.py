from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.resource import Resource, ResourceCreate, ResourceUpdate, ResourceResponse
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[ResourceResponse])
async def read_resources(
    category: Optional[str] = Query(None, description="Filter resources by category"),
    limit: int = 100,
    offset: int = 0
):
    """
    Get all learning resources. Optionally filter by category. Accessible by anyone.
    """
    db = get_db()
    resources_ref = db.collection("resources")
    
    if category:
        docs = resources_ref.where("category", "==", category).get()
    else:
        docs = resources_ref.get()
        
    resources = [Resource(id=doc.id, **doc.to_dict()) for doc in docs]
    return resources[offset : offset + limit]


@router.get("/{id}", response_model=ResourceResponse)
async def read_resource(id: str):
    """
    Get a single resource profile by ID.
    """
    db = get_db()
    doc = db.collection("resources").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )
    return Resource(id=doc.id, **doc.to_dict())


@router.post("/", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_resource(
    resource_in: ResourceCreate,
    current_user: User = Depends(get_current_admin)
):
    """
    Create a new study resource. Restricted to Admins.
    """
    db = get_db()
    resource = Resource(**resource_in.model_dump())
    
    doc_ref = db.collection("resources").document()
    doc_ref.set(resource.model_dump(exclude={"id"}))
    resource.id = doc_ref.id
    
    return resource


@router.put("/{id}", response_model=ResourceResponse)
async def update_resource(
    id: str,
    resource_in: ResourceUpdate,
    current_user: User = Depends(get_current_admin)
):
    """
    Update a resource. Restricted to Admins.
    """
    db = get_db()
    doc = db.collection("resources").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )
        
    resource = Resource(id=doc.id, **doc.to_dict())
    update_data = resource_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(resource, field, value)
        
    db.collection("resources").document(resource.id).set(resource.model_dump(exclude={"id"}))
    return resource


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    id: str,
    current_user: User = Depends(get_current_admin)
):
    """
    Delete a resource. Restricted to Admins.
    """
    db = get_db()
    doc = db.collection("resources").document(id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )
    db.collection("resources").document(id).delete()
    return None
