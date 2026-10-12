"""集中式鉴权包（authorization）。

对外只暴露 :class:`Authz`：服务层通过它做数据可见性判定与动作能力判定，
不再各自书写 ``if role == ...`` 分支。角色与数据级别常量仍复用
``app.services.constants``（本包不重复定义）。
"""
from app.security.policy import Authz, default_dataset_visibility, is_management

__all__ = ["Authz", "default_dataset_visibility", "is_management"]
