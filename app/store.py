from datetime import date, timedelta
from typing import Dict, List, Optional
import uuid
import logging

from app.models import (
    Worker, WorkerTrade, WorkerLevel,
    Equipment, EquipmentType, EquipmentOwnership,
    MaterialInventory, MaterialType, MATERIAL_UNITS, MaterialDelivery,
    Project, ProjectPriority, ResourceRequirement, Milestone,
    WorkerAssignment, EquipmentAssignment, MaterialAllocation,
    ConflictAlert,
)

logger = logging.getLogger(__name__)


class DataStore:
    def __init__(self):
        self.workers: Dict[str, Worker] = {}
        self.equipments: Dict[str, Equipment] = {}
        self.materials: Dict[str, MaterialInventory] = {}
        self.material_deliveries: Dict[str, MaterialDelivery] = {}
        self.projects: Dict[str, Project] = {}
        self.worker_assignments: Dict[str, WorkerAssignment] = {}
        self.equipment_assignments: Dict[str, EquipmentAssignment] = {}
        self.material_allocations: Dict[str, MaterialAllocation] = {}
        self.conflicts: Dict[str, ConflictAlert] = {}

    def load_initial_data(self):
        self._load_workers()
        self._load_equipments()
        self._load_materials()
        self._load_projects()
        logger.info("初始数据加载完成")

    def sync_from_external_systems(self):
        logger.info("开始从外部系统同步数据：HR系统、设备管理系统、物资采购系统")
        self._load_workers()
        self._load_equipments()
        self._load_materials()
        logger.info("外部系统数据同步完成")

    def _load_workers(self):
        sample_workers = [
            ("老张", WorkerTrade.CARPENTER, WorkerLevel.SENIOR, 600),
            ("老李", WorkerTrade.CARPENTER, WorkerLevel.INTERMEDIATE, 480),
            ("小王", WorkerTrade.CARPENTER, WorkerLevel.JUNIOR, 350),
            ("老赵", WorkerTrade.STEELWORKER, WorkerLevel.SENIOR, 650),
            ("老钱", WorkerTrade.STEELWORKER, WorkerLevel.INTERMEDIATE, 520),
            ("小孙", WorkerTrade.STEELWORKER, WorkerLevel.JUNIOR, 380),
            ("老周", WorkerTrade.CONCRETE_WORKER, WorkerLevel.SENIOR, 580),
            ("老吴", WorkerTrade.CONCRETE_WORKER, WorkerLevel.INTERMEDIATE, 460),
            ("小郑", WorkerTrade.CONCRETE_WORKER, WorkerLevel.JUNIOR, 340),
            ("老冯", WorkerTrade.ELECTRICIAN, WorkerLevel.SENIOR, 700),
            ("老陈", WorkerTrade.ELECTRICIAN, WorkerLevel.INTERMEDIATE, 550),
            ("小褚", WorkerTrade.ELECTRICIAN, WorkerLevel.JUNIOR, 400),
            ("老卫", WorkerTrade.PLUMBER, WorkerLevel.SENIOR, 620),
            ("老蒋", WorkerTrade.PLUMBER, WorkerLevel.INTERMEDIATE, 490),
            ("小沈", WorkerTrade.PLUMBER, WorkerLevel.JUNIOR, 360),
            ("老韩", WorkerTrade.WELDER, WorkerLevel.SENIOR, 680),
            ("老杨", WorkerTrade.WELDER, WorkerLevel.INTERMEDIATE, 540),
            ("小朱", WorkerTrade.WELDER, WorkerLevel.JUNIOR, 390),
            ("老秦", WorkerTrade.LABORER, WorkerLevel.SENIOR, 400),
            ("老尤", WorkerTrade.LABORER, WorkerLevel.INTERMEDIATE, 320),
            ("小许", WorkerTrade.LABORER, WorkerLevel.JUNIOR, 260),
            ("老何", WorkerTrade.CARPENTER, WorkerLevel.INTERMEDIATE, 480),
            ("老吕", WorkerTrade.STEELWORKER, WorkerLevel.INTERMEDIATE, 520),
            ("老施", WorkerTrade.CONCRETE_WORKER, WorkerLevel.INTERMEDIATE, 460),
            ("老张2", WorkerTrade.ELECTRICIAN, WorkerLevel.INTERMEDIATE, 550),
        ]
        for i, (name, trade, level, wage) in enumerate(sample_workers):
            worker_id = f"W{i+1:03d}"
            self.workers[worker_id] = Worker(
                id=worker_id, name=name, trade=trade, level=level, daily_wage=wage
            )

    def _load_equipments(self):
        sample_equipments = [
            ("塔吊-01", EquipmentType.TOWER_CRANE, EquipmentOwnership.OWNED, 0, 500, True),
            ("塔吊-02", EquipmentType.TOWER_CRANE, EquipmentOwnership.RENTED, 3000, 0, True),
            ("挖掘机-01", EquipmentType.EXCAVATOR, EquipmentOwnership.OWNED, 0, 300, False),
            ("挖掘机-02", EquipmentType.EXCAVATOR, EquipmentOwnership.RENTED, 1500, 0, False),
            ("装载机-01", EquipmentType.LOADER, EquipmentOwnership.OWNED, 0, 200, False),
            ("装载机-02", EquipmentType.LOADER, EquipmentOwnership.RENTED, 800, 0, False),
            ("混凝土泵车-01", EquipmentType.CONCRETE_PUMP, EquipmentOwnership.OWNED, 0, 800, True),
            ("混凝土泵车-02", EquipmentType.CONCRETE_PUMP, EquipmentOwnership.RENTED, 2500, 0, True),
            ("升降机-01", EquipmentType.ELEVATOR, EquipmentOwnership.OWNED, 0, 150, False),
            ("升降机-02", EquipmentType.ELEVATOR, EquipmentOwnership.RENTED, 600, 0, False),
            ("发电机-01", EquipmentType.GENERATOR, EquipmentOwnership.OWNED, 0, 100, False),
            ("发电机-02", EquipmentType.GENERATOR, EquipmentOwnership.RENTED, 400, 0, False),
        ]
        for i, (name, eq_type, ownership, rent, dep, scarce) in enumerate(sample_equipments):
            eq_id = f"E{i+1:03d}"
            self.equipments[eq_id] = Equipment(
                id=eq_id, name=name, type=eq_type, ownership=ownership,
                daily_rent=rent, daily_depreciation=dep, is_scarce=scarce
            )

    def _load_materials(self):
        sample_materials = [
            (MaterialType.REBAR, 200.0),
            (MaterialType.CEMENT, 5000.0),
            (MaterialType.AGGREGATE, 1000.0),
            (MaterialType.BRICK, 100000.0),
            (MaterialType.FORMWORK, 2000.0),
            (MaterialType.SCAFFOLDING, 500.0),
        ]
        for mat_type, stock in sample_materials:
            self.materials[mat_type.value] = MaterialInventory(
                material_type=mat_type,
                total_stock=stock,
                unit=MATERIAL_UNITS[mat_type],
            )

    def _load_projects(self):
        today = date.today()
        projects_data = [
            (
                "P001", "市政大桥工程", today, 365, 50000000.0,
                ProjectPriority.VIP, "市政集团",
                {
                    WorkerTrade.CARPENTER.value: 500,
                    WorkerTrade.STEELWORKER.value: 800,
                    WorkerTrade.CONCRETE_WORKER.value: 600,
                    WorkerTrade.ELECTRICIAN.value: 200,
                    WorkerTrade.WELDER.value: 300,
                    WorkerTrade.LABORER.value: 1000,
                },
                {
                    EquipmentType.TOWER_CRANE.value: 180,
                    EquipmentType.EXCAVATOR.value: 90,
                    EquipmentType.CONCRETE_PUMP.value: 60,
                },
                {
                    MaterialType.REBAR.value: 150,
                    MaterialType.CEMENT.value: 3000,
                    MaterialType.AGGREGATE.value: 800,
                },
            ),
            (
                "P002", "阳光花园住宅楼", today + timedelta(days=7), 240, 20000000.0,
                ProjectPriority.NORMAL, "阳光地产",
                {
                    WorkerTrade.CARPENTER.value: 400,
                    WorkerTrade.STEELWORKER.value: 500,
                    WorkerTrade.CONCRETE_WORKER.value: 400,
                    WorkerTrade.ELECTRICIAN.value: 150,
                    WorkerTrade.PLUMBER.value: 150,
                    WorkerTrade.LABORER.value: 800,
                },
                {
                    EquipmentType.TOWER_CRANE.value: 120,
                    EquipmentType.ELEVATOR.value: 100,
                },
                {
                    MaterialType.REBAR.value: 80,
                    MaterialType.CEMENT.value: 2000,
                    MaterialType.BRICK.value: 50000,
                },
            ),
            (
                "P003", "市民中心广场", today + timedelta(days=14), 180, 15000000.0,
                ProjectPriority.NORMAL, "城投公司",
                {
                    WorkerTrade.CARPENTER.value: 300,
                    WorkerTrade.CONCRETE_WORKER.value: 350,
                    WorkerTrade.ELECTRICIAN.value: 100,
                    WorkerTrade.PLUMBER.value: 80,
                    WorkerTrade.LABORER.value: 600,
                },
                {
                    EquipmentType.EXCAVATOR.value: 60,
                    EquipmentType.LOADER.value: 45,
                    EquipmentType.GENERATOR.value: 30,
                },
                {
                    MaterialType.REBAR.value: 50,
                    MaterialType.CEMENT.value: 1500,
                    MaterialType.AGGREGATE.value: 500,
                    MaterialType.FORMWORK.value: 800,
                },
            ),
        ]
        for pid, name, sdate, dur, amount, priority, client, wdem, eqdem, mdem in projects_data:
            milestones = [
                Milestone(
                    id=f"M{pid}-1", name="基础完工",
                    planned_date=sdate + timedelta(days=dur // 4),
                    worker_trade=WorkerTrade.CONCRETE_WORKER,
                ),
                Milestone(
                    id=f"M{pid}-2", name="主体结构封顶",
                    planned_date=sdate + timedelta(days=dur // 2),
                    worker_trade=WorkerTrade.STEELWORKER,
                ),
                Milestone(
                    id=f"M{pid}-3", name="竣工验收",
                    planned_date=sdate + timedelta(days=dur),
                    worker_trade=None,
                ),
            ]
            self.projects[pid] = Project(
                id=pid, name=name, start_date=sdate,
                planned_duration_days=dur, contract_amount=amount,
                priority=priority, client=client,
                requirements=ResourceRequirement(
                    worker_demands=wdem,
                    equipment_demands=eqdem,
                    material_demands=mdem,
                ),
                milestones=milestones,
            )

    def add_conflict(self, conflict: ConflictAlert):
        self.conflicts[conflict.id] = conflict
        logger.warning(f"冲突告警: {conflict.type} - {conflict.description}")

    def get_unresolved_conflicts(self) -> List[ConflictAlert]:
        return [c for c in self.conflicts.values() if not c.resolved]


store = DataStore()
