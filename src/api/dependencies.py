"""API dependency injection providers."""

from typing import Annotated

from fastapi import Depends

from src.config import Settings, get_settings
from src.core.security import CurrentUser, Role, get_current_user, require_role

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Auth dependencies
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
ComplianceOfficerDep = Annotated[CurrentUser, Depends(require_role(Role.COMPLIANCE_OFFICER))]
AuditorDep = Annotated[CurrentUser, Depends(require_role([Role.COMPLIANCE_OFFICER, Role.AUDITOR]))]
AdminDep = Annotated[CurrentUser, Depends(require_role(Role.ADMIN))]
