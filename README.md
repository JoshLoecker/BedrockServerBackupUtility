Bedrock Server Backup Utility
-----------------------------

This is a simple backup utility that will back up a bedrock server running in docker

### Installation
The following packages must be installed in pip

- docker
- pexpect
- python-rclone
- six

### Execution
1. Clone this repository (git clone https://github.com/JoshLoecker/BedrockServerBackupUtility)
2. Open the `main.py` file
3. Edit the variables under the `if __main__ == "main"` section
4. Only edit those variables which are under the header `# These values SHOULD be modified before running the server`

### Known Issues
The method for installation & execution is not good and should be better
This has not been tested with multiple worlds. I have zero idea what will happen if this is ran with multiple minecraft worlds open in docker
