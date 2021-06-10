import os
import pathlib
import pexpect
import rclone


class _Constants:
    """
    A list of constants used throughout this script
    """
    server_path: str = "/Users/joshl/Downloads/bedrock-backup/server/worlds"
    backup_path: str = "/tmp/bedrock-backup/"
    docker_attach: str = "docker attach bedrock-server"

    log_file: str = os.path.expanduser("~/projects/bedrock-server/log.txt")

    rclone_config: str = os.path.expanduser("~/.config/rclone/rclone.conf")
    rclone_sync_path: str = "onedrive:rclone/backup/bedrock-server/"


class Logging:
    """
    A simple logging class to write things to the screen or to the log file
    """
    @staticmethod
    def log_to_screen(message: str):
        print(message)

    @staticmethod
    def log_to_file(message: str):
        with open(_Constants.log_file, "a") as o_stream:
            o_stream.write(message)


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
    child.expect(["Data .+"])
    save_query_result: str = child.after.decode()

    child.sendline("save resume")
    child.expect(["Changes to the level are resumed.", "A previous save has not been completed."])

    child.sendcontrol("p")
    child.sendcontrol("q")

    child.close()

    return save_query_result


def get_files_dictionary(query_result: str) -> dict[str:int]:
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
        directory_path = file_path.split("/")[:-1]
        directory_path = os.path.join("/".join(directory_path))
    else:
        directory_path = item_path

    os.makedirs(directory_path, exist_ok=True)


def write_backups(files_dict: dict[str:int]):
    """
    Write files to the _Constants.backup_path location

    :param files_dict: A dictionary containing input file paths as the keys and bytes to read as values
    :return: None
    """
    for i, file_name in enumerate(files_dict):

        save_file_path: os.path = os.path.join(_Constants.backup_path, file_name)
        create_directory(save_file_path, True)

        read_file_path: os.path = os.path.join(path, file_name)
        read_bytes: int = files_dict[file_name]

        with open(read_file_path, "rb") as i_stream:
            lines = i_stream.read(read_bytes)

        with open(save_file_path, "wb") as o_stream:
            o_stream.write(lines)


def rclone_upload() -> bool:
    """
    Upload items in the _Constants.backup_path to the _Constants.rclone_sync path
    :return: True if upload successful, otherwise False
    """
    with open(_Constants.rclone_config, "r") as i_stream:
        cfg: str = i_stream.read()

    result = rclone.with_config(cfg)
    if result.sync(_Constants.backup_path, _Constants.rclone_sync_path):
        return True
    else:
        return False


if __name__ == '__main__':
    path = pathlib.Path(_Constants.server_path)
    child: pexpect.pty_spawn.spawn = pexpect.spawn(_Constants.docker_attach)
    query_result: str = query_save_server(child)
    files_list = get_files_dictionary(query_result)
    write_backups(files_list)

    rclone_upload()

    Logging.log_to_screen("Done")
