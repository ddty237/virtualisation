from pyVim import connect
from pyVmomi import vim
import ssl
import json
import time

def connect_to_esxi(host, user, password):
    """Établit la connexion avec le serveur ESXi"""
    #je ne sais pas ce que le context fais mais je l'ai trouvé dans la docs
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.verify_mode = ssl.CERT_NONE
    
    si = connect.SmartConnect(
        host=host,
        user=user,
        pwd=password,
        sslContext=context
    )
    return si

def get_obj(content, vimtype, name):
    """Récupère un objet VMware vSphere par son nom"""
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vimtype, True
    )
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj

def create_dummy_vm(vm_name, si, vm_folder, resource_pool, datastore):
    """Crée une VM vide"""
    vmx_file = vim.vm.FileInfo(logDirectory=None,
                              snapshotDirectory=None,
                              suspendDirectory=None,
                              vmPathName=f"[{datastore}] {vm_name}/{vm_name}.vmx")
    
    config = vim.vm.ConfigSpec(
        name=vm_name,
        memoryMB=1024,
        numCPUs=1,
        files=vmx_file,
        guestId='otherLinux64Guest',
        version='vmx-14'
    )

    task = vm_folder.CreateVM_Task(config=config, pool=resource_pool)
    return task

def attach_cdrom(si, vm_name, iso_path):
    """Attache un CD-ROM à la VM"""
    content = si.RetrieveContent()
    vm = get_obj(content, [vim.VirtualMachine], vm_name)
    
    # Création du contrôleur IDE
    ide_controller = vim.vm.device.VirtualIDEController()
    ide_controller.key = 200
    ide_controller.device = [0]
    ide_controller.busNumber = 0
    
    # Configuration du CD-ROM
    cdrom = vim.vm.device.VirtualCdrom()
    cdrom.controllerKey = ide_controller.key
    cdrom.key = 3000
    cdrom.unitNumber = 0
    cdrom.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo(
        fileName=iso_path
    )
    cdrom.connectable = vim.vm.device.VirtualDevice.ConnectInfo(
        startConnected=True,
        allowGuestControl=True,
        connected=True
    )

    device_change = []
    device_change.append(
        vim.vm.device.VirtualDeviceSpec(
            operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
            device=ide_controller
        )
    )
    device_change.append(
        vim.vm.device.VirtualDeviceSpec(
            operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
            device=cdrom
        )
    )

    config_spec = vim.vm.ConfigSpec(deviceChange=device_change)
    task = vm.ReconfigVM_Task(spec=config_spec)
    return task

def deploy_ova(si, ova_path, num_instances):
    """Déploie plusieurs instances d'un OVA"""
    content = si.RetrieveContent()
    resource_pool = content.rootFolder.childEntity[0].hostFolder.childEntity[0].resourcePool
    vm_folder = content.rootFolder.childEntity[0].vmFolder
    
    for i in range(num_instances):
        vm_name = f"TINY_OVA_{i+1}"
        # Ici, vous devrez utiliser l'API OVF pour déployer l'OVA
        # Cette partie nécessite l'utilisation de ovftool ou de l'API OVF

def clone_vm(si, source_vm_name, new_vm_name):
    """Clone une VM existante"""
    content = si.RetrieveContent()
    source_vm = get_obj(content, [vim.VirtualMachine], source_vm_name)
    
    if source_vm is None:
        raise Exception(f"VM source {source_vm_name} non trouvée")
        
    relocate_spec = vim.vm.RelocateSpec()
    clone_spec = vim.vm.CloneSpec(
        location=relocate_spec,
        powerOn=False,
        template=False
    )
    
    task = source_vm.Clone(
        folder=source_vm.parent,
        name=new_vm_name,
        spec=clone_spec
    )
    return task

def create_vm_from_scratch(config):
    """Crée une nouvelle VM selon la configuration JSON"""
    si = connect_to_esxi(
        config['esxi']['host'],
        config['esxi']['user'],
        config['esxi']['password']
    )
    content = si.RetrieveContent()
    
    vm_folder = content.rootFolder.childEntity[0].vmFolder
    resource_pool = content.rootFolder.childEntity[0].hostFolder.childEntity[0].resourcePool
    
    for vm in config['vms']:
        # Création de la VM vide
        task = create_dummy_vm(
            vm['name'],
            si,
            vm_folder,
            resource_pool,
            config['datastore']
        )
        
        # Attendre la fin de la création
        while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
            time.sleep(1)
            
        if task.info.state == vim.TaskInfo.State.error:
            raise Exception(f"Erreur lors de la création de la VM: {task.info.error}")
            
        # Attacher le CD-ROM si spécifié
        if 'iso_path' in vm:
            attach_cdrom(si, vm['name'], vm['iso_path'])

def main():
    # Exemple de fichier de configuration
    config = {
        "esxi": {
            "host": "192.168.1.100",
            "user": "root",
            "password": "password"
        },
        "datastore": "datastore1",
        "vms": [
            {
                "name": "TestVM1",
                "ram": 1024,
                "cpu": 1,
                "disk_size": 20,
                "iso_path": "[datastore1] test/Core-5.4.iso"
            }
        ]
    }
    
    create_vm_from_scratch(config)

if __name__ == "__main__":
    main()
