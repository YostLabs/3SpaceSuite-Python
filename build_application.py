#In addition to the requirements in requirements.txt,
#this script requires PyInstaller and GitPython

import os
import PyInstaller.__main__
import pathlib
import git
import time
import shutil
import datetime

#----------------------------DETERMINE VERSION TO DISPLAY BASED ON GIT STATUS----------------------------
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


#-----------------------------CLEAN UP OLD BUILD FOLDERS----------------------------

build_folder = parent_folder / "build"
dist_folder = parent_folder / "dist"
if build_folder.exists():
    shutil.rmtree(build_folder)
if dist_folder.exists():
    shutil.rmtree(dist_folder)

#-----------------------------APPLY BUILD SETTINGS-----------------------------

debug = False
os.environ["TSS3_DEBUG_BUILD"] = "1" if debug else "0"

#----------------------------------RUN THE BUILD--------------------------------

PyInstaller.__main__.run([
    'TSS-3 Suite.spec',
    '--noconfirm',
    '--clean',
])

print()
print("Finished building version:", version)