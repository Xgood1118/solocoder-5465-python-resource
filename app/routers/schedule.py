from typing import List, Dict, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
import uuid
import logging

from app.models import (
    Project, ProjectPriority,
    Worker, WorkerTrade, WorkerLevel,
    WorkerAssignment,
    Equipment, EquipmentType, EquipmentOwnership,
    EquipmentAssignment,
    MaterialType, MaterialAllocation,
    ScheduleResult, ConflictAlert,
)
from app.store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/schedule", tags=["调度引擎"])

LEVEL_PRIORITY = {
    WorkerLevel.SENIOR: 0,
    WorkerLevel.INTERMEDIATE: 1,
    WorkerLevel.JUNIOR: 2,
}


def _is_worker_available(worker_id: str, start: date, end: date) -> bool:
    for a in store.worker_assignments.values():
        if a.worker_id == worker_id:
            if not (a.end_date < start or a.start_date > end):
                return False
    return True


def _is_equipment_available(equipment_id: str, start: date, end: date) -> bool:
    for a in store.equipment_assignments.values():
        if a.equipment_id == equipment_id:
            if not (a.end_date < start or a.start_date > end):
                return False
    return True


def _get_workers_by_trade(trade: WorkerTrade) -> List[Worker]:
    workers = [w for w in store.workers.values() if w.trade == trade]
    workers.sort(key=lambda w: LEVEL_PRIORITY[w.level])
    return workers


def _allocate_workers_for_project(
    project: Project,
    conflicts: List[ConflictAlert],
) -> Tuple[List[WorkerAssignment], float]:
    assignments = []
    total_cost = 0.0
    demands = project.requirements.worker_demands
    project_start = project.start_date
    project_end = project.end_date

    for trade_str, person_days in demands.items():
        try:
            trade = WorkerTrade(trade_str)
        except ValueError:
            continue

        workers = _get_workers_by_trade(trade)
        remaining_days = float(person_days)
        assigned_workers = set()

        for worker in workers:
            if remaining_days <= 0:
                break
            if worker.id in assigned_workers:
                continue
            if not _is_worker_available(worker.id, project_start, project_end):
                existing = [
                    a for a in store.worker_assignments.values()
                    if a.worker_id == worker.id
                    and not (a.end_date < project_start or a.start_date > project_end)
                ]
                if existing:
                    conflict = ConflictAlert(
                        id=f"C{uuid.uuid4().hex[:8]}",
                        type="工人冲突",
                        description=f"工人{worker.name}({worker.id})已被分配到其他项目，无法同时分配给{project.name}",
                        resource_id=worker.id,
                        project_ids=[project.id] + [a.project_id for a in existing],
                    )
                    conflicts.append(conflict)
                continue

            assign_days = min(remaining_days, float(project.planned_duration_days))
            if assign_days <= 0:
                continue

            assignment = WorkerAssignment(
                worker_id=worker.id,
                project_id=project.id,
                start_date=project_start,
                end_date=project_start + timedelta(days=int(assign_days) - 1),
            )
            assignments.append(assignment)
            assigned_workers.add(worker.id)
            total_cost += assign_days * worker.daily_wage
            remaining_days -= assign_days

        if remaining_days > 0:
            conflict = ConflictAlert(
                id=f"C{uuid.uuid4().hex[:8]}",
                type="工人不足",
                description=f"项目{project.name}的{trade.value}人天不足，尚缺{remaining_days:.1f}人天",
                project_ids=[project.id],
            )
            conflicts.append(conflict)

    return assignments, total_cost


def _get_equipments_by_type(eq_type: EquipmentType) -> List[Equipment]:
    return [e for e in store.equipments.values() if e.type == eq_type]


def _allocate_equipments_for_project(
    project: Project,
    conflicts: List[ConflictAlert],
) -> Tuple[List[EquipmentAssignment], float]:
    assignments = []
    total_cost = 0.0
    demands = project.requirements.equipment_demands
    project_start = project.start_date
    project_end = project.end_date

    for eq_type_str, days_needed in demands.items():
        try:
            eq_type = EquipmentType(eq_type_str)
        except ValueError:
            continue

        equipments = _get_equipments_by_type(eq_type)
        remaining_days = float(days_needed)

        for eq in equipments:
            if remaining_days <= 0:
                break
            if not _is_equipment_available(eq.id, project_start, project_end):
                existing = [
                    a for a in store.equipment_assignments.values()
                    if a.equipment_id == eq.id
                    and not (a.end_date < project_start or a.start_date > project_end)
                ]
                if existing:
                    conflict = ConflictAlert(
                        id=f"C{uuid.uuid4().hex[:8]}",
                        type="设备冲突",
                        description=f"设备{eq.name}({eq.id})已被其他项目占用，无法同时分配给{project.name}",
                        resource_id=eq.id,
                        project_ids=[project.id] + [a.project_id for a in existing],
                    )
                    conflicts.append(conflict)
                continue

            assign_days = min(remaining_days, float(project.planned_duration_days))
            if assign_days <= 0:
                continue

            if eq.ownership == EquipmentOwnership.RENTED:
                day_cost = eq.daily_rent
            else:
                day_cost = eq.daily_depreciation

            assignment = EquipmentAssignment(
                equipment_id=eq.id,
                project_id=project.id,
                start_date=project_start,
                end_date=project_start + timedelta(days=int(assign_days) - 1),
            )
            assignments.append(assignment)
            total_cost += assign_days * day_cost
            remaining_days -= assign_days

            if eq.is_scarce:
                break

        if remaining_days > 0:
            conflict = ConflictAlert(
                id=f"C{uuid.uuid4().hex[:8]}",
                type="设备不足",
                description=f"项目{project.name}的{eq_type.value}台班不足，尚缺{remaining_days:.1f}台班",
                project_ids=[project.id],
            )
            conflicts.append(conflict)

    return assignments, total_cost


MATERIAL_COST_PER_UNIT = {
    MaterialType.REBAR: 5000.0,
    MaterialType.CEMENT: 30.0,
    MaterialType.AGGREGATE: 120.0,
    MaterialType.BRICK: 0.8,
    MaterialType.FORMWORK: 50.0,
    MaterialType.SCAFFOLDING: 200.0,
}


def _allocate_materials_for_project(
    project: Project,
    conflicts: List[ConflictAlert],
) -> Tuple[List[MaterialAllocation], float]:
    allocations = []
    total_cost = 0.0
    demands = project.requirements.material_demands

    for mat_type_str, qty_needed in demands.items():
        key = mat_type_str
        if key not in store.materials:
            conflict = ConflictAlert(
                id=f"C{uuid.uuid4().hex[:8]}",
                type="材料缺失",
                description=f"项目{project.name}所需的材料{mat_type_str}不在库存中",
                project_ids=[project.id],
            )
            conflicts.append(conflict)
            continue

        inv = store.materials[key]
        qty = float(qty_needed)

        if inv.available_stock < qty:
            conflict = ConflictAlert(
                id=f"C{uuid.uuid4().hex[:8]}",
                type="材料超额分配",
                description=f"项目{project.name}的{mat_type_str}分配超额: 需要{qty}{inv.unit}, 库存仅{inv.available_stock}{inv.unit}",
                resource_id=key,
                project_ids=[project.id],
            )
            conflicts.append(conflict)

        alloc_qty = min(qty, inv.available_stock)
        if alloc_qty <= 0:
            continue

        try:
            mat_type = MaterialType(mat_type_str)
        except ValueError:
            continue

        inv.allocated_stock += alloc_qty
        allocation = MaterialAllocation(
            material_type=mat_type,
            project_id=project.id,
            quantity=alloc_qty,
            allocation_date=date.today(),
        )
        allocations.append(allocation)
        unit_cost = MATERIAL_COST_PER_UNIT.get(mat_type, 0.0)
        total_cost += alloc_qty * unit_cost

    return allocations, total_cost


def _run_greedy_scheduling(project_ids: Optional[List[str]] = None) -> Dict[str, ScheduleResult]:
    projects = list(store.projects.values())
    if project_ids:
        projects = [p for p in projects if p.id in project_ids]

    projects.sort(key=lambda p: (
        0 if p.priority == ProjectPriority.VIP else 1,
        p.start_date,
    ))

    results: Dict[str, ScheduleResult] = {}

    for proj in projects:
        conflicts: List[ConflictAlert] = []

        worker_assignments, labor_cost = _allocate_workers_for_project(proj, conflicts)
        equipment_assignments, equip_cost = _allocate_equipments_for_project(proj, conflicts)
        material_allocations, mat_cost = _allocate_materials_for_project(proj, conflicts)

        for a in worker_assignments:
            assign_id = f"WA{uuid.uuid4().hex[:8]}"
            store.worker_assignments[assign_id] = a
        for a in equipment_assignments:
            assign_id = f"EA{uuid.uuid4().hex[:8]}"
            store.equipment_assignments[assign_id] = a
        for a in material_allocations:
            alloc_id = f"MA{uuid.uuid4().hex[:8]}"
            store.material_allocations[alloc_id] = a
        for c in conflicts:
            store.add_conflict(c)

        result = ScheduleResult(
            project_id=proj.id,
            worker_assignments=worker_assignments,
            equipment_assignments=equipment_assignments,
            material_allocations=material_allocations,
            conflicts=conflicts,
            total_labor_cost=labor_cost,
            total_equipment_cost=equip_cost,
            total_material_cost=mat_cost,
        )
        results[proj.id] = result
        logger.info(f"项目 {proj.name}({proj.id}) 调度完成: 人力成本{labor_cost:.2f}, 设备成本{equip_cost:.2f}, 材料成本{mat_cost:.2f}, 冲突{len(conflicts)}个")

    return results


@router.post("/run", response_model=Dict[str, ScheduleResult])
def run_scheduling(
    project_ids: Optional[List[str]] = Query(None, description="指定项目ID列表，为空则调度所有项目"),
):
    if project_ids:
        for pid in project_ids:
            if pid not in store.projects:
                raise HTTPException(status_code=404, detail=f"项目 {pid} 不存在")
    store.worker_assignments.clear()
    store.equipment_assignments.clear()
    for inv in store.materials.values():
        inv.allocated_stock = 0.0
    store.material_allocations.clear()
    return _run_greedy_scheduling(project_ids)


@router.get("/results", response_model=Dict[str, ScheduleResult])
def get_schedule_results(project_id: Optional[str] = Query(None)):
    results: Dict[str, ScheduleResult] = {}
    pids = [project_id] if project_id else list(store.projects.keys())
    for pid in pids:
        if pid not in store.projects:
            continue
        was = [a for a in store.worker_assignments.values() if a.project_id == pid]
        eas = [a for a in store.equipment_assignments.values() if a.project_id == pid]
        mas = [a for a in store.material_allocations.values() if a.project_id == pid]
        cs = [c for c in store.conflicts.values() if pid in c.project_ids]

        labor_cost = 0.0
        for wa in was:
            w = store.workers.get(wa.worker_id)
            if w:
                days = (wa.end_date - wa.start_date).days + 1
                labor_cost += days * w.daily_wage

        equip_cost = 0.0
        for ea in eas:
            e = store.equipments.get(ea.equipment_id)
            if e:
                days = (ea.end_date - ea.start_date).days + 1
                if e.ownership == EquipmentOwnership.RENTED:
                    equip_cost += days * e.daily_rent
                else:
                    equip_cost += days * e.daily_depreciation

        mat_cost = 0.0
        for ma in mas:
            unit_cost = MATERIAL_COST_PER_UNIT.get(ma.material_type, 0.0)
            mat_cost += ma.quantity * unit_cost

        results[pid] = ScheduleResult(
            project_id=pid,
            worker_assignments=was,
            equipment_assignments=eas,
            material_allocations=mas,
            conflicts=cs,
            total_labor_cost=labor_cost,
            total_equipment_cost=equip_cost,
            total_material_cost=mat_cost,
        )
    return results


@router.get("/conflicts", response_model=List[ConflictAlert])
def list_conflicts(resolved: Optional[bool] = Query(None)):
    result = list(store.conflicts.values())
    if resolved is not None:
        result = [c for c in result if c.resolved == resolved]
    return result


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictAlert)
def resolve_conflict(conflict_id: str):
    if conflict_id not in store.conflicts:
        raise HTTPException(status_code=404, detail="冲突不存在")
    store.conflicts[conflict_id].resolved = True
    return store.conflicts[conflict_id]
