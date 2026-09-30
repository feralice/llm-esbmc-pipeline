# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/ansible/ansible/blob/v1.9.2-0.1.rc1/lib/ansible/playbook/__init__.py#L579-L641
# smelly line(s) in the original file: 585
# smelly line(s) in this file: 14
# ids: pysmell_0026
# note: Python 2 era source, kept as found
def _do_setup_step(self, play):
    ''' get facts from the remote system '''

    host_list = self._trim_unavailable_hosts(play._play_hosts)

    if play.gather_facts is None and C.DEFAULT_GATHERING == 'smart':
        host_list = [h for h in host_list if h not in self.SETUP_CACHE or 'module_setup' not in self.SETUP_CACHE[h]]
        if len(host_list) == 0:
            return {}
    elif play.gather_facts is False or (play.gather_facts is None and C.DEFAULT_GATHERING == 'explicit'):
        return {}

    self.callbacks.on_setup()
    self.inventory.restrict_to(host_list)

    ansible.callbacks.set_task(self.callbacks, None)
    ansible.callbacks.set_task(self.runner_callbacks, None)

    # push any variables down to the system
    setup_results = ansible.runner.Runner(
        basedir=self.basedir,
        pattern=play.hosts,
        module_name='setup',
        module_args={},
        inventory=self.inventory,
        forks=self.forks,
        module_path=self.module_path,
        timeout=self.timeout,
        remote_user=play.remote_user,
        remote_pass=self.remote_pass,
        remote_port=play.remote_port,
        private_key_file=self.private_key_file,
        setup_cache=self.SETUP_CACHE,
        vars_cache=self.VARS_CACHE,
        callbacks=self.runner_callbacks,
        become=play.become,
        become_method=play.become_method,
        become_user=play.become_user,
        become_pass=self.become_pass,
        vault_pass=self.vault_password,
        transport=play.transport,
        is_playbook=True,
        module_vars=play.vars,
        play_vars=play.vars,
        play_file_vars=play.vars_file_vars,
        role_vars=play.role_vars,
        default_vars=play.default_vars,
        check=self.check,
        diff=self.diff,
        accelerate=play.accelerate,
        accelerate_port=play.accelerate_port,
    ).run()
    self.stats.compute(setup_results, setup=True)

    self.inventory.lift_restriction()

    # now for each result, load into the setup cache so we can
    # let runner template out future commands
    setup_ok = setup_results.get('contacted', {})
    for (host, result) in setup_ok.iteritems():
        utils.update_hash(self.SETUP_CACHE, host, {'module_setup': True})
        utils.update_hash(self.SETUP_CACHE, host, result.get('ansible_facts', {}))
    return setup_results
