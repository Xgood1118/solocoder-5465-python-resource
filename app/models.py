from enum import Enum
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class WorkerTrade(str, Enum):
    CARPENTER = "木工"
    STEELWORKER = "钢筋工"
    CONCRETE_WORKER = "混凝土工"
    ELECTRICIAN = "电工"
    PLUMBER = "水工"
    WELDER = "焊工"
    LABORER = "普工"


class WorkerLevel(str, Enum):
    SENIOR = "高级工"
    INTERMEDIATE = "中级工"
    JUNIOR = "初级工"


class EquipmentType(str, Enum):
    TOWER_CRANE = "塔吊"
    EXCAVATOR = "挖掘机"
    LOADER = "装载机"
    CONCRETE_PUMP = "混凝土泵车"
    ELEVATOR = "升降机"
    GENERATOR = "发电机"


class MaterialType(str, Enum):
    REBAR = "钢筋"
    CEMENT = "水泥"
    AGGREGATE = "砂石"
    BRICK = "砖"
    FORMWORK = "模板"
    SCAFFOLDING = "脚手架"


MATERIAL_UNITS = {
    MaterialType.REBAR: "吨",
    MaterialType.CEMENT: "袋",
    MaterialType.AGGREGATE: "立方米",
    MaterialType.BRICK: "块",
    MaterialType.FORMWORK: "平方米",
    MaterialType.SCAFFOLDING: "套",
}


class ProjectPriority(str, Enum):
    VIP = "VIP"
    NORMAL = "普通"


class EquipmentOwnership(str, Enum):
    OWNED = "自有"
    RENTED = "外租"


class Worker(BaseModel):
    id: str
    name: str
    trade: WorkerTrade
    level: WorkerLevel
    daily_wage: float = Field(gt=0)
    status: str = Field(default="在岗")


class WorkerAssignment(BaseModel):
    worker_id: str
    project_id: str
    start_date: date
    end_date: date


class Equipment(BaseModel):
    id: str
    name: str
    type: EquipmentType
    ownership: EquipmentOwnership
    daily_rent: float = Field(default=0.0)
    daily_depreciation: float = Field(default=0.0)
    is_scarce: bool = Field(default=False)
    status: str = Field(default="可用")


class EquipmentAssignment(BaseModel):
    equipment_id: str
    project_id: str
    start_date: date
    end_date: date


class MaterialDelivery(BaseModel):
    id: str
    material_type: MaterialType
    quantity: float
    delivery_date: date
    milestone: Optional[str] = None


class MaterialInventory(BaseModel):
    material_type: MaterialType
    total_stock: float
    allocated_stock: float = Field(default=0.0)
    unit: str

    @property
    def available_stock(self) -> float:
        return self.total_stock - self.allocated_stock


class MaterialAllocation(BaseModel):
    material_type: MaterialType
    project_id: str
    quantity: float
    allocation_date: date


class ResourceRequirement(BaseModel):
    worker_demands: Dict[str, float] = Field(default_factory=dict)
    equipment_demands: Dict[str, float] = Field(default_factory=dict)
    material_demands: Dict[str, float] = Field(default_factory=dict)


class Milestone(BaseModel):
    id: str
    name: str
    planned_date: date
    actual_date: Optional[date] = None
    completed: bool = Field(default=False)
    worker_trade: Optional[WorkerTrade] = None


class Project(BaseModel):
    id: str
    name: str
    start_date: date
    planned_duration_days: int
    contract_amount: float
    priority: ProjectPriority = Field(default=ProjectPriority.NORMAL)
    client: str
    requirements: ResourceRequirement = Field(default_factory=ResourceRequirement)
    milestones: List[Milestone] = Field(default_factory=list)
    status: str = Field(default="进行中")

    @property
    def end_date(self) -> date:
        from datetime import timedelta
        return self.start_date + timedelta(days=self.planned_duration_days)


class ConflictAlert(BaseModel):
    id: str
    type: str
    description: str
    resource_id: Optional[str] = None
    project_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    resolved: bool = Field(default=False)


class ScheduleResult(BaseModel):
    project_id: str
    worker_assignments: List[WorkerAssignment] = Field(default_factory=list)
    equipment_assignments: List[EquipmentAssignment] = Field(default_factory=list)
    material_allocations: List[MaterialAllocation] = Field(default_factory=list)
    conflicts: List[ConflictAlert] = Field(default_factory=list)
    total_labor_cost: float = Field(default=0.0)
    total_equipment_cost: float = Field(default=0.0)
    total_material_cost: float = Field(default=0.0)


class ProjectCostStats(BaseModel):
    project_id: str
    project_name: str
    labor_cost: float
    equipment_cost: float
    material_cost: float
    other_cost: float
    contract_amount: float
    profit: float
    profit_rate: float
    equipment_utilization: Dict[str, float]
    material_waste_rate: Dict[str, float]


class MonthlyStats(BaseModel):
    year: int
    month: int
    project_stats: List[ProjectCostStats] = Field(default_factory=list)


class MilestoneCompleteEvent(BaseModel):
    project_id: str
    milestone_id: str
    worker_trade: Optional[WorkerTrade] = None
    completed_date: date = Field(default_factory=date.today)
