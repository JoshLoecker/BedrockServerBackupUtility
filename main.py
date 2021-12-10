import datetime
import docker
import os
import pathlib
import pexpect
import rclone
import shutil
from typing import Dict


class Logging:
    """
    A simple logging class to write things to the screen or to the log file
    """
    @staticmethod
    def log_to_screen(message: str):
        print(message)

    @staticmethod
    def log_to_file(log_file: str, message: str,):
        with open(log_file, "a") as o_stream:
            o_stream.write(message)


def get_server_binds() -> str:
    api: docker.APIClient = docker.APIClient()
    binds = api.inspect_container(server_name)["HostConfig"]

    mount_point = ""
    for bind in binds["Binds"]:
        temp_mount = bind.split(":")
        if temp_mount[1] == "/data":
            mount_point = temp_mount[0]
            break

    mount_point = os.path.join(mount_point, "worlds")
    return mount_point


def query_save_server(child: pexpect.pty_spawn.spawn) -> str:
    """
    Execute the save hold/query/resume commands on the bedrock server.
    These commands will be executed after attaching to the bedrock server

    :param child: The pexpect child process
    :return: A string containing the result of the 'save query' command
    """
    child.sendline("save hold")
    child.expect(["Saving...", "The command is already running"])

    child.sendline("save query")
    child.expect(["Data .+\n.+"])
    save_query_result: str = child.after.decode()

    child.sendline("save resume")
    child.expect(["Changes to the world are resumed.", "A previous save has not been completed."])

    child.sendcontrol("p")
    child.sendcontrol("q")

    child.close()

    return save_query_result


def get_files_dictionary(query_result: str) -> Dict[str, int]:
    """
    This function will produce a dictionary of file names and byte values to read

    {
        FILE_1: 100,
        FILE_2: 30,
        FILE_3: 10
    }

    :param query_result: The result from the query_save_server function
    :return: A dictionary containing strings as keys and integers as values
    """
    files: str = query_result.split("\n")[1]
    file_list: list = files.split(", ")

    file_name_list: list = [name.split(":")[0] for name in file_list]
    file_name_byte: list = [name.split(":")[1].rstrip() for name in file_list]
    files_dictionary: dict[str:int] = {}
    for i, (name, byte) in enumerate(zip(file_name_list, file_name_byte)):
        files_dictionary[name] = int(byte)

    return files_dictionary


def create_directory(item_path: str, file_name_included: bool = True):
    """
    Create directories to the incoming file path

    file_name_included = True
    Path: /A/Path/To/My/File.txt
    The final "File.txt" is not used as a path

    file_name_included = False
    Path: /A/Path/To/Directory
    The final "Directory" item is created


    :param item_path: The path to the file or directory to create
    :param file_name_included: Is the file name included in the input string?
    :return:
    """

    if file_name_included:
        directory_path = item_path.split("/")[:-1]
        directory_path = os.path.join("/".join(directory_path))
    else:
        directory_path = item_path

    os.makedirs(directory_path, exist_ok=True)


def write_backups(files_dict: Dict[str, int]):
    """
    Write files to the temp_backup_path location

    :param files_dict: A dictionary containing input file paths as the keys and bytes to read as values
    :return: None
    """
    for i, file_name in enumerate(files_dict):

        save_file_path: os.path = os.path.join(temp_backup_path, file_name)
        create_directory(save_file_path, True)

        read_file_path: os.path = os.path.join(path, file_name)
        read_bytes: int = files_dict[file_name]

        with open(read_file_path, "rb") as i_stream:
            lines = i_stream.read(read_bytes)

        with open(save_file_path, "wb") as o_stream:
            o_stream.write(lines)


def rclone_upload(file_path: str) -> bool:
    """
    Upload items in the temp_backup_path to the rclone_path path
    :return: True if upload successful, otherwise False
    """

    with open(rclone_config, "r") as i_stream:
        cfg: str = i_stream.read()

    result = rclone.with_config(cfg)
    if result.sync(file_path, rclone_sync_path):
        return True
    else:
        return False


def zip_temp_backup() -> str:
    """
    This function will zip the folder under the temp_backup_path
    After doing so, it will save the file in the following format
        YYYY-MM-DD-[FOLDER NAME].zip

    It will return a string of the new file path
    """
    curr_date = datetime.date.today()
    year = str(curr_date.year)
    month = f"{curr_date.month:02d}"
    day = f"{curr_date.day:02d}"

    backup_name = os.listdir(temp_backup_path)

    file_name = f"{year}-{month}-{day}-{backup_name[0]}"

    zip_file_name = os.path.join(temp_backup_path, file_name)
    shutil.make_archive(zip_file_name, "zip", temp_backup_path)
    return f"{zip_file_name}.zip"


def remove_temp_backup_path(backup_path: str):
    """
    Remove the temporary files that exist at the backup path location
    """
    shutil.rmtree(os.path.expanduser(backup_path))


if __name__ == '__main__':
    # These values SHOULD be modified before running the server
    server_name: str = "survival"
    temp_backup_path: str = os.path.expanduser("/tmp/bedrock-server-backups")
    log_file: str = os.path.expanduser("/opt/minecraft_backup/log.txt")
    rclone_sync_path: str = "onedrive:rclone/backup/bedrock-server/1.18"

    # These values SHOULD NOT be modified before running the server
    worlds_path: str = get_server_binds()
    docker_attach: str = f"docker attach {server_name}"
    rclone_config: str = os.path.expanduser("~/.config/rclone/rclone.conf")
    # -------

    path = pathlib.Path(worlds_path)

    child: pexpect.pty_spawn.spawn = pexpect.spawn(docker_attach)
    Logging.log_to_screen("Attached to docker container")

    query_result: str = query_save_server(child)
    Logging.log_to_screen("Queried server for files")

    files_list = get_files_dictionary(query_result)
    Logging.log_to_screen("Collected files list")

    Logging.log_to_screen("Writing to temporary files")
    write_backups(files_list)

    temp_zip_file = zip_temp_backup()
    print(temp_zip_file)

    Logging.log_to_screen("Starting upload. . .")
    # rclone_upload(temp_zip_file)
    Logging.log_to_screen("Finished upload")

    # remove_temp_backup_path(temp_backup_path)

    Logging.log_to_screen("Done")
