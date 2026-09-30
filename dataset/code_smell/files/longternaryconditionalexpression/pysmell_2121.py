# smell: LongTernaryConditionalExpression
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/nltk/nltk/blob/3.0.2/nltk/internals.py#L548-L641
# smelly line(s) in the original file: 614
# smelly line(s) in this file: 74
# ids: pysmell_2121
# note: Python 2 era source, kept as found
def find_jar_iter(name_pattern, path_to_jar=None, env_vars=(),
        searchpath=(), url=None, verbose=True, is_regex=False):
    """
    Search for a jar that is used by nltk.

    :param name_pattern: The name of the jar file
    :param path_to_jar: The user-supplied jar location, or None.
    :param env_vars: A list of environment variable names to check
                     in addition to the CLASSPATH variable which is
                     checked by default.
    :param searchpath: List of directories to search.
    :param is_regex: Whether name is a regular expression.
    """

    assert isinstance(name_pattern, compat.string_types)
    assert not isinstance(searchpath, compat.string_types)
    if isinstance(env_vars, compat.string_types):
        env_vars = env_vars.split()
    yielded = False

    # Make sure we check the CLASSPATH first
    env_vars = ['CLASSPATH'] + list(env_vars)

    # If an explicit location was given, then check it, and yield it if
    # it's present; otherwise, complain.
    if path_to_jar is not None:
        if os.path.isfile(path_to_jar):
            yielded = True
            yield path_to_jar
        else:
            raise LookupError('Could not find %s jar file at %s' %
                            (name_pattern, path_to_jar))

    # Check environment variables
    for env_var in env_vars:
        if env_var in os.environ:
            if env_var == 'CLASSPATH':
                classpath = os.environ['CLASSPATH']
                for cp in classpath.split(os.path.pathsep):
                    if os.path.isfile(cp):
                        filename=os.path.basename(cp)
                        if is_regex and re.match(name_pattern, filename) or \
                                (not is_regex and filename == name_pattern):
                            if verbose:
                                print('[Found %s: %s]' % (name_pattern, cp))
                            yielded = True
                            yield cp
            else:
                jar_env = os.environ[env_var]
                jar_iter = ((os.path.join(jar_env, path_to_jar) for path_to_jar in os.listdir(jar_env))
                            if os.path.isdir(jar_env) else (jar_env,))
                for path_to_jar in jar_iter:
                    if os.path.isfile(path_to_jar):
                        filename=os.path.basename(path_to_jar)
                        if is_regex and re.match(name_pattern, filename) or \
                                (not is_regex and filename == name_pattern):
                            if verbose:
                                print('[Found %s: %s]' % (name_pattern, path_to_jar))
                            yielded = True
                            yield path_to_jar

    # Check the path list.
    for directory in searchpath:
        if is_regex:
            for filename in os.listdir(directory):
                path_to_jar = os.path.join(directory, filename)
                if os.path.isfile(path_to_jar):
                    if re.match(name_pattern, filename):
                        if verbose:
                            print('[Found %s: %s]' % (filename, path_to_jar))
                yielded = True
                yield path_to_jar
        else:
            path_to_jar = os.path.join(directory, name_pattern)
            if os.path.isfile(path_to_jar):
                if verbose:
                    print('[Found %s: %s]' % (name_pattern, path_to_jar))
                yielded = True
                yield path_to_jar

    if not yielded:
        # If nothing was found, raise an error
        msg = ("NLTK was unable to find %s!" % name_pattern)
        if env_vars: msg += ' Set the %s environment variable' % env_vars[0]
        msg = textwrap.fill(msg+'.', initial_indent='  ',
                            subsequent_indent='  ')
        if searchpath:
            msg += '\n\n  Searched in:'
            msg += ''.join('\n    - %s' % d for d in searchpath)
        if url:
            msg += ('\n\n  For more information, on %s, see:\n    <%s>' %
                    (name_pattern, url))
        div = '='*75
        raise LookupError('\n\n%s\n%s\n%s' % (div, msg, div))
