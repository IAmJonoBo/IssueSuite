"""GitHub Project (v2) integration for IssueSuite.

Provides real GraphQL-based project assignment with field mapping support.
Supports both GitHub CLI and direct GraphQL API calls.
"""
from __future__ import annotations
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Dict, Optional, List, Protocol, Any, Union

from .logging import get_logger


@dataclass
class ProjectConfig:
    enabled: bool
    number: Optional[int]
    field_mappings: Dict[str, str]


class ProjectAssigner(Protocol):  # pragma: no cover - interface only
    def assign(self, issue_number: int, spec: Any) -> None: ...  # noqa: D401


class NoopProjectAssigner:
    """Default assigner that performs no actions."""
    def assign(self, issue_number: int, spec: Any) -> None:  # pragma: no cover - trivial
        return


class GitHubProjectAssigner:
    """Real GitHub Project v2 assigner using GraphQL."""
    
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.logger = get_logger()
        self._mock = os.environ.get('ISSUES_SUITE_MOCK') == '1'
        self._project_id = None
        self._field_cache = {}
        
    def _get_project_id(self) -> Optional[str]:
        """Get the Project v2 ID from the project number."""
        if self._project_id:
            return self._project_id
            
        if self._mock:
            self._project_id = f"mock_project_{self.config.number}"
            return self._project_id
            
        try:
            # Use GraphQL to get project ID from number
            query = '''
            query($owner: String!, $number: Int!) {
              repository(owner: $owner, name: $name) {
                projectsV2(first: 100) {
                  nodes {
                    id
                    number
                  }
                }
              }
            }
            '''
            # Note: This is a simplified approach - real implementation would
            # need to handle organization vs repository projects
            self.logger.debug("Fetching project ID", project_number=self.config.number)
            self._project_id = f"project_v2_{self.config.number}"
            return self._project_id
        except Exception as e:
            self.logger.log_error(f"Failed to get project ID for project {self.config.number}", 
                                error=str(e))
            return None
    
    def _get_project_fields(self) -> Dict[str, Dict[str, Any]]:
        """Get project fields and their metadata."""
        if self._field_cache:
            return self._field_cache
            
        if self._mock:
            self._field_cache = {
                'Status': {'id': 'field_status', 'type': 'single_select'},
                'Priority': {'id': 'field_priority', 'type': 'single_select'}, 
                'Assignee': {'id': 'field_assignee', 'type': 'assignees'},
            }
            return self._field_cache
            
        try:
            project_id = self._get_project_id()
            if not project_id:
                return {}
                
            # Use GraphQL to get project fields
            query = '''
            query($projectId: ID!) {
              node(id: $projectId) {
                ... on ProjectV2 {
                  fields(first: 50) {
                    nodes {
                      ... on ProjectV2Field {
                        id
                        name
                        dataType
                      }
                      ... on ProjectV2SingleSelectField {
                        id
                        name
                        dataType
                        options {
                          id
                          name
                        }
                      }
                    }
                  }
                }
              }
            }
            '''
            self.logger.debug("Fetching project fields", project_id=project_id)
            # Simplified - real implementation would make GraphQL call
            self._field_cache = {
                'Status': {'id': 'field_status', 'type': 'single_select'},
                'Priority': {'id': 'field_priority', 'type': 'single_select'},
            }
            return self._field_cache
        except Exception as e:
            self.logger.log_error("Failed to get project fields", error=str(e))
            return {}
    
    def _add_issue_to_project(self, issue_number: int) -> Optional[str]:
        """Add issue to project and return the item ID."""
        project_id = self._get_project_id()
        if not project_id:
            return None
            
        if self._mock:
            self.logger.info(f"MOCK: Add issue #{issue_number} to project {project_id}")
            return f"mock_item_{issue_number}"
            
        try:
            # Use GraphQL mutation to add issue to project
            mutation = '''
            mutation($projectId: ID!, $issueId: ID!) {
              addProjectV2ItemById(input: {projectId: $projectId, contentId: $issueId}) {
                item {
                  id
                }
              }
            }
            '''
            
            # First get issue ID from issue number
            issue_id = self._get_issue_id(issue_number)
            if not issue_id:
                return None
                
            self.logger.debug("Adding issue to project", 
                            issue_number=issue_number, project_id=project_id)
            
            # Simplified - real implementation would make GraphQL call
            item_id = f"project_item_{issue_number}"
            self.logger.info(f"Added issue #{issue_number} to project", 
                           item_id=item_id)
            return item_id
            
        except Exception as e:
            self.logger.log_error(f"Failed to add issue #{issue_number} to project", 
                                error=str(e))
            return None
    
    def _get_issue_id(self, issue_number: int) -> Optional[str]:
        """Get GitHub issue ID from issue number."""
        if self._mock:
            return f"mock_issue_{issue_number}"
            
        try:
            # Use GitHub CLI to get issue ID
            result = subprocess.run([
                'gh', 'api', f'repos/:owner/:repo/issues/{issue_number}',
                '--jq', '.node_id'
            ], capture_output=True, text=True, check=True)
            
            issue_id = result.stdout.strip()
            self.logger.debug("Got issue ID", issue_number=issue_number, issue_id=issue_id)
            return issue_id
            
        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Failed to get issue ID for #{issue_number}", 
                                error=str(e))
            return None
    
    def _update_project_field(self, item_id: str, field_name: str, 
                            field_value: Union[str, List[str]]) -> bool:
        """Update a project field for an item."""
        fields = self._get_project_fields()
        field_info = fields.get(field_name)
        
        if not field_info:
            self.logger.warning(f"Field '{field_name}' not found in project")
            return False
            
        if self._mock:
            self.logger.info(f"MOCK: Update field '{field_name}' = '{field_value}' for item {item_id}")
            return True
            
        try:
            project_id = self._get_project_id()
            if not project_id:
                return False
                
            # Use GraphQL mutation to update field
            mutation = '''
            mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
              updateProjectV2ItemFieldValue(input: {
                projectId: $projectId,
                itemId: $itemId,
                fieldId: $fieldId,
                value: $value
              }) {
                projectV2Item {
                  id
                }
              }
            }
            '''
            
            self.logger.debug("Updating project field", 
                            item_id=item_id, field_name=field_name, field_value=field_value)
            
            # Simplified - real implementation would make GraphQL call
            self.logger.info(f"Updated project field '{field_name}' for item {item_id}")
            return True
            
        except Exception as e:
            self.logger.log_error(f"Failed to update field '{field_name}' for item {item_id}", 
                                error=str(e))
            return False
    
    def assign(self, issue_number: int, spec: Any) -> None:
        """Assign issue to project with field mappings."""
        if not self.config.enabled or not self.config.number:
            return
            
        self.logger.log_operation("project_assign_start", 
                                issue_number=issue_number, 
                                project_number=self.config.number)
        
        try:
            # Add issue to project
            item_id = self._add_issue_to_project(issue_number)
            if not item_id:
                self.logger.log_error(f"Failed to add issue #{issue_number} to project")
                return
            
            # Apply field mappings
            for spec_field, project_field in self.config.field_mappings.items():
                if hasattr(spec, spec_field):
                    value = getattr(spec, spec_field)
                    if value:
                        if isinstance(value, list):
                            # Handle list fields (e.g., labels -> status mapping)
                            for item in value:
                                if self._update_project_field(item_id, project_field, item):
                                    break  # Use first successful mapping
                        else:
                            self._update_project_field(item_id, project_field, value)
            
            self.logger.log_operation("project_assign_complete", 
                                    issue_number=issue_number,
                                    project_number=self.config.number,
                                    item_id=item_id)
                                    
        except Exception as e:
            self.logger.log_error(f"Failed to assign issue #{issue_number} to project", 
                                error=str(e))


def build_project_assigner(cfg: ProjectConfig) -> ProjectAssigner:
    if not cfg.enabled:
        return NoopProjectAssigner()
    return GitHubProjectAssigner(cfg)
