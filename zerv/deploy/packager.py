# from datetime import datetime
# from distutils.dir_util import copy_tree
# import glob
import os
# import pip
# import runpy
import shutil
import tempfile

# import click
# import virtualenv

from chalice.utils import OSUtils, UI
from chalice.deploy.packager import (
    DependencyBuilder as PipDependencyBuilder,
    LambdaDeploymentPackager,
    PipRunner,
    SubprocessPip
)

from zerv.utils import zip_write_dir

class MutedUI(UI):
    def write(*args, **kwargs):
        pass


class ChaliceLambdaDeploymentPackager(LambdaDeploymentPackager):
    _VENDOR_DIR = 'vendor'
    _IGNORED_APP_FILES = ['.chalice', '.ds_store', 'requirements.txt']

    def _get_zerv_init(self):
        temp = tempfile.NamedTemporaryFile()
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(temp.name, 0o666 & ~umask)
        return temp

    def _add_zerv(self, zip_fileobj):
        zerv_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        init_file = self._get_zerv_init()
        zip_fileobj.write(init_file.name, 'zerv/__init__.py')

        zerv_api_path = os.path.join(zerv_path, 'api')
        zip_write_dir(zip_fileobj, zerv_api_path, files_prefix='zerv/api')

    def _add_app_files(self, zip_fileobj, project_dir):
        for file_name in os.listdir(project_dir):
            if file_name in self._IGNORED_APP_FILES or file_name.endswith('.pyc'):
                continue

            file_path = os.path.join(project_dir, file_name)
            zip_fileobj.write(file_path, 'function/%s' % file_name)

        self._add_zerv(zip_fileobj)

class Packager(object):
    def __init__(self, source_code_path, *args, **kwargs):
        self.source_code_path = source_code_path
        self._osutils = OSUtils()
        self._ui = MutedUI()

    def load_package(self):
        """Read content from zipped-package.
        """
        package = open(self.package_path, 'rb')
        return package.read()

    def package(self):
        pip_runner = PipRunner(
            pip=SubprocessPip(osutils=self._osutils),
            osutils=self._osutils
        )

        dependency_builder = PipDependencyBuilder(
            osutils=self._osutils,
            pip_runner=pip_runner
        )

        packager = ChaliceLambdaDeploymentPackager(
            osutils=self._osutils,
            dependency_builder=dependency_builder,
            ui=self._ui,
        )

        self.package_path = packager.create_deployment_package(
            self.source_code_path,
            'python3.6'
        )
        package_content = self.load_package()
        self.cleanup()
        return package_content

    def cleanup(self):
        chalice_dir = '%s/.chalice' % self.source_code_path
        shutil.rmtree(chalice_dir, ignore_errors=True)

# class DeprecatedPackager(object):
#     DEFAULT_FUNCTION_FOLDER = 'function'

#     def __init__(self, function_name, source_code_path, debug=False):
#         temp_version = datetime.now().strftime('%Y%m%d_%H%M%S')
#         dir_prefix = '.zerv_%s_%s' % (function_name, temp_version)
#         venv_prefix = '%s_venv' % dir_prefix
#         build_prefix = '%s_build' % dir_prefix

#         self.source_code_path = source_code_path
#         self.debug = debug
#         # Create all temp files needed.
#         self.build_temp = tempfile.TemporaryDirectory(prefix=build_prefix)
#         self.build_path = self.build_temp.name
#         self.venv_temp = tempfile.TemporaryDirectory(prefix=venv_prefix)
#         self.venv_path = self.venv_temp.name
#         self.zip_temp = tempfile.NamedTemporaryFile()
#         self.zip_path = self.zip_temp.name
#         self.package_path = None

#     def install_dependencies(self):
#         """Install dependencies received
#         """
#         # TODO: Optimize this to avoid creating a venv from scratch
#         # TODO: Find a way to install only manylinux compatible versions without any noise/useless packages
#         if self.debug:
#             click.secho('    Installing dependencies...', blink=True, fg='black', bold=True)

#         pip.main(["install", '--prefix', self.venv_path, 'requests', '--quiet', '--ignore-installed'])
#         site_packages_pattern = os.path.join(self.venv_path, 'lib', 'python3.*', 'site-packages')
#         site_package_paths = glob.glob(site_packages_pattern)

#         for site_package_path in site_package_paths:
#             copy_tree(site_package_path, self.build_path)

#     def create_virtualenv(self):
#         """Create virtualenv into which dependencies will be installed
#         """
#         if self.debug:
#             click.secho('    Creating virtualenv...', blink=True, fg='black', bold=True)

#         virtualenv.create_environment(self.venv_path)
#         activate_path = os.path.join(self.venv_path, 'bin', 'activate_this.py')
#         runpy.run_path(activate_path)

#     def zip_package(self):
#         """Put package temp folder content into a zip file
#         """
#         if self.debug:
#             click.secho('    Creating archive...', blink=True, fg='black', bold=True)

#         self.package_path = shutil.make_archive(self.zip_path, format='zip', root_dir=self.build_path)
#         temp_version = datetime.now().strftime('%Y%m%d_%H%M%S')
#         shutil.copyfile(self.package_path, '/Users/henocdz/Downloads/' + temp_version)

#     def load_package(self):
#         """Read content from zipped-package.
#         """
#         package = open(self.package_path, 'rb')
#         return package.read()

#     def package_source_code(self):
#         """Move function source code into package temp folder
#         """
#         if self.debug:
#             click.secho('    Copying source code...', blink=True, fg='black', bold=True)
#         source_path = os.path.join(self.build_path, self.DEFAULT_FUNCTION_FOLDER)
#         copy_tree(self.source_code_path, source_path)

#         init_path = os.path.join(source_path, '__init__.py')
#         if not os.path.exists(init_path):
#             with open(init_path, 'w'): pass

#     def package(self):
#         """Execute all packaging steps
#         """
#         # self.create_virtualenv()
#         # self.install_dependencies()
#         self.package_source_code()
#         self.zip_package()
#         package_content = self.load_package()
#         self.cleanup()
#         return package_content

#     def cleanup(self):
#         """Delete all files and directories created during packaging.
#         """
#         if self.debug:
#             click.secho('    Cleaning up...', blink=True, fg='black', bold=True)
#         self.venv_temp.cleanup()
#         self.build_temp.cleanup()
#         # self.zip_temp will be cleaned up automatically on close
