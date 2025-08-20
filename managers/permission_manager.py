import yaml
import os
from typing import List

class PermissionManager:
    def __init__(self, permissions_file: str = 'configs/permissions.yml'):
        self.permissions_file = permissions_file
        self.permissions = self.load_permissions()
        
        self.admin_user_id = 919498122940547072

    def load_permissions(self) -> dict:
        try:
            if os.path.exists(self.permissions_file):
                with open(self.permissions_file, 'r') as file:
                    return yaml.safe_load(file) or {}
        except Exception as e:
            print(f'Failed to load permissions: {e}')
        return {}

    def get_required_roles(self, command_name: str) -> List[int]:
        return self.permissions.get(command_name, [])

    def has_permission(self, command_name: str, user_roles: List[int], user_id: int = None) -> bool:
        
        if user_id and int(user_id) == self.admin_user_id:
            return True

        command_parts = command_name.split(' ')

        for i in range(len(command_parts)):
            parent_command = ' '.join(command_parts[:i + 1])
            required_roles = self.get_required_roles(parent_command)

            if not required_roles:
                continue

            
            if 'everyone' in required_roles:
                return True

            
            if not any(role_id in user_roles for role_id in required_roles):
                return False

        return True

    def has_group_permission(self, group_name: str, subcommand_name: str, user_roles: List[int], user_id: int = None) -> bool:
        
        if not self.has_permission(group_name, user_roles, user_id):
            return False

        
        full_command_name = f"{group_name} {subcommand_name}"
        return self.has_permission(full_command_name, user_roles, user_id)
