from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class Token(BaseModel):
    access_token:str
    token_type:str
    id:int

class RoleOption(BaseModel):
    role_id: int
    role_name: str

class MyRolesResponse(BaseModel):
    roles: list[RoleOption]

class RoleSelectionRequired(BaseModel):
    requires_role_selection: bool = True
    pending_token: str
    roles: List[RoleOption]

class SelectRoleRequest(BaseModel):
    pending_token: str
    role_id: int

class SwitchRoleRequest(BaseModel):
    role_id: int


class CreateCodedMasterDataRequest(BaseModel):
    code: str
    name: str
    is_active: bool = True
    description: Optional[str] = None
    claim_other: Optional[str] = None
    example: Optional[str] = None



class UpdateCodedMasterDataRequest(BaseModel):
    name: str
    is_active: bool = True
    description: Optional[str] = None
    claim_other: Optional[str] = None
    example: Optional[str] = None


class CreatePlainMasterDataRequest(BaseModel):
    name: str


class UpdatePlainMasterDataRequest(BaseModel):
    name: str


class CreateUserRequest(BaseModel):
    username: str
    password: Optional[str]
    name: str
    is_active: bool = True
    role_ids: List[int] = []  # optional - assign roles at creation time


class UpdateUserRequest(BaseModel):
    name: str
    is_active: bool


class ResetPasswordRequest(BaseModel):
    password: str


class CreateRoleRequest(BaseModel):
    role_name: str


class AssignRoleRequest(BaseModel):
    role_id: int

class User(BaseModel):
    id:int
    username:str
    role_id:int

class UserInDB(User):
    hashed_password:str


class Attachment(BaseModel):
    attachmentType: str
    fileName: str
    filePath: str
    fileSize: int


class Ownership(BaseModel):
    ownerName: str
    ownerRole: str
    ownerInitials: str


class CreateConceptRequest(BaseModel):
    conceptId: str
    conceptName: str
    internalConceptDescription: Optional[str] = None
    developmentStatus: Optional[str] = None
    priority: Optional[str] = None
    haloNumber: Optional[str] = None
    developmentNote: Optional[str] = None
    estimatedVolume: Optional[int] = None
    estimatedDollars: Optional[float] = None
    confidenceScore: Optional[str] = None
    previousReportId: Optional[str] = None
    qaSchedule: Optional[str] = None
    productionSchedule: Optional[str] = None
    conceptDevelopmentCompleted: bool = False
    clientApprovalCompleted: bool = False
    supportingDocumentsCompleted: bool = False
    conceptStatus: str = "Pending"
    ownership: Ownership
    attachments: List[Attachment] = []


class DashboardRequest(BaseModel):
    page: int = 1
    page_size: int = 50
    filterModel: Optional[Dict[str, Any]] = None
    sortModel: Optional[List[Dict[str, Any]]] = None
    quickSearch: Optional[str] = None






    # current_user_id:Optional[str] = None
