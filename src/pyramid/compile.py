from pathlib import Path
import shutil
from Cython.Build import cythonize
from setuptools import Extension
from setuptools.dist import Distribution
from typing import Callable, List, Optional


class CythonCompiler:
    """Compiles Python and Cython source files from a project into a build directory."""

    DEFAULT_IGNORES = {"__pycache__", ".venv", ".git", ".tmp"}
    FORCE_COPY_NAMES = {"setup.py", "__init__.py", "main.py"}
    COMPILE_EXTENSIONS = {".pyx", ".py"}

    def __init__(
        self,
        output_dir: str,
        skip_and_copy_predicate: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """Initializes the compiler with an output directory and a predicate for copy-only files."""
        self.output_dir = Path(output_dir).resolve()
        self.temp_build = self.output_dir / ".tmp"
        self.skip_and_copy_predicate = skip_and_copy_predicate or (lambda _: False)

    def _run_distribution_build(self, extensions: List[Extension]) -> None:
        """Builds and writes compiled extensions to the configured output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_build.mkdir(parents=True, exist_ok=True)

        try:
            dist = Distribution(
                {
                    "ext_modules": cythonize(
                        extensions,
                        compiler_directives={"language_level": "3"},
                        build_dir=str(self.temp_build),
                    )
                }
            )
            dist.finalize_options()

            build_ext = dist.get_command_obj("build_ext")
            build_ext.ensure_finalized()

            build_ext.build_lib = str(self.output_dir)
            build_ext.build_temp = str(self.temp_build)
            build_ext.inplace = False

            dist.run_command("build_ext")
        finally:
            self._cleanup_temp()

    def _cleanup_temp(self) -> None:
        """Removes the temporary build directory after compilation completes."""
        if self.temp_build.exists():
            shutil.rmtree(self.temp_build)

    def _should_ignore(self, file_path: Path, relative_str: str) -> bool:
        """Determines whether a given file should be excluded from compilation or copying."""
        if file_path.is_relative_to(self.output_dir):
            return True
        if not file_path.is_file():
            return True
        if any(part in self.DEFAULT_IGNORES for part in file_path.parts):
            return True
        return False

    def compile_project(self, project_dir: str) -> None:
        """Scans a project directory, compiles source files, and copies non-compilable files."""
        project_path = Path(project_dir).resolve()
        if not project_path.is_dir():
            raise NotADirectoryError(
                f"Project path must be a directory: {project_path}"
            )

        extensions: List[Extension] = []
        files_to_copy: List[tuple[Path, Path]] = []

        for file_path in project_path.rglob("*"):
            relative_path = file_path.relative_to(project_path)
            relative_str = str(relative_path)

            if self._should_ignore(file_path, relative_str):
                continue

            is_forced_copy = file_path.name in self.FORCE_COPY_NAMES
            is_user_skipped = self.skip_and_copy_predicate(relative_str)

            if is_forced_copy or is_user_skipped:
                files_to_copy.append((file_path, relative_path))
                continue

            if file_path.suffix in self.COMPILE_EXTENSIONS:
                module_name = ".".join(relative_path.with_suffix("").parts)
                extensions.append(Extension(module_name, [str(file_path)]))
            else:
                files_to_copy.append((file_path, relative_path))

        if extensions:
            self._run_distribution_build(extensions)

        for src_file, rel_path in files_to_copy:
            dest_file = self.output_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)
