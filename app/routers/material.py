from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, Query
from datetime import date
import uuid
import logging

from app.models import (
    MaterialInventory, MaterialType, MATERIAL_UNITS,
    MaterialDelivery, MaterialAllocation,
    MilestoneCompleteEvent, WorkerTrade,
    ConflictAlert,
)
from app.store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/materials", tags=["材料管理"])


@router.get("", response_model=List[MaterialInventory])
def list_materials():
    return list(store.materials.values())


@router.get("/{material_type}", response_model=MaterialInventory)
def get_material(material_type: MaterialType):
    key = material_type.value
    if key not in store.materials:
        raise HTTPException(status_code=404, detail="材料不存在")
    return store.materials[key]


@router.put("/{material_type}/stock", response_model=MaterialInventory)
def update_material_stock(material_type: MaterialType, quantity: float = Query(..., gt=0, description="新增入库数量")):
    key = material_type.value
    if key not in store.materials:
        store.materials[key] = MaterialInventory(
            material_type=material_type,
            total_stock=quantity,
            unit=MATERIAL_UNITS[material_type],
        )
    else:
        store.materials[key].total_stock += quantity
    return store.materials[key]


@router.get("/deliveries", response_model=List[MaterialDelivery])
def list_deliveries(
    material_type: Optional[MaterialType] = Query(None),
    project_id: Optional[str] = Query(None),
):
    result = list(store.material_deliveries.values())
    if material_type:
        result = [d for d in result if d.material_type == material_type]
    return result


@router.post("/deliveries", response_model=MaterialDelivery)
def create_delivery(delivery: MaterialDelivery):
    if not delivery.id:
        delivery.id = f"D{uuid.uuid4().hex[:8]}"
    store.material_deliveries[delivery.id] = delivery
    key = delivery.material_type.value
    if key in store.materials:
        store.materials[key].total_stock += delivery.quantity
    else:
        store.materials[key] = MaterialInventory(
            material_type=delivery.material_type,
            total_stock=delivery.quantity,
            unit=MATERIAL_UNITS[delivery.material_type],
        )
    return delivery


@router.get("/allocations", response_model=List[MaterialAllocation])
def list_allocations(project_id: Optional[str] = Query(None)):
    result = list(store.material_allocations.values())
    if project_id:
        result = [a for a in result if a.project_id == project_id]
    return result


@router.post("/allocations", response_model=MaterialAllocation)
def create_allocation(allocation: MaterialAllocation):
    key = allocation.material_type.value
    if key not in store.materials:
        raise HTTPException(status_code=400, detail="材料类型不存在")
    inv = store.materials[key]
    if inv.available_stock < allocation.quantity:
        conflict = ConflictAlert(
            id=f"C{uuid.uuid4().hex[:8]}",
            type="材料超额分配",
            description=f"{allocation.material_type.value}库存不足: 需要{allocation.quantity}{inv.unit}, 可用{inv.available_stock}{inv.unit}",
            resource_id=key,
            project_ids=[allocation.project_id],
        )
        store.add_conflict(conflict)
        raise HTTPException(
            status_code=400,
            detail=f"材料库存不足: {inv.available_stock}{inv.unit} < {allocation.quantity}{inv.unit}",
        )
    inv.allocated_stock += allocation.quantity
    alloc_id = f"MA{uuid.uuid4().hex[:8]}"
    new_alloc = MaterialAllocation(
        material_type=allocation.material_type,
        project_id=allocation.project_id,
        quantity=allocation.quantity,
        allocation_date=allocation.allocation_date,
    )
    store.material_allocations[alloc_id] = new_alloc
    return new_alloc


def _recalculate_material_gaps(project_id: str, worker_trade: Optional[WorkerTrade]):
    if worker_trade is None:
        logger.info(f"项目 {project_id} 里程碑事件工种类别为空，跳过材料缺口重算")
        return
    if project_id not in store.projects:
        logger.warning(f"项目 {project_id} 不存在，无法重算材料缺口")
        return
    project = store.projects[project_id]
    mat_demands = project.requirements.material_demands
    gaps: Dict[str, float] = {}
    for mat_type_str, required in mat_demands.items():
        key = mat_type_str
        if key in store.materials:
            inv = store.materials[key]
            allocated = sum(
                a.quantity for a in store.material_allocations.values()
                if a.project_id == project_id and a.material_type.value == mat_type_str
            )
            remaining = required - allocated
            if remaining > inv.available_stock:
                gaps[mat_type_str] = remaining - inv.available_stock
    if gaps:
        logger.info(f"项目 {project_id} 材料缺口: {gaps}")
    else:
        logger.info(f"项目 {project_id} 材料无缺口")


@router.post("/milestone-complete")
def handle_milestone_complete(event: MilestoneCompleteEvent):
    if event.project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    project = store.projects[event.project_id]
    milestone = None
    for m in project.milestones:
        if m.id == event.milestone_id:
            milestone = m
            break
    if milestone is None:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    milestone.completed = True
    milestone.actual_date = event.completed_date
    if event.worker_trade is None:
        logger.info(
            f"里程碑 {event.milestone_id} 工种类别为空，静默跳过材料缺口重算"
        )
        return {
            "status": "ok",
            "milestone_id": event.milestone_id,
            "gap_recalculated": False,
            "reason": "worker_trade为空",
        }
    _recalculate_material_gaps(event.project_id, event.worker_trade)
    return {
        "status": "ok",
        "milestone_id": event.milestone_id,
        "gap_recalculated": True,
    }


@router.get("/gaps/{project_id}")
def get_material_gaps(project_id: str):
    if project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    project = store.projects[project_id]
    mat_demands = project.requirements.material_demands
    gaps = []
    for mat_type_str, required in mat_demands.items():
        allocated = sum(
            a.quantity for a in store.material_allocations.values()
            if a.project_id == project_id and a.material_type.value == mat_type_str
        )
        remaining = required - allocated
        key = mat_type_str
        available = 0.0
        unit = ""
        if key in store.materials:
            available = store.materials[key].available_stock
            unit = store.materials[key].unit
        gap = max(0.0, remaining - available)
        gaps.append({
            "material_type": mat_type_str,
            "required": required,
            "allocated": allocated,
            "remaining_needed": remaining,
            "available_stock": available,
            "unit": unit,
            "gap": gap,
        })
    return {"project_id": project_id, "gaps": gaps}
