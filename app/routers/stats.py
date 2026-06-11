from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import date
from calendar import monthrange

from app.models import (
    ProjectCostStats, MonthlyStats,
    EquipmentOwnership, EquipmentType,
    MaterialType,
)
from app.store import store
from app.routers.schedule import MATERIAL_COST_PER_UNIT

router = APIRouter(prefix="/api/stats", tags=["统计报表"])


def _in_month(d: date, year: int, month: int) -> bool:
    return d.year == year and d.month == month


def _days_in_range_month(start: date, end: date, year: int, month: int) -> int:
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    overlap_start = max(start, month_start)
    overlap_end = min(end, month_end)
    if overlap_start > overlap_end:
        return 0
    return (overlap_end - overlap_start).days + 1


@router.get("/monthly", response_model=MonthlyStats)
def get_monthly_stats(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
):
    project_stats = []

    for pid, project in store.projects.items():
        labor_cost = 0.0
        for wa in store.worker_assignments.values():
            if wa.project_id != pid:
                continue
            w = store.workers.get(wa.worker_id)
            if not w:
                continue
            days = _days_in_range_month(wa.start_date, wa.end_date, year, month)
            labor_cost += days * w.daily_wage

        equipment_cost = 0.0
        eq_usage: Dict[str, int] = {}
        eq_total: Dict[str, int] = {}
        for ea in store.equipment_assignments.values():
            if ea.project_id != pid:
                continue
            e = store.equipments.get(ea.equipment_id)
            if not e:
                continue
            days = _days_in_range_month(ea.start_date, ea.end_date, year, month)
            if days <= 0:
                continue
            if e.ownership == EquipmentOwnership.RENTED:
                equipment_cost += days * e.daily_rent
            else:
                equipment_cost += days * e.daily_depreciation
            type_key = e.type.value
            eq_usage[type_key] = eq_usage.get(type_key, 0) + days

        for e in store.equipments.values():
            type_key = e.type.value
            eq_total[type_key] = eq_total.get(type_key, 0) + monthrange(year, month)[1]

        eq_utilization: Dict[str, float] = {}
        for t, usage in eq_usage.items():
            total = eq_total.get(t, 1)
            eq_utilization[t] = round(usage / total, 4) if total > 0 else 0.0

        material_cost = 0.0
        mat_actual: Dict[str, float] = {}
        for ma in store.material_allocations.values():
            if ma.project_id != pid:
                continue
            if not _in_month(ma.allocation_date, year, month):
                continue
            unit_cost = MATERIAL_COST_PER_UNIT.get(ma.material_type, 0.0)
            material_cost += ma.quantity * unit_cost
            mat_actual[ma.material_type.value] = mat_actual.get(ma.material_type.value, 0.0) + ma.quantity

        mat_theoretical = project.requirements.material_demands
        mat_waste_rate: Dict[str, float] = {}
        for mt, theoretical in mat_theoretical.items():
            actual = mat_actual.get(mt, 0.0)
            if theoretical > 0:
                mat_waste_rate[mt] = round((actual - theoretical) / theoretical, 4)
            else:
                mat_waste_rate[mt] = 0.0

        other_cost = (project.contract_amount * 0.05)
        total_cost = labor_cost + equipment_cost + material_cost + other_cost
        profit = project.contract_amount - total_cost
        profit_rate = round(profit / project.contract_amount, 4) if project.contract_amount > 0 else 0.0

        project_stats.append(ProjectCostStats(
            project_id=pid,
            project_name=project.name,
            labor_cost=round(labor_cost, 2),
            equipment_cost=round(equipment_cost, 2),
            material_cost=round(material_cost, 2),
            other_cost=round(other_cost, 2),
            contract_amount=project.contract_amount,
            profit=round(profit, 2),
            profit_rate=profit_rate,
            equipment_utilization=eq_utilization,
            material_waste_rate=mat_waste_rate,
        ))

    return MonthlyStats(year=year, month=month, project_stats=project_stats)


@router.get("/project/{project_id}")
def get_project_stats(project_id: str):
    if project_id not in store.projects:
        raise HTTPException(status_code=404, detail="项目不存在")
    project = store.projects[project_id]

    labor_cost = 0.0
    for wa in store.worker_assignments.values():
        if wa.project_id != project_id:
            continue
        w = store.workers.get(wa.worker_id)
        if not w:
            continue
        days = (wa.end_date - wa.start_date).days + 1
        labor_cost += days * w.daily_wage

    equipment_cost = 0.0
    eq_usage: Dict[str, int] = {}
    for ea in store.equipment_assignments.values():
        if ea.project_id != project_id:
            continue
        e = store.equipments.get(ea.equipment_id)
        if not e:
            continue
        days = (ea.end_date - ea.start_date).days + 1
        if e.ownership == EquipmentOwnership.RENTED:
            equipment_cost += days * e.daily_rent
        else:
            equipment_cost += days * e.daily_depreciation
        type_key = e.type.value
        eq_usage[type_key] = eq_usage.get(type_key, 0) + days

    material_cost = 0.0
    mat_actual: Dict[str, float] = {}
    for ma in store.material_allocations.values():
        if ma.project_id != project_id:
            continue
        unit_cost = MATERIAL_COST_PER_UNIT.get(ma.material_type, 0.0)
        material_cost += ma.quantity * unit_cost
        mat_actual[ma.material_type.value] = mat_actual.get(ma.material_type.value, 0.0) + ma.quantity

    mat_theoretical = project.requirements.material_demands
    mat_waste_rate: Dict[str, float] = {}
    for mt, theoretical in mat_theoretical.items():
        actual = mat_actual.get(mt, 0.0)
        if theoretical > 0:
            mat_waste_rate[mt] = round((actual - theoretical) / theoretical, 4)
        else:
            mat_waste_rate[mt] = 0.0

    other_cost = project.contract_amount * 0.05
    total_cost = labor_cost + equipment_cost + material_cost + other_cost
    profit = project.contract_amount - total_cost
    profit_rate = round(profit / project.contract_amount, 4) if project.contract_amount > 0 else 0.0

    return {
        "project_id": project_id,
        "project_name": project.name,
        "contract_amount": project.contract_amount,
        "labor_cost": round(labor_cost, 2),
        "equipment_cost": round(equipment_cost, 2),
        "material_cost": round(material_cost, 2),
        "other_cost": round(other_cost, 2),
        "total_cost": round(total_cost, 2),
        "profit": round(profit, 2),
        "profit_rate": profit_rate,
        "equipment_usage_days": eq_usage,
        "material_waste_rate": mat_waste_rate,
    }
