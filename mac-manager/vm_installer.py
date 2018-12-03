from threading import Thread
from executor import ShellExecutor as Executor
from time import sleep
from downloader import Downloader as Dl
from os import path, makedirs
from installer_exceptions import IslandsImageNotFound, IslandSetupError, CmdExecutionError, PortForwardingException
from util import get_full_path

def check_output(func):
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        if res[0] != 0:
            raise CmdExecutionError(*res)
        return res
    return wrapper

class VMInstaller:
    def __init__(self,
                 setup,
                 on_message,
                 on_complete,
                 on_error,
                 data_path,
                 init_progres_bar,
                 update_progres_bar,
                 config,
                 finalize_progres_bar,
                 download=False,
                 image_path=None,
                 port=False):
        self.thread = None
        self.setup = setup
        self.message = on_message
        self.complete = on_complete
        self.error = on_error
        self.config = config
        self.init_progres_bar = init_progres_bar
        self.update_progres_bar = update_progres_bar
        self.finalize_progres_bar = finalize_progres_bar
        self.download = download
        self.data_path = data_path
        self.image_path = image_path
        self.port = port
        self.cmd = setup.cmd
        if not download:
            assert(bool(image_path))

    def start(self):
        self.thread = Thread(target=self.install)
        self.thread.start()

    def install(self):
        try:
            if self.download:
                self.init_progres_bar("Downloading Islands Virtual Machine...")
                self.download_vm()
                self.finalize_progres_bar()
                self.message(msg="Download complete", size=20)
            self.message("Importing VM...")
            vm_image_default_dest = get_full_path(self.config['downloads_path'] + self.config["vm_image_name"])
            self.import_vm(self.image_path if self.image_path else vm_image_default_dest, self.message, self.message)
            self.message("Image imported. Configuring...")
            self.setup_host_only_adapter()
            self.message("Network configured..")
            self.setup_shared_folder(self.data_path)
            self.message("Data folder set up... Launching VM")
            # Start machine... Wait until controlvm is available then run scripts
            self.start_vm(headless=False)
            self.message("VM started... You should see started Islands virtual machine window. "
                         "\nDo not close it until setup is finished!")
            self.insert_guest_additions_image()
            self.message("Guest additions mounted... Waiting for initial setup. \n"
                            "This will take a while! Do not turn off your computer.")
            self.wait_guest_additions()
            sleep(3)
            self.wait_guest_additions()
            if self.port:
                self.setup_port_forwarding(self.port)
            self.message("Guest additions are installed. Fetching Islands setup script..")
            self.onvm_get_setup_script()
            self.onvm_chmodx_install_script()
            self.message("Installation in progress. This step takes a while... Grab some tea")
            self.onvm_launch_setup_script()
            self.message("Setup completed. Restarting Islands...")
            sleep(1)
            self.shutdown_vm()
            self.first_boot()
            self.complete()
        except CmdExecutionError as e:
            print("CMD execution error: " + str(e))
            error_message = "CmdExecutionError.\nReturn code: {retcode}" \
                            "\nstderr: {stderr}" \
                            "\nstdout: {stdout}".format(retcode=e.args[0], stderr=e.args[1], stdout=e.args[2])
            self.error(msg=error_message, size=16)
        except IslandsImageNotFound as e:
            error_message = "Islands image was not found. Please restart setup."
            self.error(msg=error_message, size=16)
        except Exception as e:
            error_message = "Islands VM installation error: \n{msg}".format(msg=str(e))
            self.error(msg=error_message, size=16)

    def download_vm(self):
        Dl.get(url=self.config['vm_download'],
               dest_path=get_full_path(self.config["downloads_path"]),
               filename=self.config["vm_image_name"],
               on_update=self.update_progres_bar)

    def wait_guest_additions(self):
        for i in range(40):
            res = Executor.exec_sync(self.cmd.ls_on_guest())
            if res[0] == 0:
                print("Looks like guestcontrol is available on Islands VM! Returning...")
                return
            print("Awaiting for initial setup to complete..")
            sleep(15)
        raise IslandSetupError("Guest additions installation timed out. Please restart setup")

    @check_output
    def import_vm(self, path_to_image, on_data, on_error):
        if not path.exists(path_to_image):
            raise IslandsImageNotFound
        return Executor.exec_stream(self.cmd.import_vm(path_to_image=path_to_image),
            on_data=on_data, on_error=on_error)


    # This assumes that VM is already imported
    # There is no way to check whether vboxnet0 interface exists,
    # so we issue erroneous command to modify it
    # if exitcode is 1 - interface doesn't exists, so we create it
    # if exitcode is 2 - interface found and we can add it to our VM
    # Otherwise there is some other error and we raise it
    @check_output
    def setup_host_only_adapter(self):
        res = Executor.exec_sync(self.cmd.hostonly_config())
        if res[0] == 1:
            Executor.exec_sync(self.cmd.hostonly_create())
        elif res[0] != 2:
            raise Exception(res[2])
        # Installing adapter onto vm
        return Executor.exec_sync(self.cmd.hostonly_setup())

    # Sets up shareed folder for the imported vm
    @check_output
    def setup_shared_folder(self, data_folder_path=""):
        fullpath = get_full_path(data_folder_path)
        if not path.exists(fullpath):
            makedirs(fullpath)
        return Executor.exec_sync(self.cmd.sharedfolder_setup(fullpath))

    @check_output
    def start_vm(self, headless=True):
        return Executor.exec_sync(self.cmd.start_vm(headless))

    @check_output
    def insert_guest_additions_image(self):
        return Executor.exec_sync(self.cmd.insert_guest_additions())

    @check_output
    def setup_port_forwarding(self, port):
        island_ip = self.setup.get_islands_ip()
        if not island_ip:
            raise PortForwardingException("Was not able to determine ip address of Islands VM")
        res = Executor.exec_sync(self.cmd.setup_port_forwarding(island_ip, port))

        if res[0] == 0:
            self.config["local_access"] = "<a href='http://{island_ip}:4000'>http://{island_ip}:4000".format(island_ip=island_ip)
            self.config.save()
        return res

    @check_output
    def onvm_get_setup_script(self):
        return Executor.exec_sync(self.cmd.onvm_get_setup_script())

    @check_output
    def onvm_chmodx_install_script(self):
        return Executor.exec_sync(self.cmd.onvm_chmodx_install_script)

    @check_output
    def onvm_launch_setup_script(self):
        def on_data(msg):
            self.message(msg=msg, size=8, color="black")
        return Executor.exec_stream(
            self.cmd.onvm_launch_setup_script(),
            on_data=on_data, on_error=on_data)


    @check_output
    def shutdown_vm(self):
        return Executor.exec_sync(self.cmd.shutdown_vm())

    def first_boot(self):
        for i in range(10):
            sleep(3)
            try:
                self.start_vm()
                return
            except CmdExecutionError:
                print("Unsuccessful launch %d" %i)
                continue
        raise Exception("VM launch unsuccessfull")


