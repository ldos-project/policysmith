import re
import subprocess

# https://stackoverflow.com/questions/241327/remove-c-and-c-comments-using-python/1294188#1294188
def cpp_comment_remover(text):
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " " # note: a space and not an empty string
        else:
            return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    return re.sub(pattern, replacer, text)

def get_git_info(dir_path=None):
    git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=dir_path).decode().strip()
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=dir_path).decode()
    return {'hash': git_hash, 'status': status}