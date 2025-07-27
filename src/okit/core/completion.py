import os
import sys
import platform
import subprocess
from pathlib import Path
import click

def detect_shell():
    """
    Detect the current shell type. Return one of SUPPORTED_SHELLS or None.
    Compatible with Windows git bash.
    """
    shell = os.environ.get("SHELL", "").lower()
    if not shell and os.name == "nt":
        # On Windows, try to detect git bash or others
        msystem = os.environ.get("MSYSTEM", "").lower()
        if msystem.startswith("mingw") or msystem == "gitbash":
            return "bash"
        # Try to detect from parent process
        try:
            import psutil
            parent = psutil.Process(os.getppid())
            pname = parent.name().lower()
            if "bash" in pname:
                return "bash"
            if "zsh" in pname:
                return "zsh"
            if "fish" in pname:
                return "fish"
        except Exception:
            pass
    for s in get_supported_shells():
        if s in shell:
            return s
    return None


def get_home_dir():
    """Get user's home directory as Path object."""
    return Path.home()


def get_completion_file(shell, for_shell_rc=False):
    """
    Get the path to the completion script file for the given shell.
    If for_shell_rc is True, return '~/.okit-complete.{shell}' for shell config.
    Otherwise, return absolute Path for file writing.
    """
    if for_shell_rc:
        return f"~/.okit-complete.{shell}"
    else:
        return Path.home() / f".okit-complete.{shell}"


def get_rc_files(shell):
    """Get the list of rc files for the given shell."""
    return [get_home_dir() / rc for rc in get_shell_rc_files().get(shell, [])]


def is_source_line_present(rc_path, completion_file):
    """Check if the source line is already present in the rc file."""
    if not rc_path.exists():
        return False
    try:
        content = rc_path.read_text(encoding="utf-8")
        return str(completion_file) in content
    except Exception:
        return False


def append_source_line(rc_path, shell, completion_file):
    """Append the source line to the rc file if not present."""
    # Always use ~ for home in shell config
    line = f"source {completion_file}"
    try:
        with rc_path.open("a", encoding="utf-8") as f:
            f.write(f"\n# Enable okit CLI completion\n{line}\n")
    except Exception as e:
        print(f"Failed to write to {rc_path}: {e}", file=sys.stderr)


def generate_completion_script(shell: str, program_name: str) -> str:
    """
    Generate shell completion script by invoking the CLI itself with the correct env var.
    Compatible with click >=8.1.x, including 8.2.x (no get_completion_script API).
    """
    env = os.environ.copy()
    env_var = f"_{program_name.replace('-', '_').upper()}_COMPLETE"
    env[env_var] = f"{shell}_source"
    # Try to find the executable in PATH
    exe = program_name
    # If running as a module, sys.argv[0] may be python, so prefer program_name
    result = subprocess.run(
        [exe],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8"
    )
    if result.returncode == 0:
        return result.stdout
    else:
        raise RuntimeError(f"Failed to generate completion script: {result.stderr}")


def write_completion_script(shell):
    """Generate and write the completion script for the given shell."""
    completion_file = get_completion_file(shell, for_shell_rc=False)
    try:
        script = generate_completion_script(shell, get_program_name())
        # 强制使用 LF 换行
        with open(completion_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(script)
        return completion_file
    except Exception as e:
        print(f"Failed to write completion script for {shell}: {e}", file=sys.stderr)
        return None


def get_source_command(shell):
    """Return the shell-specific source command for immediate effect."""
    if shell == "bash":
        return "source ~/.bashrc"
    elif shell == "zsh":
        return "source ~/.zshrc"
    elif shell == "fish":
        return "source ~/.config/fish/config.fish"
    else:
        return None


def auto_enable_completion_if_possible():
    """
    Try to auto-enable shell completion for supported shells.
    This should be called at CLI startup.
    """
    shell = detect_shell()
    if shell not in get_supported_shells():
        return
    completion_file_abs = get_completion_file(shell, for_shell_rc=False)
    completion_file_tilde = get_completion_file(shell, for_shell_rc=True)
    completion_file = write_completion_script(shell)
    if not completion_file:
        return
    for rc_path in get_rc_files(shell):
        if not is_source_line_present(rc_path, completion_file_tilde):
            append_source_line(rc_path, shell, completion_file_tilde) 


def enable_completion():
    """Manually enable shell completion for the current shell."""
    shell = detect_shell()
    if shell not in get_supported_shells():
        click.echo("Shell completion is only supported for bash, zsh, fish.")
        return
    completion_file_abs = get_completion_file(shell, for_shell_rc=False)
    completion_file_tilde = get_completion_file(shell, for_shell_rc=True)
    completion_file = write_completion_script(shell)
    if not completion_file:
        click.echo(f"Failed to write completion script for {shell}.")
        return
    updated = False
    for rc_path in get_rc_files(shell):
        if not is_source_line_present(rc_path, completion_file_tilde):
            append_source_line(rc_path, shell, completion_file_tilde)
            click.echo(f"Added completion source to {rc_path}")
            updated = True
    if not updated:
        click.echo("Completion source already present in shell config.")
    else:
        click.echo(f"Completion enabled for {shell}.")
        source_cmd = get_source_command(shell)
        if source_cmd:
            click.echo(f"To activate completion now, run: {source_cmd}")
        else:
            click.echo("Please restart your shell or source your rc file.")


def disable_completion():
    """Manually disable shell completion for the current shell."""
    shell = detect_shell()
    if shell not in get_supported_shells():
        click.echo("Shell completion is only supported for bash, zsh, fish.")
        return
    completion_file_tilde = get_completion_file(shell, for_shell_rc=True)
    removed = False
    for rc_path in get_rc_files(shell):
        if not rc_path.exists():
            continue
        try:
            lines = rc_path.read_text(encoding="utf-8").splitlines()
            new_lines = []
            skip = False
            for line in lines:
                if line.strip() == f"# Enable okit CLI completion":
                    skip = True
                    continue
                if skip and line.strip().startswith("source ") and completion_file_tilde in line:
                    skip = False
                    removed = True
                    continue
                skip = False
                new_lines.append(line)
            rc_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        except Exception as e:
            click.echo(f"Failed to update {rc_path}: {e}")
    # 可选：删除补全脚本文件
    completion_file_abs = get_completion_file(shell, for_shell_rc=False)
    try:
        if completion_file_abs.exists():
            completion_file_abs.unlink()
            click.echo(f"Deleted completion script: {completion_file_abs}")
    except Exception as e:
        click.echo(f"Failed to delete completion script: {e}")
    if removed:
        click.echo("Completion disabled.")
        source_cmd = get_source_command(shell)
        if source_cmd:
            click.echo(f"To reload your shell config now, run: {source_cmd}")
        else:
            click.echo("Please restart your shell or source your rc file.")
    else:
        click.echo("No okit completion source found in shell config.")


@click.group()
def completion():
    """Manage shell completion for okit CLI."""
    pass

@completion.command()
def enable():
    """Enable shell completion for okit CLI."""
    enable_completion()

@completion.command()
def disable():
    """Disable shell completion for okit CLI."""
    disable_completion() 


def get_supported_shells():
    return ["bash", "zsh", "fish"]

def get_shell_rc_files():
    return {
        "bash": [".bashrc", ".bash_profile"],
        "zsh": [".zshrc"],
        "fish": [os.path.join(".config", "fish", "config.fish")],
    }

def get_program_name():
    return "okit"

def get_completion_file_template():
    return ".okit-complete.{shell}" 