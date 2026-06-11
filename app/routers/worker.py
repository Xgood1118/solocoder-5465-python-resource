from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import date

from app.models import (
    Worker, WorkerTrade, WorkerLevel,
    WorkerAssignment,
)
from app.store import store

router = APIRouter(prefix="/api/workers", tags=["工人管理"])


@router.get("", response_model=List[Worker])
def list_workers(
    trade: Optional[WorkerTrade] = Query(None, description="按工种筛选"),
    level: Optional[WorkerLevel] = Query(None, description="按级别筛选"),
):
    result = list(store.workers.values())
    if trade:
        result = [w for w in result if w.trade == trade]
    if level:
        result = [w for w in result if w.level == level]
    return result


@router.get("/{worker_id}", response_model=Worker)
def get_worker(worker_id: str):
    if worker_id not in store.workers:
        raise HTTPException(status_code=404, detail="工人不存在")
    return store.workers[worker_id]


@router.post("", response_model=Worker)
def create_worker(worker: Worker):
    if worker.id in store.workers:
        raise HTTPException(status_code=400, detail="工人ID已存在")
    store.workers[worker.id] = worker
    return worker


@router.put("/{worker_id}", response_model=Worker)
def update_worker(worker_id: str, worker: Worker):
    if worker_id not in store.workers:
        raise HTTPException(status_code=404, detail="工人不存在")
    worker.id = worker_id
    store.workers[worker_id] = worker
    return worker


@router.get("/{worker_id}/assignments", response_model=List[WorkerAssignment])
def get_worker_assignments(worker_id: str):
    if worker_id not in store.workers:
        raise HTTPException(status_code=404, detail="工人不存在")
    return [a for a in store.worker_assignments.values() if a.worker_id == worker_id]


@router.get("/{worker_id}/availability")
def check_worker_availability(
    worker_id: str,
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
):
    if worker_id not in store.workers:
        raise HTTPException(status_code=404, detail="工人不存在")
    assignments = [
        a for a in store.worker_assignments.values()
        if a.worker_id == worker_id
        and not (a.end_date < start_date or a.start_date > end_date)
    ]
    return {
        "worker_id": worker_id,
        "available": len(assignments) == 0,
        "conflicting_assignments": assignments,
    }
