import datetime
import docker
import logging
import os
import pathlib
import pexpect
import rclone
import shutil
from typing import Dict
import zipfile


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

    if mount_point == "worlds":
        logging.critical(f"Unable to find mount point '/data' in server '{server_name}'")
        exit(1)

    return mount_point


def query_save_server(child: pexpect.pty_spawn.spawn) -> str:
    """
    Execute the save hold/query/resume commands on the bedrock server.
    These commands will be executed after attaching to the bedrock server

    :param child: The pexpect child process
    :return: A string containing the result of the 'save query' command
    """
    commands = ["save hold", "save query", "save resume"]
    expectations = [["Saving...", "The command is already running"],
                    ["Data .+\n.+"],
                    ["Changes to the world are resumed.", "A previous save has not been completed."]]

    error: bool = False
    save_query_result: str = ""
    for i, (command, expectation) in enumerate(zip(commands, expectations)):
        if error:
            exit(1)

        try:
            child.sendline(command)
            child.expect(expectation, timeout=3)

            if command == "save query":
                save_query_result: str = child.after.decode()

        except pexpect.exceptions.TIMEOUT:
            logging.error(f"Unable to find {expectation} in command {command} to server {server_name}")
            error = True


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
    cfg: str = open(rclone_config, "r").read()
    rclone_agent = rclone.with_config(cfg)

    logging.info(f"{rclone_agent.log.root.handlers[0].baseFilename}")

    valid_backup: bool = False

    logging.info(f"Starting upload")
    if rclone_agent.copy(file_path, rclone_sync_path):
        valid_backup = True
    logging.info("Upload complete")

    return valid_backup


def rename_backup_folder() -> str:
    """
    This function will rename the folder under the temp_backup_path
    It will save in the following format
        YYYY-MM-DD-[FOLDER NAME].zip

    It will return a string of the new file path (/tmp/backups/YYY-MM-DD-[FOLDER NAME])
    """

    current_date = datetime.datetime.now()
    year = f"{current_date.year}"
    month = f"{current_date.month:02d}"
    day = f"{current_date.day:02d}"
    hour = f"{current_date.hour:02d}"
    minute = f"{current_date.minute:02d}"
    second = f"{current_date.second:02d}"

    previous_folder_name = os.listdir(temp_backup_path)[0]
    previous_folder_path = os.path.join(temp_backup_path, previous_folder_name)

    new_folder_name = f"{year}-{month}-{day}_{hour}-{minute}-{second}-{previous_folder_name}"
    new_folder_path = os.path.join(temp_backup_path, new_folder_name)

    shutil.rmtree(new_folder_path, ignore_errors=True)
    shutil.move(previous_folder_path, new_folder_path)

    return new_folder_path


def remove_temp_backup_path(backup_path: str):
    """
    Remove the temporary files that exist at the backup path location
    """
    shutil.rmtree(os.path.expanduser(backup_path))



if __name__ == '__main__':
    # Logging parameters
    log_file = "/opt/minecraft_backup/log.txt"
    log_level = logging.INFO  # log anything above an INFO level
    log_mode = "a"  # append
    log_format = "%(asctime)s %(levelname)s\t:  %(message)s"  # Should not be changed
    date_format = "%Y/%m/%d %H:%M:%S"
    logging.basicConfig(filename=log_file, level=log_level, filemode=log_mode, format=log_format, datefmt=date_format)

    # These values SHOULD be modified before running the server
    server_name: str = "survival"
    temp_backup_path: str = os.path.expanduser("/tmp/bedrock-server-backups")
    rclone_sync_path: str = "onedrive:rclone/backup/bedrock-server/1.18"

    # These values SHOULD NOT be modified before running the server
    worlds_path: str = get_server_binds()
    docker_attach: str = f"docker attach {server_name}"
    rclone_config: str = os.path.expanduser("~/.config/rclone/rclone.conf")
    # -------

    path = pathlib.Path(worlds_path)
    child: pexpect.pty_spawn.spawn = pexpect.spawn(docker_attach)
    query_result: str = query_save_server(child)
    files_list = get_files_dictionary(query_result)

    write_backups(files_list)
    rename_backup_folder()

    rclone_upload(temp_backup_path)
    remove_temp_backup_path(temp_backup_path)
