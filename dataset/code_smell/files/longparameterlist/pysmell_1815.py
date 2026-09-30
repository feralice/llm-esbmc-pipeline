# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/boto/pyami/config.py#L92-L108
# smelly line(s) in the original file: 92
# smelly line(s) in this file: 8
# ids: pysmell_1815
# note: Python 2 era source, kept as found
def save_option(self, path, section, option, value):
    """
    Write the specified Section.Option to the config file specified by path.
    Replace any previous value.  If the path doesn't exist, create it.
    Also add the option the the in-memory config.
    """
    config = ConfigParser()
    config.read(path)
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, option, value)
    fp = open(path, 'w')
    config.write(fp)
    fp.close()
    if not self.has_section(section):
        self.add_section(section)
    self.set(section, option, value)
