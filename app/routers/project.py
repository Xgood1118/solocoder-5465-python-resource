from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import date

from app.models import (
    Project, ProjectPriority, ResourceRequirement, Milestone,
)
from app.store import store

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


@router.get("", response_model=List[Project])
def list_projects(
    priority: Optional[ProjectPriority] = Query(None, description="按优先级筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
):
    result = list(store.projects.values())
    if priority:
        result = [p for p in result if p.priority == priority]
    if status:
        result = [p for p in result if p.status == status]
    result.sort(key=lambda p: (0 if p.priority == ProjectPriority.VIP else 1, p.start_date))
    return result


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str):
    if project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    return store.projects[project_id]


@router.post("", response_model=Project)
def create_project(project: Project):
    if project.id in store.projects:
        raise HTTPException(status_code=400, detail="项目ID已存在")
    store.projects[project.id] = project
    return project


@router.put("/{project_id}", response_model=Project)
def update_project(project_id: str, project: Project):
    if project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    project.id = project_id
    store.projects[project_id] = project
    return project


@router.get("/{project_id}/requirements", response_model=ResourceRequirement)
def get_project_requirements(project_id: str):
    if project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    return store.projects[project_id].requirements


@router.put("/{project_id}/requirements", response_model=ResourceRequirement)
def update_project_requirements(project_id: str, requirements: ResourceRequirement):
    if project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    store.projects[project_id].requirements = requirements
    return requirements


@router.get("/{project_id}/milestones", response_model=List[Milestone])
def get_project_milestones(project_id: str):
    if project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    return store.projects[project_id].milestones


@router.post("/{project_id}/milestones", response_model=Milestone)
def add_project_milestone(project_id: str, milestone: Milestone):
    if project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    store.projects[project_id].milestones.append(milestone)
    return milestone
