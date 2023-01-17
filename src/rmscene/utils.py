import subprocess
import sys


def run_command(command, **kwargs):
    env = kwargs.get('env', None)
    stdin = subprocess.PIPE if kwargs.get('stdin', False) else None
    bufsize = kwargs.get('bufsize', 0)
    universal_newlines = kwargs.get('universal_newlines', False)
    default_close_fds = True if sys.platform == 'linux2' else False
    close_fds = kwargs.get('close_fds', default_close_fds)
    shell = type(command) in (type(''), type(u''))
    dry_run = kwargs.get('dry_run', False)
    if dry_run:
        return 0, b'stdout', b'stderr'
    p = subprocess.Popen(command, stdin=stdin, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, bufsize=bufsize,
                         universal_newlines=universal_newlines,
                         env=env, close_fds=close_fds, shell=shell)
    # wait for the command to terminate
    if stdin is not None:
        out, err = p.communicate(stdin)
    else:
        out, err = p.communicate()
    returncode = p.returncode
    # clean up
    del p
    # return results
    return returncode, out, err
