#In addition to the requirements in requirements.txt,
#this script requires PyInstaller and GitPython

import glfw.library
import PyInstaller.__main__
import pathlib
import git
import time
import shutil
import datetime

try:
    repo = git.Repo(".")
    current_commit = repo.head.commit

    if repo.is_dirty():
        dt = datetime.datetime.now()
        version = f"v{dt.year}.{dt.month}.{dt.day}"
        version += f" DEBUG"
    else:
        #Compensate for timezone
        commit_date = current_commit.authored_date - current_commit.committer_tz_offset
        commit_date = time.gmtime(commit_date)

        version = f"v{commit_date.tm_year}.{commit_date.tm_mon}.{commit_date.tm_mday}"

    if repo.active_branch != repo.heads.main:
        version += f" {repo.active_branch.name}"
    else:
        #Check if committed
        exists = False
        for commit in repo.iter_commits("origin/main"):
            if commit == current_commit:
                exists = True
                break
        if not exists:
            version += " Custom"
except:
    local_time = time.localtime()
    version = f"v{local_time.tm_year}.{local_time.tm_mon}.{local_time.tm_mday} Custom"

parent_folder = pathlib.Path(__file__).parent

#Write the version to a file that can be read by the application.
#This file is ignored by the git repository
with open(parent_folder / "resources" / "version.txt", 'w') as fp:
    fp.write(version)

#Clean up any old folders for a clean build
build_folder = parent_folder / "build"
dist_folder = parent_folder / "dist"
if build_folder.exists():
    shutil.rmtree(build_folder)
if dist_folder.exists():
    shutil.rmtree(dist_folder)


debug = False

cmd_properties = []
cmd_properties.append(f'src/main.py')
cmd_properties.append(f"--paths=src")
#cmd_properties.append(f'--specpath=src')
cmd_properties.append(f"--add-binary={glfw.library.glfw._name}:glfw")
cmd_properties.append(f"--add-data=resources:resources")
cmd_properties.append(f"--icon=resources/images/icon.ico")
cmd_properties.append(f"--splash=resources/images/logo.jpg")
cmd_properties.append(f"--noconfirm")

if not debug:
    cmd_properties.append(f"--name=TSS-3 Suite")
    cmd_properties.append(f"--noconsole")
else:
    cmd_properties.append(f"--name=TSS-3 Suite DEV")

PyInstaller.__main__.run(cmd_properties)

print()
print("Finished building version:", version)