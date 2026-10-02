class LinuxHardware:
    def get_cpu_facts(self, collected_facts=None):
        cpu_facts = {}
        collected_facts = collected_facts or {}

        i = 0
        vendor_id_occurrence = 0
        model_name_occurrence = 0
        processor_occurence = 0
        physid = 0
        coreid = 0
        sockets = {}
        cores = {}

        xen = False
        xen_paravirt = False
        try:
            if os.path.exists('/proc/xen'):
                xen = True
            else:
                for line in get_file_lines('/sys/hypervisor/type'):
                    if line.strip() == 'xen':
                        xen = True
                    # Only interested in the first line
                    break
        except IOError:
            pass

        if not os.access("/proc/cpuinfo", os.R_OK):
            return cpu_facts

        cpu_facts['processor'] = []
        for line in get_file_lines('/proc/cpuinfo'):
            data = line.split(":", 1)
            key = data[0].strip()

            try:
                val = data[1].strip()
            except IndexError:
                val = ""

            if xen:
                if key == 'flags':
                    # Check for vme cpu flag, Xen paravirt does not expose this.
                    #   Need to detect Xen paravirt because it exposes cpuinfo
                    #   differently than Xen HVM or KVM and causes reporting of
                    #   only a single cpu core.
                    if 'vme' not in val:
                        xen_paravirt = True

            # model name is for Intel arch, Processor (mind the uppercase P)
            # works for some ARM devices, like the Sheevaplug.
            # 'ncpus active' is SPARC attribute
            if key in ['model name', 'Processor', 'vendor_id', 'cpu', 'Vendor', 'processor']:
                if 'processor' not in cpu_facts:
                    cpu_facts['processor'] = []
                cpu_facts['processor'].append(val)
                if key == 'vendor_id':
                    vendor_id_occurrence += 1
                if key == 'model name':
                    model_name_occurrence += 1
                if key == 'processor':
                    processor_occurence += 1
                i += 1
            elif key == 'physical id':
                physid = val
                if physid not in sockets:
                    sockets[physid] = 1
            elif key == 'core id':
                coreid = val
                if coreid not in sockets:
                    cores[coreid] = 1
            elif key == 'cpu cores':
                sockets[physid] = int(val)
            elif key == 'siblings':
                cores[coreid] = int(val)
            elif key == '# processors':
                cpu_facts['processor_cores'] = int(val)
            elif key == 'ncpus active':
                i = int(val)

        # Skip for platforms without vendor_id/model_name in cpuinfo (e.g ppc64le)
        if vendor_id_occurrence > 0:
            if vendor_id_occurrence == model_name_occurrence:
                i = vendor_id_occurrence

        # The fields for ARM CPUs do not always include 'vendor_id' or 'model name',
        # and sometimes includes both 'processor' and 'Processor'.
        # Always use 'processor' count for ARM systems
        if collected_facts.get('ansible_architecture', '').startswith(('armv', 'aarch')):
            i = processor_occurence

        # FIXME
        if collected_facts.get('ansible_architecture') != 's390x':
            if xen_paravirt:
                cpu_facts['processor_count'] = i
                cpu_facts['processor_cores'] = i
                cpu_facts['processor_threads_per_core'] = 1
                cpu_facts['processor_vcpus'] = i
            else:
                if sockets:
                    cpu_facts['processor_count'] = len(sockets)
                else:
                    cpu_facts['processor_count'] = i

                socket_values = list(sockets.values())
                if socket_values and socket_values[0]:
                    cpu_facts['processor_cores'] = socket_values[0]
                else:
                    cpu_facts['processor_cores'] = 1

                core_values = list(cores.values())
                if core_values:
                    cpu_facts['processor_threads_per_core'] = core_values[0] // cpu_facts['processor_cores']
                else:
                    cpu_facts['processor_threads_per_core'] = 1 // cpu_facts['processor_cores']

                cpu_facts['processor_vcpus'] = (cpu_facts['processor_threads_per_core'] *
                                                cpu_facts['processor_count'] * cpu_facts['processor_cores'])

        return cpu_facts
