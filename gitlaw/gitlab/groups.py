"""Manages configuration at /groups gitlab API."""
from gitlab.exceptions import GitlabGetError

class Groups:
    """Groups class."""
    def __init__(self, gl, config) -> None:
        """Init method.

        Args:
        gl: Object with gitlab auth
        config: Groups config data
        """
        self.gl = gl
        if config is not None:
            self.config = config
        else:
            self.config = {}

    def manager(self, auto_create_groups=True) -> None:
        """Orchestrates the other class methods.

        Args:
        auto_create_groups: Boolean defaults to True
        """
        user_group = self._set_defaults(self.config.get('name', None),
                                        self.config.get('description', ""),
                                        self.config.get('policy', None))
        server_object = self.get_groups(auto_create_groups)
        self.eval_changes(user_group, server_object)
        print(f"Configuring members of group {self.config.get('name', None)}...")
        self.configure_members(members=self.config.get('members', None), server_obj=server_object)
        srv_projects = self.list_projects(server_object)
        print(f"Configuring projects for group {self.config.get('name', None)}...")

        # Iterate over server projects, if project is not in user defined list,
        # adds the project into the user list for default configuration.
        # If projects is not defined in the config file, force creation
        # so projects can be configured with default values.
        for srv in srv_projects:
            try:
                if not any(x.get('name') == srv.name for x in self.config.get('projects', [])):
                    self.config.get('projects').append({'name': srv.name})
            except AttributeError:
                self.config['projects'] = [{'name': srv.name}]

        # With the full list of projects configure each one
        for project in self.config.get('projects', []):
            project_defaults = self._set_project_defaults(project.get('name'), policy=project.get('policy', {}))
            print(f"Configuring project {project.get('name')}...")
            self.eval_project_changes(project_defaults)
    def get_groups(self, auto_create_groups) -> dict:
        """Query config data from the API.

        Args:
        auto_create_groups: Boolean defaults to True

        Returns: dict
        """
        try:
            group = self.gl.groups.get(self.config.get('name'))
        except GitlabGetError as exc:
            if auto_create_groups:
                group = self.gl.groups.create({'name': self.config.get('name'),
                                               'path': self.config.get('name')})
            else:
                raise GitlabGetError(f"Group {self.config.get('name')} does not exists "
                                f"and auto_create_groups is disabled") from exc
        return group

    def _set_defaults(self, name, description, policy):
        """Set default values if not defined in the yaml config file.
        
        Args:
        name: Group name
        description: Group description
        policy: Group policy config data
        """
        defaults = {}
        defaults['name'] = name
        defaults['description'] = description
        defaults['visibility'] = policy.get('visibility', "private")
        defaults['auto_devops_enabled'] = policy.get('auto_devops_enabled', False)
        defaults['default_branch'] = policy.get('default_branch', "main")
        defaults['enabled_git_access_protocol'] = self.config.get('enabled_git_access_protocol', None)

        defaults['lfs_enabled'] = policy.get('lfs_enabled', True)
        defaults['project_creation_level'] = policy.get('project_creation_level', "maintainer")
        defaults['subgroup_creation_level'] = policy.get('subgroup_creation_level', "maintainer")
        defaults['wiki_access_level'] = policy.get('wiki_access_level', "private")
        defaults['request_access_enabled'] = policy.get('request_access_enabled', True)
        defaults['require_two_factor_authentication'] = policy.get('require_two_factor_authentication', False)
        defaults['default_branch_protection_defaults'] = policy.get(
            'default_branch_protection_defaults', {'allowed_to_push': [{'access_level': 40}], 
                                                   'allow_force_push': False, 
                                                   'allowed_to_merge': [{'access_level': 40}], 
                                                   'developer_can_initial_push': False})

        return defaults

    def eval_changes(self, user_group, server_obj):
        """Checks for changes on group api.

        Evaluate if the config file data provided match with data in GitLab group API,
        if does not match, set value with the user data and store changes in the API"""
        for key, value in user_group.items():
            try:
                # Some user provided data might me None and continuing the loop will fail.
                if value is not None and getattr(server_obj, key) != value:
                    print(f"Expected value `{key}: {value}` does not match with remote "
                          f"`{getattr(server_obj, key)}`")
                    setattr(server_obj, key, value)
                server_obj.save()
            except AttributeError:
                # When some attribute is only present in licensed servers, the attribute
                # does not exists in the API and raises this exception.
                pass

    def configure_members(self, members, server_obj):
        """Add or update members of a group.

        """
        try:
            # if members is not None
            for member in (members) or []:
                existing_user = self.gl.users.list(username=member.get('name'))[0]
                user_id = existing_user.id
                try:
                    group_member = server_obj.members.get(user_id)
                    if member.get('access_level') != group_member.access_level:
                        print(f"Expected access_level for member `{member.get('name')}: {member.get('access_level')}` "
                          f"does not match with remote `{group_member.access_level}`")
                        group_member.access_level = member.get('access_level')
                        group_member.save()
                except GitlabGetError:
                    print(f"Creating group member {member.get('name')}")
                    server_obj.members.create({'user_id': user_id,
                                            'access_level': member.get('access_level')})
        except IndexError as exc:
            raise IndexError(f"User {member.get('name')} does not exists") from exc

    def list_projects(self, srv_object):
        """List projects of a group."""
        projects = srv_object.projects.list()
        return projects


    def _set_project_defaults(self, name, policy):
        """Set default values if not defined in the yaml config file.
        
        Args:
        name: Group name
        description: Group description
        policy: Group policy config data
        """
        defaults = {}
        defaults['name'] = name
        defaults['visibility'] = policy.get('visibility', "private")
        defaults['git_strategy'] = policy.get('git_strategy', "fetch")
        defaults['build_timeout'] = policy.get('build_timeout', 3600)
        defaults['ci_config_path'] = policy.get('ci_config_path', None)
        defaults['group_runners_enabled'] = policy.get('group_runners_enabled', True)
        defaults['issues_template'] = policy.get('issues_template', None)
        defaults['merge_commit_template'] = policy.get('merge_commit_template', None)
        defaults['max_artifacts_size'] = policy.get('max_artifacts_size', None)
        defaults['lfs'] = policy.get('lfs', True)
        defaults['merge_method'] = policy.get('merge_method', "merge")
        defaults['merge_pipelines_enabled'] = policy.get('merge_pipelines_enabled', True)
        defaults['merge_trains_enabled'] = policy.get('merge_trains_enabled', True)
        defaults['only_allow_merge_if_all_discussions_are_resolved'] = \
            policy.get('only_allow_merge_if_all_discussions_are_resolved', False)
        defaults['only_allow_merge_if_pipeline_succeeds'] = policy.get('only_allow_merge_if_pipeline_succeeds', False)
        defaults['packages_enabled'] = policy.get('packages_enabled', True)
        defaults['public_jobs'] = policy.get('public_jobs', True)
        defaults['remove_source_branch_after_merge'] = policy.get('remove_source_branch_after_merge', True)
        defaults['request_access_enabled'] = policy.get('request_access_enabled', True)
        defaults['resolve_outdated_diff_discussions'] = policy.get('resolve_outdated_diff_discussions', False)
        defaults['shared_runners_enabled'] = policy.get('shared_runners_enabled', True)
        defaults['squash_option'] = policy.get('squash_option', "default_off")
        # defaults['visibility'] = policy.get('visibility', "private")
        # defaults['visibility'] = policy.get('visibility', "private")
        # defaults['visibility'] = policy.get('visibility', "private")
        # defaults['visibility'] = policy.get('visibility', "private")
        # defaults['visibility'] = policy.get('visibility', "private")
        # defaults['visibility'] = policy.get('visibility', "private")
        return defaults


    def eval_project_changes(self, user_project):
        """Checks for changes on group api.

        Evaluate if the config file data provided match with data in GitLab group API,
        if does not match, set value with the user data and store changes in the API"""
        project_id = self.gl.projects.list(search=user_project.get('name'))[0].id
        project = self.gl.projects.get(project_id)
        for key, value in user_project.items():
            try:
                # Some user provided data might me None and continuing the loop will fail.
                if value is not None and getattr(project, key) != value:
                    print(f"Expected value in project {project.name} `{key}: {value}` does not match with remote "
                          f"`{getattr(project, key)}`")
                    setattr(project, key, value)
                    project.save()
            except AttributeError:
                # When some attribute is only present in licensed servers, the attribute
                # does not exists in the API and raises this exception.
                pass
