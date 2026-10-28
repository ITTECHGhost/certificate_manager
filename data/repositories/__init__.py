# data/repositories — Data Access Layer (MySQL SP Architecture); this file only re-exports.
import sys as _sys
import types as _types

from .base import (
    API_URL, DB_PATH, safe_cast, _local_ready, _refreshes_local_copy, OfflineModeError, BaseRepository,
)
from .settings import SettingsRepository, CountryRepository, GovernorateRepository
from .departments import DepartmentRepository, StudySystemRepository
from .personnel import (
    PersonnelRepository, ALL_SYSTEM_PERMISSIONS, ALL_PERMISSION_KEYS, PermissionRepository,
    DEFAULT_SYSTEM_ROLES, _RESULT_STATUS_CODES, RoleRepository,
)
from .courses import CourseRepository
from .certificates import CertificateRepository, IssuedCertificateRepository
from .students import StudentRepository, AcademicPeriodRepository, EnrollmentRepository
from .graduation import (
    GraduationOrderRepository, ThesisRepository, StudentSupervisorRepository, SupervisorRepository,
)
from .audit import AuditRepository, DashboardRepository
from .study_routines import StudyRoutineRepository
from .auth import AuthRepository
from . import personnel as _role_state_owner

# RoleRepository keeps its caches in module globals, and sync_engine resets one through this package
# (`_repos._USER_ROLE_CACHE = None`). A re-exported copy would go stale, so reads and writes of these
# names are forwarded to the module that owns them.
_LIVE_ROLE_STATE = ("_USER_ROLE_CACHE", "_ROLES_INITIALIZED")


class _Package(_types.ModuleType):
    def __getattr__(self, name):
        if name in _LIVE_ROLE_STATE:
            return getattr(_role_state_owner, name)
        raise AttributeError(f"module {self.__name__!r} has no attribute {name!r}")

    def __setattr__(self, name, value):
        if name in _LIVE_ROLE_STATE:
            setattr(_role_state_owner, name, value)
        else:
            super().__setattr__(name, value)


_sys.modules[__name__].__class__ = _Package
