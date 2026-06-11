from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import date

from app.models import (
    Equipment, EquipmentType, EquipmentOwnership,
    EquipmentAssignment,
)
from app.store import store

router = APIRouter(prefix="/api/equipments", tags=["设备管理"])


@router.get("", response_model=List[Equipment])
def list_equipments(
    eq_type: Optional[EquipmentType] = Query(None, description="按设备类型筛选"),
    ownership: Optional[EquipmentOwnership] = Query(None, description="按所有权筛选"),
    scarce_only: Optional[bool] = Query(None, description="仅显示稀缺资源"),
):
    result = list(store.equipments.values())
    if eq_type:
        result = [e for e in result if e.type == eq_type]
    if ownership:
        result = [e for e in result if e.ownership == ownership]
    if scarce_only is not None:
        result = [e for e in result if e.is_scarce == scarce_only]
    return result


@router.get("/{equipment_id}", response_model=Equipment)
def get_equipment(equipment_id: str):
    if equipment_id not in store.equipments:
        raise HTTPException(status_code=404, detail="设备不存在")
    return store.equipments[equipment_id]


@router.post("", response_model=Equipment)
def create_equipment(equipment: Equipment):
    if equipment.id in store.equipments:
        raise HTTPException(status_code=400, detail="设备ID已存在")
    store.equipments[equipment.id] = equipment
    return equipment


@router.put("/{equipment_id}", response_model=Equipment)
def update_equipment(equipment_id: str, equipment: Equipment):
    if equipment_id not in store.equipments:
        raise HTTPException(status_code=404, detail="设备不存在")
    equipment.id = equipment_id
    store.equipments[equipment_id] = equipment
    return equipment


@router.get("/{equipment_id}/assignments", response_model=List[EquipmentAssignment])
def get_equipment_assignments(equipment_id: str):
    if equipment_id not in store.equipments:
        raise HTTPException(status_code=404, detail="设备不存在")
    return [a for a in store.equipment_assignments.values() if a.equipment_id == equipment_id]


@router.get("/{equipment_id}/availability")
def check_equipment_availability(
    equipment_id: str,
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
):
    if equipment_id not in store.equipments:
        raise HTTPException(status_code=404, detail="设备不存在")
    assignments = [
        a for a in store.equipment_assignments.values()
        if a.equipment_id == equipment_id
        and not (a.end_date < start_date or a.start_date > end_date)
    ]
    return {
        "equipment_id": equipment_id,
        "available": len(assignments) == 0,
        "conflicting_assignments": assignments,
    }


@router.get("/{equipment_id}/cost")
def get_equipment_cost(
    equipment_id: str,
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
):
    if equipment_id not in store.equipments:
        raise HTTPException(status_code=404, detail="设备不存在")
    eq = store.equipments[equipment_id]
    days = (end_date - start_date).days + 1
    if eq.ownership == EquipmentOwnership.RENTED:
        daily_cost = eq.daily_rent
        cost_type = "外租租金"
    else:
        daily_cost = eq.daily_depreciation
        cost_type = "折旧费"
    return {
        "equipment_id": equipment_id,
        "equipment_name": eq.name,
        "ownership": eq.ownership.value,
        "cost_type": cost_type,
        "daily_cost": daily_cost,
        "days": days,
        "total_cost": daily_cost * days,
    }
