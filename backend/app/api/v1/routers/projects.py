from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.models import Project, ProjectCreate, ProjectUpdate
from app.infrastructure.memory import store

router = APIRouter()


@router.get("/projects", response_model=list[Project])
def list_projects() -> list[Project]:
    return store.projects


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    for p in store.projects:
        if p.id == project_id:
            return p
    raise HTTPException(status_code=404, detail="Project not found")


@router.post("/projects", response_model=Project)
def create_project(payload: ProjectCreate) -> Project:
    pid = store._id("pr")
    accents = ["#7296FF", "#A78BFA", "#35D99B", "#E48EF0", "#F0B45C", "#39D6D0"]
    project = Project(
        id=pid,
        name=payload.name,
        description=payload.description or "",
        health="draft",
        pipelineCount=0,
        chunkCount=0,
        editedAt="Just now",
        updatedAt=store._now_iso(),
        accent=accents[len(store.projects) % len(accents)],
    )
    store.projects.insert(0, project)
    return project


@router.patch("/projects/{project_id}", response_model=Project)
def update_project(project_id: str, payload: ProjectUpdate) -> Project:
    for i, p in enumerate(store.projects):
        if p.id == project_id:
            data = p.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updatedAt"] = store._now_iso()
            updated = Project(**data)
            store.projects[i] = updated
            return updated
    raise HTTPException(status_code=404, detail="Project not found")


@router.delete("/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, bool]:
    for i, p in enumerate(store.projects):
        if p.id == project_id:
            store.projects.pop(i)
            return {"ok": True}
    raise HTTPException(status_code=404, detail="Project not found")
